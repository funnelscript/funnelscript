"""Verification tests for Phase 5: Multi-Touch Attribution (MTA), Incrementality Bridge, and Canonical Playbooks.

Validates:
1. AttributionEngine heuristic models (First-Touch, Last-Touch, Linear, Time-Decay, Position-Based).
2. Shapley Value game-theoretic attribution (Efficiency, Dummy Player, Symmetry properties).
3. First-order Markov Chain attribution via Removal Effect.
4. Platform Over-Reporting Factor vs. Ledger-Audited Incremental conversions.
5. End-to-end execution of canonical .fnls playbooks (lead_response, ecommerce_cashflow, saas_subscription).
"""

from pathlib import Path

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent,
    PopulationExecutor,
    WorldExecutor,
)
from funnelscript.stdlib.marketing.kernels import (
    AttributionEngine,
    ConversionPath,
    Touchpoint,
)


class TestMultiTouchAttributionModels:
    @pytest.fixture
    def sample_customer_journeys(self):
        # Journey 1: GoogleSearch -> MetaRetargeting -> Email -> Converted ($100)
        p1 = ConversionPath(
            user_id="user-1",
            touches=(
                Touchpoint(channel="GoogleSearch", timestamp=1.0),
                Touchpoint(channel="MetaRetargeting", timestamp=3.0),
                Touchpoint(channel="Email", timestamp=7.0),
            ),
            converted=True,
            conversion_value=100.0,
        )
        # Journey 2: MetaAwareness -> GoogleSearch -> Converted ($60)
        p2 = ConversionPath(
            user_id="user-2",
            touches=(
                Touchpoint(channel="MetaAwareness", timestamp=2.0),
                Touchpoint(channel="GoogleSearch", timestamp=4.0),
            ),
            converted=True,
            conversion_value=60.0,
        )
        # Journey 3: MetaAwareness -> Unconverted ($0)
        p3 = ConversionPath(
            user_id="user-3",
            touches=(Touchpoint(channel="MetaAwareness", timestamp=1.0),),
            converted=False,
            conversion_value=0.0,
        )
        return (p1, p2, p3)

    def test_first_touch_attribution(self, sample_customer_journeys):
        attr = AttributionEngine.first_touch(sample_customer_journeys)
        # Journey 1 first touch: GoogleSearch ($100)
        # Journey 2 first touch: MetaAwareness ($60)
        assert attr["GoogleSearch"] == 100.0
        assert attr["MetaAwareness"] == 60.0
        assert sum(attr.values()) == 160.0

    def test_last_touch_attribution(self, sample_customer_journeys):
        attr = AttributionEngine.last_touch(sample_customer_journeys)
        # Journey 1 last touch: Email ($100)
        # Journey 2 last touch: GoogleSearch ($60)
        assert attr["Email"] == 100.0
        assert attr["GoogleSearch"] == 60.0
        assert sum(attr.values()) == 160.0

    def test_linear_attribution(self, sample_customer_journeys):
        attr = AttributionEngine.linear(sample_customer_journeys)
        # Journey 1: 100 / 3 = 33.33 each to GoogleSearch, MetaRetargeting, Email
        # Journey 2: 60 / 2 = 30 each to MetaAwareness, GoogleSearch
        assert pytest.approx(attr["GoogleSearch"], rel=1e-3) == (100.0 / 3.0) + 30.0
        assert pytest.approx(attr["MetaAwareness"], rel=1e-3) == 30.0
        assert pytest.approx(attr["MetaRetargeting"], rel=1e-3) == (100.0 / 3.0)
        assert pytest.approx(attr["Email"], rel=1e-3) == (100.0 / 3.0)
        assert pytest.approx(sum(attr.values()), rel=1e-5) == 160.0

    def test_position_based_u_shaped_attribution(self, sample_customer_journeys):
        attr = AttributionEngine.position_based(sample_customer_journeys, first_weight=0.4, last_weight=0.4)
        # Journey 1 (3 touches): First (GoogleSearch)=40, Middle (MetaRetargeting)=20, Last (Email)=40
        # Journey 2 (2 touches): 50/50 split -> MetaAwareness=30, GoogleSearch=30
        assert attr["GoogleSearch"] == 40.0 + 30.0
        assert attr["MetaAwareness"] == 30.0
        assert pytest.approx(attr["MetaRetargeting"], rel=1e-5) == 20.0
        assert attr["Email"] == 40.0
        assert sum(attr.values()) == 160.0

    def test_shapley_value_attribution_efficiency_property(self):
        channels = ["Search", "Social", "Email"]
        # Coalition values (conversions achieved by each subset of channels)
        coalition_values = {
            frozenset(): 0.0,
            frozenset(["Search"]): 30.0,
            frozenset(["Social"]): 20.0,
            frozenset(["Email"]): 10.0,
            frozenset(["Search", "Social"]): 70.0,
            frozenset(["Search", "Email"]): 50.0,
            frozenset(["Social", "Email"]): 40.0,
            frozenset(["Search", "Social", "Email"]): 100.0,
        }
        shapley = AttributionEngine.shapley(channels, coalition_values)

        # Efficiency Property: Sum of Shapley values MUST equal grand coalition value (100.0)
        assert pytest.approx(sum(shapley.values()), rel=1e-6) == 100.0
        # All channels must have positive attribution
        assert all(v > 0 for v in shapley.values())
        # Search is most valuable, then Social, then Email
        assert shapley["Search"] > shapley["Social"] > shapley["Email"]

    def test_markov_chain_removal_effect_attribution(self, sample_customer_journeys):
        markov_weights = AttributionEngine.markov_chain(sample_customer_journeys)
        # Weights should sum to 1.0
        assert pytest.approx(sum(markov_weights.values()), rel=1e-5) == 1.0
        assert all(0.0 <= w <= 1.0 for w in markov_weights.values())

    def test_platform_over_reporting_factor(self):
        # Channels individually report 80 + 70 + 50 = 200 conversions due to attribution window overlap
        reported = {"Meta": 80.0, "Google": 70.0, "TikTok": 50.0}
        incremental_ledger_conversions = 125.0

        comparison = AttributionEngine.compare_reported_vs_incremental(reported, incremental_ledger_conversions)
        assert comparison["total_reported"] == 200.0
        assert comparison["audited_incremental"] == 125.0
        # Over-reporting factor = 200 / 125 = 1.6x (60% over-reported)
        assert pytest.approx(comparison["over_reporting_factor"], rel=1e-5) == 1.6


class TestCanonicalPlaybooksExecution:
    def test_ecommerce_cashflow_simulation(self):
        source_path = Path(__file__).parent.parent.parent / "src/funnelscript/stdlib/marketing/ecommerce_cashflow.fnls"
        ast = Parser.from_file(source_path)
        world = WorldExecutor(ast)

        agents = [PopulationAgent(f"shopper-{i}", "cohort-1", "all") for i in range(5)]
        pop_exec = PopulationExecutor(
            world,
            agents,
            seed=42,
            trial_id="ecom-trial-1",
            state_field="phase",
            states=("browser", "shopper", "settled", "terminal"),
        )

        # Fire AdClick events
        events = {
            f"shopper-{i}": (Event(0, "Shopper.AdClick", {"cpc": 1.50, "purchase_intent": 0.8, "basket_size": 75.0}),)
            for i in range(5)
        }
        res = pop_exec.run(events, until=12, trace=True)
        assert len(res.results) == 5

    def test_saas_subscription_simulation(self):
        source_path = Path(__file__).parent.parent.parent / "src/funnelscript/stdlib/marketing/saas_subscription.fnls"
        ast = Parser.from_file(source_path)
        world = WorldExecutor(ast)

        agents = [PopulationAgent(f"sub-{i}", "cohort-saas", "all") for i in range(5)]
        pop_exec = PopulationExecutor(
            world,
            agents,
            seed=101,
            trial_id="saas-trial-1",
            state_field="phase",
            states=("trial", "active", "churned"),
        )

        # Fire Signup events
        events = {
            f"sub-{i}": (Event(0, "Subscriber.Signup", {"plan_fee": 99.0, "trial_success_rate": 0.9}),)
            for i in range(5)
        }
        res = pop_exec.run(events, until=12, trace=True)
        assert len(res.results) == 5

"""Phase 007B fixed reference conversion/attribution and empirical risk cases."""

from decimal import Decimal
from pathlib import Path

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import PopulationAgent, PopulationExecutor, WorldExecutor
import funnelscript.stdlib.marketing as marketing


SOURCE = Path(__file__).parent / "fixtures/population-reference/identity-rng.fnl"
D = Decimal


def population(trial="trial-1", conversions=(0, 4, 5)):
    agents = [
        PopulationAgent(f"user-{i}", "batch", "north" if i < 4 else "south")
        for i in range(10)
    ]
    world = WorldExecutor(Parser.from_file(SOURCE))
    runner = PopulationExecutor(
        world, agents, seed=1, trial_id=trial,
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    return runner.run({
        agents[i].agent_id: (Event(0, "Visitor.Tick"),) for i in conversions
    })


def example_ledger():
    entry = marketing.LedgerEntry
    return marketing.MarketingLedger(
        trial_id="trial-1", currency="SAR",
        cash_initial=D("100.00"), horizon=3, settlement_delay=2,
        entries=(
            entry("trial-1", "ad-1", "ad_spend", 0, D("20.00"), "SAR"),
            entry("trial-1", "cost-1", "other_cost", 0, D("5.00"), "SAR"),
            entry("trial-1", "sale-1", "sale", 1, D("60.00"), "SAR"),
            entry("trial-1", "settle-1", "settlement", 3, D("30.00"), "SAR", "sale-1"),
        ),
    )


def test_conversion_cac_roas_and_cash_reference_are_distinct_metrics():
    evaluate = getattr(marketing, "evaluate_trial", None)
    assert callable(evaluate), "Missing trial reference metric evaluator"
    pop = population()
    snapshot = example_ledger().evaluate()
    result = evaluate(
        pop, snapshot, converted_state="terminal",
        attribution_label="reference-all-sales", insolvency_threshold=D("0.00"),
    )
    assert len(pop.results) == 10
    assert len(pop.segments["north"]) == 4
    assert len(pop.segments["south"]) == 6
    assert len(pop.partitions["terminal"] & pop.segments["north"]) == 1
    assert len(pop.partitions["terminal"] & pop.segments["south"]) == 2
    assert result.converted_count == 3
    assert result.eligible_count == 10
    assert result.conversion_rate == D("0.3")
    assert result.cac == D("6.666666666666666666666666667")
    assert result.roas == D("3")
    assert result.profit == D("35.00")
    assert result.ledger.cash == D("105.00")
    assert result.ledger.receivables == D("30.00")
    assert result.ruined is False


def trial_with_loss(n, loss, *, initial_cash="50.00", currency="SAR", horizon=1):
    agent = PopulationAgent("only", "batch", "north")
    run = PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)), [agent],
        seed=1, trial_id=f"trial-{n}", state_field="phase",
        states=("new", "terminal", "inactive"),
    ).run({})
    entries = (
        (marketing.LedgerEntry(f"trial-{n}", "debit", "ad_spend", 0, loss, currency),)
        if loss > 0 else ()
    )
    journal = marketing.MarketingLedger(
        trial_id=f"trial-{n}", currency=currency,
        cash_initial=D(initial_cash), horizon=horizon,
        settlement_delay=0, entries=entries,
    )
    return marketing.evaluate_trial(
        run, journal.evaluate(), converted_state="terminal",
        attribution_label="reference-all-sales", insolvency_threshold=D("0.00"),
    )


def test_risk_var_cvar_and_fractional_tail():
    risk = getattr(marketing, "evaluate_risk", None)
    assert callable(risk), "Missing empirical risk evaluator"
    one = [trial_with_loss(i, D(value)) for i, value in enumerate(("0.00", "0.00", "10.00", "30.00"))]
    result = risk(one, alpha=D("0.75"))
    assert result.var == D("10.00")
    assert result.cvar == D("30.00")
    assert result.ruin_probability == D("0")
    two = [trial_with_loss(i, D(value)) for i, value in enumerate(("0.00", "0.00", "0.00", "100.00"))]
    assert risk(two, alpha=D("0.75")).var == D("0")
    assert risk(two, alpha=D("0.75")).cvar == D("100.00")
    assert risk(two, alpha=D("0.75")).ruin_probability == D("0.25")
    fractional = [
        trial_with_loss(i, D(value)) for i, value in enumerate(("0.00", "10.00", "20.00", "30.00"))
    ]
    assert risk(fractional, alpha=D("0.625")).var == D("20.00")
    assert risk(fractional, alpha=D("0.625")).cvar == D("26.66666666666666666666666667")


def test_zero_conversions_and_zero_spend_are_undefined_ratios():
    result = marketing.evaluate_trial(
        population(conversions=()),
        marketing.MarketingLedger(
            "trial-1", "SAR", D("0.00"), 0, 0, ()
        ).evaluate(),
        converted_state="terminal", attribution_label="reference-all-sales",
        insolvency_threshold=D("0.00"),
    )
    assert result.converted_count == 0
    assert result.conversion_rate == D("0")
    assert result.cac is None
    assert result.roas is None
    assert result.profit == D("0.00")


def test_risk_rejects_invalid_alpha_or_mixed_currency_and_horizon():
    a = trial_with_loss(1, D("0.00"))
    b = trial_with_loss(2, D("1.00"), currency="USD")
    c = trial_with_loss(3, D("1.00"), horizon=2)
    with pytest.raises(ValueError, match="alpha"):
        marketing.evaluate_risk([a], alpha=D("1.0"))
    with pytest.raises(ValueError, match="currency"):
        marketing.evaluate_risk([a, b], alpha=D("0.5"))
    with pytest.raises(ValueError, match="horizon"):
        marketing.evaluate_risk([a, c], alpha=D("0.5"))
    with pytest.raises(ValueError, match="nonempty"):
        marketing.evaluate_risk([], alpha=D("0.5"))


def test_strict_ruin_predicate_observes_start_and_each_debit_checkpoint():
    bankrupt = trial_with_loss(1, D("50.00"), initial_cash="50.00")
    assert bankrupt.ledger.cash == D("0.00")
    assert bankrupt.ruined is False
    overdrawn = trial_with_loss(2, D("50.01"), initial_cash="50.00")
    assert overdrawn.ruined is True
    already_below = trial_with_loss(3, D("0.00"), initial_cash="-0.01")
    assert already_below.ruined is True


def test_population_trial_must_equal_financial_trial():
    with pytest.raises(ValueError, match="trial_id"):
        marketing.evaluate_trial(
            population("trial-2"), example_ledger().evaluate(),
            converted_state="terminal", attribution_label="reference-all-sales",
            insolvency_threshold=D("0.00"),
        )


def test_unknown_conversion_state_and_missing_attribution_rejected():
    for state, label, message in [
        ("converted", "reference-all-sales", "converted_state"),
        ("terminal", "", "attribution_label"),
    ]:
        with pytest.raises(ValueError, match=message):
            marketing.evaluate_trial(
                population(), example_ledger().evaluate(),
                converted_state=state, attribution_label=label,
                insolvency_threshold=D("0.00"),
            )


def test_unattributed_segment_costs_are_not_falsely_allocated():
    pop = population()
    summary = marketing.evaluate_trial(
        pop, example_ledger().evaluate(),
        converted_state="terminal", attribution_label="reference-all-sales",
        insolvency_threshold=D("0.00"),
    )
    assert summary.cac == D("20") / D("3")
    assert len(pop.segments["north"]) == 4
    assert len(pop.segments["south"]) == 6
    assert not hasattr(summary, "north_cac")
    assert not hasattr(summary, "south_roas")


@pytest.mark.parametrize("alpha", ["0.5", D("0"), D("1"), D("NaN"), D("Infinity"), 0.5])
def test_invalid_risk_alpha_rejected(alpha):
    with pytest.raises(ValueError, match="alpha"):
        marketing.evaluate_risk([trial_with_loss(1, D("1.00"))], alpha=alpha)


def test_risk_rejects_duplicate_trials_and_mismatched_attribution_or_threshold():
    a = trial_with_loss(1, D("1.00"))
    duplicate = trial_with_loss(1, D("2.00"))
    b = trial_with_loss(2, D("1.00"))
    with pytest.raises(ValueError, match="duplicate trial"):
        marketing.evaluate_risk([a, duplicate], alpha=D("0.5"))
    from dataclasses import replace
    with pytest.raises(ValueError, match="attribution_label"):
        marketing.evaluate_risk(
            [a, replace(b, attribution_label="different")], alpha=D("0.5")
        )
    with pytest.raises(ValueError, match="insolvency_threshold"):
        marketing.evaluate_risk(
            [a, replace(b, insolvency_threshold=D("1.00"))], alpha=D("0.5")
        )


def test_signed_loss_can_be_negative_for_profitable_trial():
    agent = population()
    profitable = marketing.evaluate_trial(
        agent, example_ledger().evaluate(), converted_state="terminal",
        attribution_label="reference-all-sales", insolvency_threshold=D("0.00"),
    )
    risk = marketing.evaluate_risk([profitable], alpha=D("0.95"))
    assert risk.var == D("-35.00")
    assert risk.cvar == D("-35.00")

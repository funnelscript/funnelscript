"""Bounded synthetic population -> explicit ledger reference integration (Phase 007B).

Every conversion event and all money assumptions are hand specified, not inferred
or calibrated market behavior.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import PopulationAgent, PopulationExecutor, WorldExecutor
from funnelscript.stdlib.marketing import (
    LedgerEntry, MarketingLedger, evaluate_trial,
)

SOURCE = Path(__file__).parent / "fixtures/population-reference/identity-rng.fnl"
D = Decimal


def integrated_case(size, trial):
    agents = [
        PopulationAgent(f"agent-{i:04}", f"cohort-{i // 10:03}", "north" if i % 10 < 4 else "south")
        for i in range(size)
    ]
    converted = {
        agent.agent_id for i, agent in enumerate(agents)
        if i % 10 in (0, 4, 5)
    }
    pop = PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)), agents,
        trial_id=trial, seed=1, state_field="phase",
        states=("new", "terminal", "inactive"),
    )
    result = pop.run({
        aid: (Event(0, "Visitor.Tick"),) for aid in sorted(converted)
    })
    entries = [
        LedgerEntry(trial, "ads", "ad_spend", 0, D(size * 2), "SAR"),
        LedgerEntry(trial, "other", "other_cost", 0, D(size) / 2, "SAR"),
    ]
    for aid in sorted(converted):
        entries.append(LedgerEntry(trial, "sale-" + aid, "sale", 1, D(20), "SAR"))
    for aid in sorted(converted):
        entries.append(
            LedgerEntry(trial, "pay-" + aid, "settlement", 3, D(10), "SAR", "sale-" + aid)
        )
    ledger = MarketingLedger(trial, "SAR", D(size * 10), 3, 2, tuple(entries))
    metrics = evaluate_trial(
        result, ledger.evaluate(), converted_state="terminal",
        attribution_label="controlled-reference", insolvency_threshold=D(0),
    )
    return result, metrics


@pytest.mark.parametrize("size", [10, 100, 1000])
@pytest.mark.parametrize("trial", ["trial-1", "trial-2"])
def test_two_segment_population_reconciles_agent_specific_delayed_receipts(size, trial):
    result, metrics = integrated_case(size, trial)
    assert len(result.results) == size
    assert len(result.segments["north"]) == size * 4 // 10
    assert len(result.segments["south"]) == size * 6 // 10
    assert len(result.partitions["terminal"]) == size * 3 // 10
    assert metrics.converted_count == size * 3 // 10
    assert metrics.conversion_rate == D("0.3")
    assert metrics.ledger.cash == D(size) * D("10.5")
    assert metrics.ledger.receivables == D(size) * D("3")
    assert metrics.ledger.recognized_revenue == D(size) * D("6")
    assert metrics.ledger.settled_receipts == D(size) * D("3")
    assert metrics.ledger.paid_ad_spend == D(size) * D("2")
    assert metrics.ledger.paid_other_costs == D(size) / 2
    assert metrics.profit == D(size) * D("3.5")
    assert metrics.roas == D(3)
    assert metrics.ruined is False
    assert set().union(*result.partitions.values()) == set(result.results)
    assert all(a in result.results for a in result.partitions["terminal"])

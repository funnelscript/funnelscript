"""Independent financial readout of resumed agent-based World trials.

Research anchor: accrual accounting conservation + discrete-event replay.
H: the same paid/settled source actions produce identical exact-Decimal
financial metrics for a continuously executed vs a restored population.
Invariant: cash_final = cash_initial - spend - costs + settlements and
receivables = recognized sales - settlements, without floats or rounding
drift at any cohort size, intervention, or restoration boundary.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent,
    PopulationExecutor,
    WorldExecutor,
)
from funnelscript.stdlib.marketing import (
    LedgerEntry,
    MarketingLedger,
    evaluate_trial,
)

D = Decimal
SOURCE = Path(__file__).resolve().parents[2] / (
    "tests/fixtures/population-reference/identity-rng.fnl"
)


def _setup(n: int, *, trial: str = "checkpoint-finance", seed: int = 98):
    enrolled = tuple(
        PopulationAgent(
            f"visitor-{i:04d}",
            f"batch-{i // 10}",
            "north" if i % 2 else "south",
        )
        for i in range(n)
    )
    runner = PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)),
        enrolled, seed=seed, trial_id=trial,
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    return runner, enrolled


def _source_events(enrolled, converted, disabled):
    return {
        agent.agent_id: (
            (Event(0, "Visitor.Tick"), Event(4, "Visitor.Tick"))
            if agent.agent_id in converted
            else (Event(0, "Visitor.Deactivate"),)
        )
        for agent in enrolled
        if agent.agent_id in converted or agent.agent_id in disabled
    }


def _finance(trial, enrolled, converted, *, change_settlement=None):
    n = len(enrolled)
    entries = [
        LedgerEntry(trial, "ad-cost", "ad_spend", 0, D(2 * n), "SAR"),
        LedgerEntry(trial, "other-cost", "other_cost", 0, D(n) / 2, "SAR"),
    ]
    for aid in sorted(converted):
        entries.append(
            LedgerEntry(trial, f"sale-{aid}", "sale", 1, D("20.00"), "SAR")
        )
        amount = D("10.00")
        if change_settlement == aid:
            amount = D("9.99")
        entries.append(LedgerEntry(
            trial, f"settle-{aid}", "settlement", 3,
            amount, "SAR", source_tx_id=f"sale-{aid}",
        ))
    return MarketingLedger(
        trial, "SAR", D(10 * n), 5, 2,
        tuple(sorted(entries, key=lambda entry: (entry.day, entry.tx_id))),
    )


def _metrics(result, ledger):
    return evaluate_trial(
        result, ledger.evaluate(),
        converted_state="terminal",
        attribution_label="controlled-population-checkpoint",
        insolvency_threshold=D(0),
    )


@settings(max_examples=60, deadline=None)
@given(
    st.integers(min_value=1, max_value=45),
    st.integers(min_value=0, max_value=2**32 - 1),
    st.integers(min_value=0, max_value=7),
)
def test_hypothesis_financial_conservation_under_partial_world_restoration(
    n, seed, split,
):
    runner, enrolled = _setup(n, seed=seed)
    converted = {
        agent.agent_id for index, agent in enumerate(enrolled)
        if index % 3 in (0, 2)
    }
    disabled = {
        agent.agent_id for index, agent in enumerate(enrolled)
        if index % 3 == 1
    }
    inputs = _source_events(enrolled, converted, disabled)
    expected = runner.run(inputs)
    live = runner.start(inputs)
    before = live.advance(until=split)
    restored = runner.restore(live.snapshot()).advance()
    assert restored == expected
    journal = _finance(runner.trial_id, enrolled, converted)
    original = _metrics(expected, journal)
    replayed = _metrics(restored, journal)
    assert original == replayed
    assert before.trial_id == replayed.trial_id
    assert replayed.converted_count == len(converted)
    snap = journal.evaluate()
    amount_settled = D("10.00") * len(converted)
    amount_recognized = D("20.00") * len(converted)
    assert snap.cash == D("7.5") * n + amount_settled
    assert snap.receivables == amount_recognized - amount_settled
    assert snap.recognized_revenue == amount_recognized
    assert snap.settled_receipts == amount_settled
    assert snap.profit == amount_recognized - D("2.5") * n


@pytest.mark.parametrize("n", (10, 100, 1_000))
def test_aggregate_population_checkpoint_reconciles_segmented_cash_flow(n):
    runner, enrolled = _setup(n)
    converted = {
        agent.agent_id for index, agent in enumerate(enrolled)
        if index % 10 in (0, 4, 5)
    }
    inputs = _source_events(enrolled, converted, set())
    live = runner.start(inputs)
    at_day_zero = live.advance(until=0)
    assert at_day_zero.partitions["terminal"] == frozenset(converted)
    at_day_one = runner.restore(live.snapshot()).advance(until=1)
    final = runner.restore(live.snapshot()).advance()
    expected = runner.run(inputs)
    assert final == expected
    assert at_day_one == at_day_zero
    assert len(final.partitions["terminal"]) == n * 3 // 10
    assert set().union(*final.partitions.values()) == set(final.results)
    ledger = _finance(runner.trial_id, enrolled, converted)
    expected_finances = _metrics(expected, ledger)
    actual_finances = _metrics(final, ledger)
    assert actual_finances == expected_finances
    assert actual_finances.ledger.cash == D(n) * D("10.5")
    assert actual_finances.ledger.receivables == D(n) * D(3)
    assert actual_finances.ledger.profit == D(n) * D("3.5")


def test_partial_checkpoints_do_not_double_post_financial_events():
    runner, enrolled = _setup(30)
    converted = {agent.agent_id for agent in enrolled[:10]}
    inputs = _source_events(enrolled, converted, set())
    ledger = _finance(runner.trial_id, enrolled, converted)
    session = runner.start(inputs)
    session.advance(until=0)
    checkpoint = session.snapshot()
    one = runner.restore(checkpoint).advance()
    two = runner.restore(checkpoint).advance()
    assert one == two
    assert _metrics(one, ledger) == _metrics(two, ledger)
    assert len(ledger.entries) == 2 + len(converted) * 2
    assert len({item.tx_id for item in ledger.entries}) == len(ledger.entries)


def test_tampered_settlement_changes_cash_without_mutating_world_rng():
    runner, enrolled = _setup(10)
    converted = {enrolled[0].agent_id, enrolled[1].agent_id}
    inputs = _source_events(enrolled, converted, set())
    active = runner.start(inputs)
    active.advance(max_steps=1)
    recovered = runner.restore(active.snapshot()).advance()
    original = runner.run(inputs)
    assert original == recovered
    ledger = _finance(runner.trial_id, enrolled, converted)
    lower = _finance(
        runner.trial_id, enrolled, converted,
        change_settlement=enrolled[0].agent_id,
    )
    baseline = _metrics(recovered, ledger)
    edited = _metrics(recovered, lower)
    assert baseline.ledger.cash - edited.ledger.cash == D("0.01")
    assert edited.ledger.receivables - baseline.ledger.receivables == D("0.01")
    assert baseline.ledger.profit == edited.ledger.profit
    assert baseline.converted_count == edited.converted_count
    assert recovered == original


def test_financial_ledger_restoration_remains_an_explicit_separate_contract():
    runner, enrolled = _setup(10)
    converted = {enrolled[0].agent_id}
    population = runner.start(_source_events(enrolled, converted, set()))
    checkpoint = population.snapshot()
    assert not hasattr(checkpoint, "uncommitted_financial_transactions")
    assert not hasattr(checkpoint, "ledger_checkpoint")
    ledger = _finance(runner.trial_id, enrolled, converted)
    assert _metrics(runner.restore(checkpoint).advance(), ledger).ledger == (
        _metrics(runner.run(_source_events(enrolled, converted, set())), ledger).ledger
    )


def test_replay_not_affected_by_unrelated_agent_in_same_cohort():
    runner, enrolled = _setup(12)
    converted = {enrolled[0].agent_id, enrolled[2].agent_id}
    inputs = _source_events(enrolled, converted, set())
    snap = runner.start(inputs).snapshot()
    expected = runner.run(inputs)
    other = replace(enrolled[1], segment_id="west")
    new_enrolled = (enrolled[0], other, *enrolled[2:])
    other_runner, _ = _setup(12)
    assert other_runner.run(inputs) == expected
    with pytest.raises(ValueError, match="enrollment"):
        PopulationExecutor(
            runner.world, new_enrolled,
            seed=runner.seed, trial_id=runner.trial_id,
            state_field="phase", states=("new", "terminal", "inactive"),
        ).restore(snap)

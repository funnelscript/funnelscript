"""Independent bounded event-to-transaction verification (no production-derived oracle)."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import PopulationAgent, PopulationExecutor, WorldExecutor
from funnelscript.stdlib import marketing

SOURCE = Path(__file__).parent / "fixtures/population-reference/identity-rng.fnl"


def trial(size=10, trial_id="trial-1", order=None, duplicate=False, until=None):
    agents = [
        PopulationAgent(f"agent-{i:04}", f"cohort-{i // 10:03}", "north" if i % 10 < 4 else "south")
        for i in range(size)
    ]
    runner = PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)), agents if order is None else [agents[i] for i in order],
        seed=11, trial_id=trial_id, state_field="phase",
        states=("new", "terminal", "inactive"),
    )
    events = {
        a.agent_id: (Event(1, "Visitor.Tick"), Event(1, "Visitor.Tick"))
        if duplicate and i == 0 else (Event(1, "Visitor.Tick"),)
        for i, a in enumerate(agents) if i % 10 in (0, 4, 5)
    }
    return runner.run(events, until=until, trace=True)


def policy():
    return marketing.DeclaredSalePolicy(
        event_name="Visitor.Tick", state_field="phase",
        from_state="new", to_state="terminal",
        amount=D("20.00"), currency="SAR", attribution_label="synthetic-campaign",
    )


def test_world_population_exposes_actual_per_event_state_transition_evidence():
    result = trial()
    assert set(result.steps) == set(result.results)
    witness = result.steps["agent-0000"][0]
    assert witness.occurrence_index == 0
    assert witness.event == Event(1, "Visitor.Tick")
    assert witness.owner == "Visitor"
    assert witness.before["phase"] == "new"
    assert witness.after["phase"] == "terminal"
    assert witness.guard_matched
    assert len(result.partitions["terminal"]) == 3


def test_event_sale_recognition_has_a_real_execution_provenance_witness():
    result = trial(duplicate=True)
    recognize = getattr(marketing, "recognize_sales", None)
    assert callable(recognize), "Domain event-to-sale integration is not implemented"
    sales = recognize(result, policy())
    assert len(sales) == 3
    assert len(set(s.entry.tx_id for s in sales)) == 3
    assert {s.provenance.agent_id for s in sales} == {"agent-0000", "agent-0004", "agent-0005"}
    assert all(s.provenance.operation == "sale" and s.entry.kind == "sale" for s in sales)


def journal(sales, trial_id="trial-1", size=10):
    return (
        marketing.LedgerEntry(trial_id, "ad-1", "ad_spend", 0, D(size * 2), "SAR"),
        marketing.LedgerEntry(trial_id, "cost-1", "other_cost", 0, D(size) / 2, "SAR"),
        *(
            marketing.LedgerEntry(
                trial_id, f"payment-{i:04}", "settlement", 3, D("10.00"),
                "SAR", sale.entry.tx_id,
            ) for i, sale in enumerate(sales)
        ),
    )


def posting(result, sales, entries=None, size=10, horizon=3):
    return marketing.post_provenanced_trial(
        result, sales, policy(),
        external_entries=journal(sales, result.trial_id, size) if entries is None else entries,
        cash_initial=D(size * 10), settlement_delay=2, horizon=horizon,
    )


def test_hand_calculated_cash_and_receivable_oracle_before_and_after_settlement():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    linked = posting(result, sales)
    early = linked.ledger.evaluate(until=1)
    late = linked.ledger.evaluate()
    assert (early.cash, early.receivables, early.recognized_revenue, early.settled_receipts) == (
        D("75.00"), D("60.00"), D("60.00"), D("0.00"))
    assert (late.cash, late.receivables, late.recognized_revenue, late.settled_receipts) == (
        D("105.00"), D("30.00"), D("60.00"), D("30.00"))
    assert (late.paid_ad_spend, late.paid_other_costs, late.profit) == (
        D("20.00"), D("5.00"), D("35.00"))
    metrics = marketing.evaluate_trial(
        result, late, converted_state="terminal", attribution_label="synthetic-campaign",
        insolvency_threshold=D("0.00"),
    )
    assert metrics.converted_count == 3
    assert metrics.conversion_rate == D("0.3")
    assert metrics.cac == D(20) / D(3)
    assert metrics.roas == D(3)
    assert metrics.profit == D(35)
    assert metrics.ruined is False


def test_retry_is_idempotent_but_conflicting_duplicate_is_rejected():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    assert posting(result, sales + sales).ledger.evaluate().recognized_revenue == D(60)
    conflicting = replace(sales[0], entry=replace(sales[0].entry, amount=D(99)))
    with pytest.raises(ValueError, match="conflicting"):
        posting(result, sales + (conflicting,))


@pytest.mark.parametrize("tamper", [
    lambda s: replace(s, provenance=replace(s.provenance, trial_id="another-trial")),
    lambda s: replace(s, provenance=replace(s.provenance, agent_id="unknown")),
    lambda s: replace(s, provenance=replace(s.provenance, event_name="Visitor.Deactivate")),
    lambda s: replace(s, entry=replace(s.entry, currency="USD")),
    lambda s: replace(s, provenance=replace(s.provenance, occurrence_index=8)),
])
def test_rejects_forged_or_inconsistent_causal_records(tamper):
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    with pytest.raises(ValueError):
        posting(result, (tamper(sales[0]), *sales[1:]))


def test_missing_origin_or_untraced_population_is_rejected():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    with pytest.raises(ValueError, match="missing"):
        posting(result, sales[1:])
    with pytest.raises(ValueError, match="trace"):
        marketing.recognize_sales(replace(result, steps={}), policy())


def test_settlement_cross_trial_out_of_horizon_and_overpayment_rejected():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    base = journal(sales)
    with pytest.raises(ValueError):
        posting(result, sales, (*base, marketing.LedgerEntry(
            "trial-1", "bad", "settlement", 3, D(1), "SAR", "unmatched-sale")))
    with pytest.raises(ValueError):
        posting(result, sales, (*base, marketing.LedgerEntry(
            "other-trial", "bad", "other_cost", 2, D(1), "SAR")))
    with pytest.raises(ValueError):
        posting(result, sales, base, horizon=1)
    with pytest.raises(ValueError):
        posting(result, sales, (*base, marketing.LedgerEntry(
            "trial-1", "bad", "settlement", 3, D(11), "SAR", sales[0].entry.tx_id)))


@pytest.mark.parametrize("size", [10, 100, 1000])
@pytest.mark.parametrize("trial_id", ["trial-1", "trial-2"])
def test_integrated_cohort_invariance_and_accounting_at_scale(size, trial_id):
    first = trial(size, trial_id)
    opposite = trial(size, trial_id, order=list(reversed(range(size))))
    expected = marketing.recognize_sales(first, policy())
    reordered = marketing.recognize_sales(opposite, policy())
    assert expected == reordered
    linked = posting(first, expected, size=size)
    snapshot = linked.ledger.evaluate()
    assert len(expected) == 3 * size // 10
    assert len(first.segments["north"]) == 4 * size // 10
    assert snapshot.cash == D(size) * D("10.5")
    assert snapshot.receivables == D(size) * D(3)
    assert snapshot.profit == D(size) * D("3.5")
    assert len(set().union(*first.partitions.values())) == size


def test_independent_transaction_identity_golden_fixture():
    import json
    fixture = json.loads((SOURCE.parent / "transaction-provenance.json").read_text())
    sales = marketing.recognize_sales(trial(), policy())
    assert {s.provenance.agent_id: s.entry.tx_id for s in sales} == fixture["transaction_ids"]
    assert {s.provenance.event_digest for s in sales} == {fixture["event_digest"]}


def test_opt_in_world_trace_is_observational_for_rng_and_event_calendar():
    world = WorldExecutor(Parser.from_file(SOURCE))
    events = (Event(1, "Visitor.Tick"), Event(1, "Visitor.Tick"))
    baseline = world.run(events, seed=42)
    steps = []
    observed = world.run(events, seed=42, trace=steps)
    assert observed == baseline
    assert len(steps) == 2
    assert steps[0].before["phase"] == "new"
    assert steps[1].before["phase"] == "terminal"
    assert steps[0].after["draw"] != steps[1].after["draw"]
    with pytest.raises(ValueError, match="trace sink"):
        world.run(events, seed=42, trace=steps)


def test_emitted_events_have_real_processing_occurrence_and_guard_witness():
    fixture = SOURCE.parents[3] / "examples" / "guarded_world.fnl"
    world = WorldExecutor(Parser.from_file(fixture))
    steps = []
    baseline = world.run((Event(0, "Counter.Tick"),), seed=5)
    observed = world.run((Event(0, "Counter.Tick"),), seed=5, trace=steps)
    assert observed == baseline
    assert [step.occurrence_index for step in steps] == [0, 1, 2, 3]
    assert [step.event.time for step in steps] == [0, 1, 2, 3]
    assert [step.guard_matched for step in steps] == [True, True, True, False]
    assert [step.after["value"] for step in steps] == [1, 2, 3, 3]


def test_missing_or_inconsistent_event_trace_is_rejected():
    original = trial()
    aid = "agent-0000"
    with pytest.raises(ValueError, match="inconsistent"):
        marketing.recognize_sales(replace(original, steps={
            **original.steps,
            aid: (replace(original.steps[aid][0], occurrence_index=3),),
        }), policy())
    with pytest.raises(ValueError, match="match final"):
        marketing.recognize_sales(replace(original, steps={
            **original.steps,
            aid: (replace(original.steps[aid][0], after={"phase": "new", "draw": 0.0}),),
        }), policy())


def test_external_sale_without_provenance_and_premature_settlement_rejected():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    with pytest.raises(ValueError, match="sales must be linked"):
        posting(result, sales, (*journal(sales), marketing.LedgerEntry(
            "trial-1", "manual-sale", "sale", 1, D("1.00"), "SAR")))
    premature = marketing.LedgerEntry(
        "trial-1", "early-payment", "settlement", 1, D("5.00"), "SAR", sales[0].entry.tx_id)
    with pytest.raises(ValueError, match="settlement before"):
        posting(result, sales, (*journal(sales), premature))


def test_policy_validation_and_fractional_event_time():
    with pytest.raises(ValueError):
        marketing.DeclaredSalePolicy("Visitor.Tick", "phase", "new", "terminal",
                                     D("0.001"), "SAR", "x")
    with pytest.raises(ValueError):
        marketing.DeclaredSalePolicy("Visitor.Tick", "phase", "new", "terminal",
                                     D(20), "US", "x")
    runner = PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)),
        [PopulationAgent("a-1", "c-1", "north")],
        seed=11, trial_id="trial-1", state_field="phase",
        states=("new", "terminal", "inactive"),
    )
    result = runner.run({"a-1": (Event(0.5, "Visitor.Tick"),)}, trace=True)
    with pytest.raises(ValueError, match="integer simulation day"):
        marketing.recognize_sales(result, policy())


def test_outside_execution_horizon_does_not_create_earlier_sale():
    result = trial(until=0)
    assert not marketing.recognize_sales(result, policy())
    assert all(not run.processed for run in result.results.values())
    assert all(run.pending for aid, run in result.results.items() if aid in {
        "agent-0000", "agent-0004", "agent-0005"})


def test_same_day_manual_costs_order_before_event_sales():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    same_day = (
        marketing.LedgerEntry("trial-1", "z-ads", "ad_spend", 1, D(20), "SAR"),
        marketing.LedgerEntry("trial-1", "a-other", "other_cost", 1, D(5), "SAR"),
    )
    linked = posting(result, sales, same_day, horizon=1)
    assert [e.tx_id for e in linked.ledger.entries[:2]] == ["a-other", "z-ads"]
    assert all(e.kind == "sale" for e in linked.ledger.entries[2:])
    assert linked.ledger.evaluate().cash == D(75)
    assert linked.ledger.evaluate().receivables == D(60)


def test_unrelated_agent_enrollment_does_not_change_original_sale_identity():
    ten = marketing.recognize_sales(trial(10), policy())
    hundred = marketing.recognize_sales(trial(100), policy())
    assert {s.entry for s in ten}.issubset({s.entry for s in hundred})
    assert {s.provenance for s in ten}.issubset({s.provenance for s in hundred})


def test_conflicting_external_entries_and_invalid_money_rejected():
    result = trial()
    sales = marketing.recognize_sales(result, policy())
    spent = marketing.LedgerEntry("trial-1", "ads", "ad_spend", 0, D(1), "SAR")
    with pytest.raises(ValueError, match="duplicate"):
        posting(result, sales, (spent, spent))
    for amount in (D("-1.00"), D("NaN"), D("0")):
        with pytest.raises(ValueError):
            marketing.DeclaredSalePolicy(
                "Visitor.Tick", "phase", "new", "terminal", amount, "SAR", "a")


def test_actual_false_guard_never_recognizes_a_sale():
    source = SOURCE.parent / "guarded-provenance.fnl"
    runner = PopulationExecutor(
        WorldExecutor(Parser.from_file(source)),
        [PopulationAgent("a-1", "c-1", "north")],
        seed=11, trial_id="trial-1", state_field="phase",
        states=("new", "terminal"),
    )
    result = runner.run({"a-1": (Event(1, "Visitor.Tick"),)}, trace=True)
    assert not result.steps["a-1"][0].guard_matched
    assert result.steps["a-1"][0].before == result.steps["a-1"][0].after
    assert marketing.recognize_sales(result, policy()) == ()

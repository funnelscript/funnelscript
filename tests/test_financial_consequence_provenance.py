"""Phase 007D independent domain envelope and exact financial reference checks."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from funnelscript.stdlib import marketing
from test_transaction_provenance import trial, policy


def operation(tx, kind, day, amount, *, source=None, trial_id="trial-1", currency="SAR",
              actor="campaign-finance", authorization=None):
    entry = marketing.LedgerEntry(trial_id, tx, kind, day, D(str(amount)), currency, source)
    return marketing.DeclaredFinancialAction(entry, actor, authorization or f"permit-{tx}")


def scenario(*, writeoff=False):
    pop = trial()
    sales = marketing.recognize_sales(pop, policy())
    actions = [
        operation("ads", "ad_spend", 0, "20.00"),
        operation("ops", "other_cost", 0, "5.00"),
    ]
    actions.extend(operation(f"receipt-{i}", "settlement", 3, "10.00",
                             source=s.entry.tx_id) for i, s in enumerate(sales))
    if writeoff:
        actions.append(operation("loss", "writeoff", 3, "5.00", source=sales[0].entry.tx_id))
    return pop, sales, tuple(actions)


def post(pop, sales, actions, horizon=3):
    return marketing.post_authorized_trial(
        pop, sales, policy(), actions=actions,
        cash_initial=D("100.00"), settlement_delay=2, horizon=horizon,
    )


def test_complete_financial_provenance_adapter_is_public_and_auditable():
    adapter = getattr(marketing, "post_authorized_trial", None)
    assert callable(adapter), "Financial action provenance and exactly-once adapter is missing"
    pop, sales, actions = scenario()
    result = adapter(pop, sales, policy(), actions=actions, cash_initial=D(100),
                     settlement_delay=2, horizon=3)
    assert result.financial_actions == actions
    assert {a.entry.kind for a in result.financial_actions} == {
        "ad_spend", "other_cost", "settlement"}
    assert all(a.actor_id == "campaign-finance" for a in result.financial_actions)


def test_independent_original_oracle_and_writeoff_variant():
    pop, sales, actions = scenario()
    linked = post(pop, sales, actions)
    first, last = linked.ledger.evaluate(until=1), linked.ledger.evaluate()
    assert (first.cash, first.receivables, first.recognized_revenue, first.settled_receipts) == (
        D(75), D(60), D(60), D(0))
    assert (last.cash, last.receivables, last.recognized_revenue, last.settled_receipts,
            last.profit, last.writeoffs) == (D(105), D(30), D(60), D(30), D(35), D(0))
    metrics = marketing.evaluate_trial(pop, last, converted_state="terminal",
        attribution_label="synthetic-campaign", insolvency_threshold=D(0))
    assert (metrics.converted_count, metrics.conversion_rate, metrics.cac,
            metrics.roas, metrics.ruined) == (3, D("0.3"), D(20) / D(3), D(3), False)
    pop, sales, actions = scenario(writeoff=True)
    written = post(pop, sales, actions).ledger.evaluate()
    assert (written.cash, written.receivables, written.recognized_revenue,
            written.settled_receipts, written.writeoffs, written.profit) == (
        D(105), D(25), D(60), D(30), D(5), D(30))


def test_identical_replay_collapses_without_mutating_authored_actions():
    pop, sales, actions = scenario(writeoff=True)
    original = tuple(actions)
    replay = post(pop, sales, (*actions, actions[2], actions[-1], actions[0]))
    once = post(pop, sales, actions)
    assert replay.ledger == once.ledger
    assert replay.financial_actions == once.financial_actions
    assert tuple(actions) == original
    assert len(replay.financial_actions) == 6
    assert len(replay.ledger.entries) == 9


@pytest.mark.parametrize("change", [
    lambda a: replace(a, entry=replace(a.entry, amount=D("11.00"))),
    lambda a: replace(a, actor_id="attacker"),
    lambda a: replace(a, authorization_id="other-permit"),
    lambda a: replace(a, entry=replace(a.entry, kind="writeoff")),
])
def test_conflicting_duplicate_delivery_rejected(change):
    pop, sales, actions = scenario()
    with pytest.raises(ValueError, match="conflicting"):
        post(pop, sales, (*actions, change(actions[2])))


def test_authorization_id_cannot_authorize_two_distinct_operations():
    pop, sales, actions = scenario()
    reused = replace(actions[3], authorization_id=actions[2].authorization_id)
    with pytest.raises(ValueError, match="authorization"):
        post(pop, sales, (*actions[:3], reused, *actions[4:]))


@pytest.mark.parametrize("replacement", [
    lambda a, s: replace(a, entry=replace(a.entry, source_tx_id="unknown-sale")),
    lambda a, s: replace(a, entry=replace(a.entry, source_tx_id=s[0].entry.tx_id + "-foreign")),
    lambda a, s: replace(a, entry=replace(a.entry, trial_id="another-trial")),
    lambda a, s: replace(a, entry=replace(a.entry, currency="USD")),
    lambda a, s: replace(a, entry=replace(a.entry, day=1)),
    lambda a, s: replace(a, entry=replace(a.entry, amount=D("25.00"))),
])
def test_invalid_settlement_reference_scope_delay_or_balance_rejected(replacement):
    pop, sales, actions = scenario()
    with pytest.raises(ValueError):
        post(pop, sales, (*actions[:2], replacement(actions[2], sales), *actions[3:]))


def test_writeoff_balance_and_foreign_sale_reference_rejected():
    pop, sales, actions = scenario()
    with pytest.raises(ValueError):
        post(pop, sales, (*actions, operation("loss", "writeoff", 3, 15,
                                           source=sales[0].entry.tx_id)))
    with pytest.raises(ValueError):
        post(pop, sales, (*actions, operation("loss", "writeoff", 3, 1,
                                           source="sale-from-another-trial")))


def test_missing_or_invalid_authorization_and_invented_world_sale_rejected():
    pop, sales, actions = scenario()
    for actor, permit in (("", "permit"), ("campaign-finance", ""), ("campaign finance", "ok")):
        with pytest.raises(ValueError):
            marketing.DeclaredFinancialAction(actions[0].entry, actor, permit)
    with pytest.raises((ValueError, TypeError)):
        marketing.DeclaredFinancialAction(actions[0].entry, "x", None)
    with pytest.raises(ValueError):
        marketing.DeclaredFinancialAction(sales[0].entry, "finance", "pretend-world")
    with pytest.raises(TypeError):
        post(pop, sales, (*actions, actions[0].entry))


def test_horizon_transaction_collision_and_wrong_external_trial_rejected():
    pop, sales, actions = scenario()
    with pytest.raises(ValueError, match="horizon"):
        post(pop, sales, actions, horizon=1)
    with pytest.raises(ValueError):
        post(pop, sales, (*actions, operation("future", "other_cost", 4, 1)))
    with pytest.raises(ValueError):
        post(pop, sales, (*actions, operation(sales[0].entry.tx_id, "other_cost", 2, 1)))
    with pytest.raises(ValueError):
        post(pop, sales, (*actions, operation("foreign", "ad_spend", 0, 1,
                                          trial_id="another-trial")))


def test_reordered_external_enrollment_and_replay_produce_identical_finances():
    pop, sales, actions = scenario(writeoff=True)
    left = post(pop, sales, actions)
    right = post(trial(order=list(reversed(range(10)))),
                 marketing.recognize_sales(trial(), policy()), tuple(reversed(actions)))
    assert left.ledger == right.ledger
    assert left.financial_actions == right.financial_actions


def test_legacy_raw_ledger_adapter_contract_is_unchanged():
    pop, sales, actions = scenario()
    old = marketing.post_provenanced_trial(pop, sales, policy(),
        external_entries=tuple(a.entry for a in actions), cash_initial=D(100),
        settlement_delay=2, horizon=3)
    assert old.ledger.evaluate().cash == D(105)
    assert old.financial_actions == ()


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "0", "0.001"])
def test_external_financial_amounts_must_be_positive_finite_minor_units(amount):
    with pytest.raises(ValueError):
        operation("bad", "ad_spend", 0, amount)


@pytest.mark.parametrize("day", [-1, 0.5, float("inf"), float("nan")])
def test_financial_dates_reject_non_integral_negative_or_nonfinite_values(day):
    with pytest.raises(ValueError):
        operation("bad", "other_cost", day, 1)


def test_same_day_policy_orders_explicit_settlement_after_source_recognition():
    pop, sales, actions = scenario()
    instant = operation("instant", "settlement", 1, "4.00", source=sales[0].entry.tx_id)
    posted = marketing.post_authorized_trial(pop, sales, policy(),
        actions=(actions[0], actions[1], instant), cash_initial=D(100),
        settlement_delay=0, horizon=1)
    assert [e.kind for e in posted.ledger.entries] == [
        "ad_spend", "other_cost", "sale", "sale", "sale", "settlement"]
    snap = posted.ledger.evaluate()
    assert (snap.cash, snap.receivables, snap.profit) == (D(79), D(56), D(35))


def test_prior_day_writeoff_cannot_reference_future_recognition():
    pop, sales, actions = scenario()
    loss = operation("bad-loss", "writeoff", 0, "1.00", source=sales[0].entry.tx_id)
    with pytest.raises(ValueError, match="existing sale"):
        post(pop, sales, (*actions, loss))


def test_remaining_receivable_after_writeoff_cannot_be_settled_twice():
    pop, sales, actions = scenario(writeoff=True)
    second = operation("exhaust", "settlement", 3, "6.00", source=sales[0].entry.tx_id)
    with pytest.raises(ValueError, match="outstanding"):
        post(pop, sales, (*actions, second))


def test_unauthorized_event_forgery_is_rejected_under_strict_mode():
    pop, sales, actions = scenario()
    forged = replace(sales[0], provenance=replace(sales[0].provenance, agent_id="fake"))
    with pytest.raises(ValueError, match="provenance"):
        post(pop, (forged, *sales[1:]), actions)


def test_missing_or_incomplete_execution_trace_cannot_claim_financial_sales():
    pop, sales, actions = scenario()
    with pytest.raises(ValueError, match="trace"):
        post(replace(pop, steps={}), sales, actions)
    with pytest.raises(ValueError):
        post(replace(pop, steps={**pop.steps, "agent-0000": ()}), sales, actions)


def test_shared_budget_is_an_explicit_counterexample_not_independent_world_evidence():
    """Conceptual order-sensitive budget counterexample; not an implemented World scheduler."""
    def winners(enrollment):
        remaining = D(10)
        allocated = []
        for agent in enrollment:
            if remaining >= D(10):
                remaining -= D(10)
                allocated.append(agent)
        return tuple(allocated)

    assert winners(("agent-a", "agent-b")) == ("agent-a",)
    assert winners(("agent-b", "agent-a")) == ("agent-b",)
    assert winners(("agent-a", "agent-b")) == winners(("agent-a", "agent-b"))

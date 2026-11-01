"""Phase 007B domain-ledger reconciliation independent golden: P-LEDGER-1."""

import importlib
import json
from decimal import Decimal
from pathlib import Path

marketing = importlib.import_module("funnelscript.stdlib.marketing")
REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/population-reference/financial-ledger.json")
    .read_text(encoding="utf-8")
)


def test_delayed_settlement_does_not_increase_cash_at_sale_recognition():
    ledger_type = getattr(marketing, "MarketingLedger", None)
    entry_type = getattr(marketing, "LedgerEntry", None)
    assert callable(ledger_type) and callable(entry_type), "Missing opt-in marketing ledger API"

    events = tuple(
        entry_type(
            trial_id=e["trial_id"], tx_id=e["tx_id"], kind=e["kind"],
            day=e["day"], amount=Decimal(e["amount"]), currency=e["currency"],
            source_tx_id=e["source_tx_id"],
        )
        for e in REFERENCE["journal"]
    )
    ledger = ledger_type(
        trial_id="trial-1", currency="SAR", cash_initial=Decimal("100.00"),
        horizon=3, settlement_delay=2, entries=events,
    )
    early = ledger.evaluate(until=1)
    final = ledger.evaluate()
    assert early.cash == Decimal("75.00")
    assert early.receivables == Decimal("60.00")
    assert early.recognized_revenue == Decimal("60.00")
    assert early.settled_receipts == Decimal("0.00")
    assert final.cash == Decimal("105.00")
    assert final.receivables == Decimal("30.00")
    assert final.settled_receipts == Decimal("30.00")
    assert final.paid_ad_spend == Decimal("20.00")
    assert final.paid_other_costs == Decimal("5.00")
    assert final.profit == Decimal("35.00")
    assert ledger.evaluate() == final


import pytest


def make_entry(kind, amount, *, tx="tx", day=0, source=None, trial="trial-1", currency="SAR"):
    return marketing.LedgerEntry(
        trial, tx, kind, day, amount, currency, source
    )


def make_ledger(entries, *, cash="100.00", until=4, delay=2, trial="trial-1"):
    return marketing.MarketingLedger(
        trial, "SAR", Decimal(cash), until, delay, tuple(entries)
    )


def test_no_automatic_receipt_and_future_event_excluded_from_horizon():
    sale = make_entry("sale", Decimal("10.00"), tx="s", day=1)
    payment = make_entry("settlement", Decimal("10.00"), tx="p", day=3, source="s")
    ledger = make_ledger((sale, payment))
    assert ledger.evaluate(until=2).cash == Decimal("100.00")
    assert ledger.evaluate(until=2).receivables == Decimal("10.00")
    assert ledger.evaluate(until=3).cash == Decimal("110.00")
    assert ledger.evaluate(until=3).receivables == Decimal("0.00")
    assert ledger.evaluate(until=3).open_receivables == ()
    assert ledger.evaluate(until=0).recognized_revenue == Decimal("0.00")


def test_partial_settlement_and_writeoff_conserve_receivables_and_profits():
    ledger = make_ledger((
        make_entry("sale", Decimal("50.00"), tx="sale-1", day=0),
        make_entry("writeoff", Decimal("15.00"), tx="writeoff-1", day=1, source="sale-1"),
        make_entry("settlement", Decimal("10.00"), tx="payment-1", day=2, source="sale-1"),
    ))
    output = ledger.evaluate()
    assert output.cash == Decimal("110.00")
    assert output.recognized_revenue == Decimal("50.00")
    assert output.writeoffs == Decimal("15.00")
    assert output.settled_receipts == Decimal("10.00")
    assert output.receivables == Decimal("25.00")
    assert output.profit == Decimal("35.00")
    assert output.open_receivables == (("sale-1", Decimal("25.00")),)
    assert len(output.checkpoints) == 4


@pytest.mark.parametrize(
    "entries,expected",
    [
        ((make_entry("settlement", Decimal("1.00"), tx="bad", source="absent"),), "existing sale"),
        ((make_entry("sale", Decimal("10.00"), tx="s"), make_entry("settlement", Decimal("1.00"), tx="p", day=1, source="s")), "minimum delay"),
        ((make_entry("sale", Decimal("10.00"), tx="s"), make_entry("settlement", Decimal("11.00"), tx="p", day=2, source="s")), "exceeds outstanding"),
        ((make_entry("sale", Decimal("10.00"), tx="s"), make_entry("writeoff", Decimal("11.00"), tx="w", day=2, source="s")), "exceeds outstanding"),
        ((make_entry("sale", Decimal("10.00"), tx="s"), make_entry("sale", Decimal("10.00"), tx="s", day=1)), "duplicate transaction"),
        ((make_entry("sale", Decimal("10.00"), tx="s", day=3), make_entry("ad_spend", Decimal("1.00"), tx="a", day=2)), "nondecreasing"),
        ((make_entry("sale", Decimal("1.00"), tx="s", trial="other"),), "trial or currency"),
        ((make_entry("sale", Decimal("1.00"), tx="s", currency="USD"),), "trial or currency"),
    ],
)
def test_invalid_journal_rejected(entries, expected):
    with pytest.raises(ValueError, match=expected):
        make_ledger(entries).evaluate()


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("0.001"), Decimal("0.00"), Decimal("-1.00"), 1.00, "1.00"])
def test_invalid_or_nonpositive_money_entry_rejected(value):
    with pytest.raises(ValueError, match="amount"):
        make_entry("sale", value)


@pytest.mark.parametrize("kind,source", [
    ("settlement", None), ("writeoff", ""), ("sale", "existing"), ("ad_spend", "source"),
])
def test_invalid_reference_shape_rejected(kind, source):
    with pytest.raises(ValueError, match="source_tx_id|only settlement"):
        make_entry(kind, Decimal("1.00"), source=source)


@pytest.mark.parametrize("value,field", [
    ("", "trial_id"), ("trial with space", "trial_id"),
])
def test_invalid_trial_identity_rejected(value, field):
    with pytest.raises(ValueError, match=field):
        make_entry("sale", Decimal("1.00"), trial=value)


@pytest.mark.parametrize("bad_day", [-1, 1.5, True])
def test_invalid_day_rejected(bad_day):
    with pytest.raises(ValueError, match="day"):
        make_entry("sale", Decimal("1.00"), day=bad_day)


def test_negative_cash_allowed_as_model_policy_and_strict_ruin_boundary():
    ledger = make_ledger(
        (make_entry("ad_spend", Decimal("120.00"), tx="spend"),),
        cash="100.00",
    )
    snapshot = ledger.evaluate()
    assert snapshot.cash == Decimal("-20.00")
    assert snapshot.min_cash == Decimal("-20.00")
    assert snapshot.checkpoints[0][2] == Decimal("100.00")
    assert snapshot.checkpoints[-1][2] == Decimal("-20.00")


@pytest.mark.parametrize("bad", [-1, True, 1.5])
def test_invalid_ledger_horizon_or_delay_rejected(bad):
    with pytest.raises(ValueError):
        make_ledger((), until=bad)
    with pytest.raises(ValueError):
        marketing.MarketingLedger("trial-1", "SAR", Decimal("100.00"), 4, bad, ())


def test_replayable_journal_rejects_mutable_list_or_invalid_until():
    with pytest.raises(TypeError, match="tuple"):
        marketing.MarketingLedger("trial-1", "SAR", Decimal("0.00"), 4, 0, [])
    ledger = make_ledger(())
    with pytest.raises(ValueError, match="until"):
        ledger.evaluate(until=5)
    with pytest.raises(ValueError, match="until"):
        ledger.evaluate(until=True)


def test_decimal_context_precision_cannot_silently_round_posted_minor_units():
    from decimal import localcontext
    ledger = make_ledger(
        (make_entry("sale", Decimal("1234567.89"), tx="sale-large"),),
        cash="100.00",
    )
    with localcontext() as ctx:
        ctx.prec = 5
        output = ledger.evaluate()
    assert output.recognized_revenue == Decimal("1234567.89")
    assert output.receivables == Decimal("1234567.89")
    assert output.cash == Decimal("100.00")

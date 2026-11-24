"""Verification tests for Canonical Ingestion Models and SQLite WAL Staging Buffer.

Validates:
1. Pydantic validation of CanonicalAdSpendRecord, CanonicalConversionEvent, CanonicalSettlementEvent.
2. Minor-unit integer cents arithmetic, ISO 4217 currency checks, YYYY-MM-DD date validation.
3. Deterministic SHA-256 payload hashing and idempotency key computation.
4. SQLite WAL staging buffer: atomic insert, deduplication on duplicate replay, DLQ routing.
5. Direct draining into FinancialLedger with continuous double-entry trial balance verification.
"""

from pathlib import Path

import pytest

from funnelscript.connectors.models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
    IngestionBatch,
    RestatementDelta,
)
from funnelscript.connectors.staging import SQLiteStagingBuffer
from funnelscript.ledger import FinancialLedger


def test_canonical_ad_spend_record_validation():
    rec = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_12345",
        campaign_id="camp_999",
        campaign_name="Black Friday Scale",
        date="2026-11-20",
        spend_cents=50000,  # $500.00
        currency="USD",
        impressions=25000,
        clicks=1000,
        actions={"purchase": 25, "lead": 100},
        action_values_cents={"purchase": 250000},
    )

    assert rec.spend_dollars == 500.00
    assert pytest.approx(rec.cpc, rel=1e-3) == 0.50
    assert pytest.approx(rec.ctr, rel=1e-3) == 0.04
    assert pytest.approx(rec.cpm, rel=1e-3) == 20.00
    assert rec.idempotency_key == "meta:act_12345:camp_999:all:2026-11-20"
    assert len(rec.raw_payload_sha256) == 64


def test_canonical_models_reject_invalid_currency_and_date():
    with pytest.raises(ValueError, match="Invalid ISO 4217 currency code"):
        CanonicalAdSpendRecord(
            platform="meta",
            account_id="act_1",
            campaign_id="c_1",
            campaign_name="Test",
            date="2026-11-20",
            spend_cents=100,
            currency="INVALID_CURRENCY",
            impressions=100,
            clicks=10,
        )

    with pytest.raises(ValueError, match="Invalid date format"):
        CanonicalAdSpendRecord(
            platform="meta",
            account_id="act_1",
            campaign_id="c_1",
            campaign_name="Test",
            date="20-11-2026",  # wrong format
            spend_cents=100,
            currency="USD",
            impressions=100,
            clicks=10,
        )


def test_canonical_conversion_event_properties():
    conv = CanonicalConversionEvent(
        platform="ga4",
        external_id="ord_888",
        event_name="Purchase",
        event_time="2026-11-20T14:30:00Z",
        revenue_cents=12550,  # $125.50
        currency="EUR",
        customer_id="cust_42",
        channel="google_search",
    )

    assert conv.revenue_dollars == 125.50
    assert conv.idempotency_key == "ga4:Purchase:ord_888"
    assert len(conv.raw_payload_sha256) == 64


def test_canonical_settlement_event_properties():
    stl = CanonicalSettlementEvent(
        gateway="stripe",
        settlement_id="stl_999",
        transaction_id="ch_123",
        gross_cents=10000,
        fee_cents=320,
        reserve_hold_cents=500,
        net_cash_cents=9180,
        currency="USD",
        settlement_time="2026-11-23T00:00:00Z",
        status="settled",
    )

    assert stl.gross_dollars == 100.00
    assert stl.fee_dollars == 3.20
    assert stl.net_cash_dollars == 91.80
    assert stl.idempotency_key == "stripe:settled:stl_999:ch_123"


def test_restatement_delta_audit_hash():
    delta = RestatementDelta(
        platform="meta",
        campaign_id="camp_1",
        date="2026-11-15",
        metric_name="conversions",
        original_value=10.0,
        restated_value=14.0,
        delta_value=4.0,
        as_of_time="2026-11-22T10:00:00Z",
    )

    assert delta.delta_value == 4.0
    assert len(delta.audit_hash) == 64
    assert delta.idempotency_key.startswith("delta:meta:camp_1:2026-11-15:conversions:")


def test_ingestion_batch_aggregation():
    rec1 = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_1",
        campaign_id="c_1",
        campaign_name="Test",
        date="2026-11-20",
        spend_cents=1000,
        impressions=100,
        clicks=10,
    )
    rec2 = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_1",
        campaign_id="c_2",
        campaign_name="Test 2",
        date="2026-11-20",
        spend_cents=2000,
        impressions=200,
        clicks=20,
    )

    batch = IngestionBatch(
        batch_id="batch_001",
        source_platform="meta",
        ingested_at="2026-11-20T23:59:59Z",
        ad_spend_records=[rec1, rec2],
    )

    assert batch.total_records == 2
    assert len(batch.raw_batch_sha256) == 64


def test_sqlite_staging_buffer_wal_mode_and_idempotency(tmp_path: Path):
    db_file = tmp_path / "staging_test.db"
    buffer = SQLiteStagingBuffer(db_file)

    rec = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_1",
        campaign_id="camp_10",
        campaign_name="Retargeting",
        date="2026-11-21",
        spend_cents=15000,
        impressions=5000,
        clicks=250,
    )

    # First insert succeeds
    assert buffer.enqueue(rec) is True

    # Duplicate insert returns False (idempotent no-op)
    assert buffer.enqueue(rec) is False

    counts = buffer.count_staging()
    assert counts["pending"] == 1
    assert counts["processed"] == 0

    pending = buffer.get_pending()
    assert len(pending) == 1
    assert pending[0]["idempotency_key"] == rec.idempotency_key

    # Mark processed
    buffer.mark_processed(rec.idempotency_key)
    counts_after = buffer.count_staging()
    assert counts_after["pending"] == 0
    assert counts_after["processed"] == 1
    buffer.close()


def test_sqlite_staging_dlq_routing_and_reprocessing(tmp_path: Path):
    buffer = SQLiteStagingBuffer(tmp_path / "staging_dlq.db")

    raw_corrupted = "{not: valid, json: here"
    dlq_id = buffer.route_to_dlq(
        platform="shopify",
        raw_payload=raw_corrupted,
        error_code="JSON_DECODE_ERROR",
        error_message="Expecting property name enclosed in double quotes",
    )

    assert dlq_id.startswith("dlq_")
    assert buffer.count_dlq() == 1

    dlq_items = buffer.list_dlq(resolved=False)
    assert len(dlq_items) == 1
    assert dlq_items[0]["dlq_id"] == dlq_id
    assert dlq_items[0]["error_code"] == "JSON_DECODE_ERROR"

    # Resolve DLQ record
    assert buffer.reprocess_dlq(dlq_id) is True
    assert buffer.count_dlq() == 0
    buffer.close()


def test_sqlite_staging_drain_to_ledger(tmp_path: Path):
    buffer = SQLiteStagingBuffer(tmp_path / "staging_drain.db")

    spend_rec = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_1",
        campaign_id="camp_drain",
        campaign_name="Drain Test",
        date="2026-11-22",
        spend_cents=25000,  # $250.00
        impressions=10000,
        clicks=500,
    )
    stl_rec = CanonicalSettlementEvent(
        gateway="stripe",
        settlement_id="stl_drain_1",
        transaction_id="tx_drain_1",
        gross_cents=100000,  # $1,000.00
        fee_cents=2900,      # $29.00
        reserve_hold_cents=5000,  # $50.00
        net_cash_cents=92100,     # $921.00
        currency="USD",
        settlement_time="2026-11-22T18:00:00Z",
        status="settled",
    )

    buffer.enqueue(spend_rec)
    buffer.enqueue(stl_rec)

    ledger = FinancialLedger()
    posted_count = buffer.drain_to_ledger(ledger)

    assert posted_count == 2
    assert buffer.count_staging()["pending"] == 0
    assert buffer.count_staging()["processed"] == 2

    # Verify ledger trial balance: continuous zero imbalance
    assert ledger.total_imbalance_cents("USD") == 0
    assert ledger.balance_cents("Bank_Cash") == 92100
    assert ledger.balance_cents("Ad_Spend_Expense") == 25000
    assert ledger.balance_cents("Merchant_Fees") == 2900
    assert ledger.balance_cents("Rolling_Reserve") == 5000
    assert ledger.balance_cents("Gross_Revenue") == -100000
    assert ledger.balance_cents("Ad_Spend_Payable") == -25000
    buffer.close()

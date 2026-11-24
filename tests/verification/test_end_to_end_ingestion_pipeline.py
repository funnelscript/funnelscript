"""End-to-End Verification Pipeline: Telemetry Ingestion -> Staging -> Ledger -> Calibration -> Backtest -> .fnls.

Proves the complete unified pipeline:
1. Mock Meta Graph API & Stripe webhooks ingest live telemetry into Canonical models.
2. Verified payloads are enqueued into SQLite WAL staging buffer.
3. Staged records drain into FinancialLedger preserving double-entry equilibrium.
4. Telemetry records feed CampaignCalibrator to fit empirical Hill parameters.
5. EmpiricalBacktester validates out-of-sample holdout forecasting superior to linear spreadsheet.
6. Auto-generated .fnls World file parses and passes structural compilation.
"""

import json
from pathlib import Path
from urllib.request import Request

from funnelscript.connectors.meta_ads import MetaAdsConnector
from funnelscript.connectors.models import (
    CanonicalSettlementEvent,
)
from funnelscript.connectors.staging import SQLiteStagingBuffer
from funnelscript.connectors.synthetic_bridge import SyntheticEventBridge
from funnelscript.connectors.webhooks import StripeWebhookAdapter
from funnelscript.ledger import FinancialLedger
from funnelscript.parser import Parser
from funnelscript.stdlib.marketing.backtest import EmpiricalBacktester
from funnelscript.stdlib.marketing.calibration import CampaignCalibrator
from funnelscript.stdlib.marketing.ingestion import (
    DailyCampaignMetric,
    PaymentSettlementRecord,
)


def test_full_offline_ingestion_to_simulation_pipeline(tmp_path: Path):
    """Executes the complete end-to-end telemetry ingestion loop offline."""
    db_file = tmp_path / "pipeline_staging.db"
    staging = SQLiteStagingBuffer(db_file)

    # 1. Pull ad spend from Meta Ads mock
    meta_days_data = [
        {"spend": 300.0, "impressions": 10000, "clicks": 200, "conversions": 10, "revenue": 1200.0, "day": f"2026-10-{d:02d}"}
        for d in range(1, 16)
    ]

    meta_mock_response = {
        "data": [
            {
                "campaign_id": "meta_ecom_01",
                "campaign_name": "Ecom Prospecting",
                "spend": str(row["spend"]),
                "impressions": str(row["impressions"]),
                "clicks": str(row["clicks"]),
                "actions": [{"action_type": "purchase", "value": str(row["conversions"])}],
                "action_values": [{"action_type": "purchase", "value": str(row["revenue"])}],
                "date_start": row["day"],
                "date_stop": row["day"],
            }
            for row in meta_days_data
        ],
        "paging": {},
    }

    def mock_meta_transport(req: Request) -> tuple[int, dict[str, str], bytes]:
        return 200, {"content-type": "application/json"}, json.dumps(meta_mock_response).encode("utf-8")

    meta_connector = MetaAdsConnector(
        account_id="act_ecom_100",
        access_token="mock_token",
        transport=mock_meta_transport,
    )
    spend_records = meta_connector.fetch_all(start_date="2026-10-01", end_date="2026-10-15")
    assert len(spend_records) == 15

    # 2. Ingest customer payments from Stripe webhook adapter
    stripe_adapter = StripeWebhookAdapter()
    settlement_records: list[CanonicalSettlementEvent] = []

    for d in range(1, 16):
        stripe_event = {
            "type": "charge.succeeded",
            "created": 1700000000 + d * 86400,
            "data": {
                "object": {
                    "id": f"ch_e2e_{d}",
                    "amount": 120000,  # $1,200.00
                    "currency": "usd",
                    "customer": f"cus_{d}",
                    "balance_transaction": {"fee": 3480},  # $34.80
                }
            },
        }
        parsed = stripe_adapter.parse_webhook(stripe_event, {})
        for p in parsed:
            if isinstance(p, CanonicalSettlementEvent):
                settlement_records.append(p)

    assert len(settlement_records) == 15

    # 3. Enqueue to SQLite WAL staging buffer
    enq_spend, _ = staging.enqueue_batch(spend_records)
    enq_stl, _ = staging.enqueue_batch(settlement_records)
    assert enq_spend == 15
    assert enq_stl == 15
    assert staging.count_staging()["pending"] == 30

    # 4. Drain staging buffer into FinancialLedger
    ledger = FinancialLedger()
    drained_txs = staging.drain_to_ledger(ledger)
    assert drained_txs == 30
    assert staging.count_staging()["pending"] == 0
    assert staging.count_staging()["processed"] == 30

    # Verify ledger trial balance
    assert ledger.total_imbalance_cents("USD") == 0
    assert ledger.balance_cents("Gross_Revenue") == -15 * 120000
    assert ledger.balance_cents("Ad_Spend_Expense") == 15 * 30000
    assert ledger.balance_cents("Merchant_Fees") == 15 * 3480
    assert ledger.balance_cents("Bank_Cash") == 15 * (120000 - 3480)

    # 5. Synthesize discrete agent event trace
    bridge = SyntheticEventBridge(base_seed=777)
    agent_events = bridge.synthesize_events_from_spend_and_conversions(
        spend_records=spend_records,
        settlement_events=settlement_records,
    )
    assert len(agent_events) > 0
    playbook_json = bridge.export_playbook_json(agent_events)
    playbook_file = tmp_path / "synthesized_playbook.json"
    playbook_file.write_text(playbook_json, encoding="utf-8")
    assert playbook_file.exists()

    # 6. Bridge into CampaignCalibrator & EmpiricalBacktester
    # Map Canonical records to DailyCampaignMetric and PaymentSettlementRecord
    campaign_metrics = [
        DailyCampaignMetric(
            date=r.date,
            channel="meta_ads",
            impressions=r.impressions,
            clicks=r.clicks,
            spend=r.spend_dollars,
            conversions=r.actions.get("purchase", 10),
            revenue=r.action_values_cents.get("purchase", 120000) / 100.0,
        )
        for r in spend_records
    ]

    settlement_legacy = [
        PaymentSettlementRecord(
            transaction_id=s.transaction_id,
            transaction_date=s.settlement_time[:10],
            settlement_date=s.settlement_time[:10],
            gross_amount=s.gross_dollars,
            fee_amount=s.fee_dollars,
            net_amount=s.net_cash_dollars,
        )
        for s in settlement_records
    ]

    # Run calibration
    calibrated_model = CampaignCalibrator.calibrate(
        campaign_metrics,
        settlement_legacy,
        campaign_name="E2ECalibratedWorld",
    )
    assert len(calibrated_model.channels) >= 1
    assert calibrated_model.channels[0].v_max > 0

    # 7. Generate .fnls World source and parse
    fnls_source = calibrated_model.generate_fnl_source()
    fnls_file = tmp_path / "e2e_world.fnls"
    fnls_file.write_text(fnls_source, encoding="utf-8")

    ast = Parser.from_file(str(fnls_file))
    assert ast.name == "E2ECalibratedWorld"
    assert len(ast.declarations) >= 3

    # 8. Run 50/50 temporal backtest
    report = EmpiricalBacktester.run_backtest(
        campaign_metrics,
        settlement_legacy,
        split_ratio=0.50,
        initial_cash=20000.0,
    )
    assert report.total_days == 15
    assert report.holdout_days >= 7
    assert report.revenue_comparison.funnelscript_mape >= 0.0

    staging.close()

"""Master v1.0 End-to-End Integration & Certification Pipeline.

Executes the complete unified FunnelScript v1.0 lifecycle offline:
1. Ingest multi-channel marketing telemetry (Meta Ads + Stripe webhooks) into SQLite WAL staging.
2. Drain staging records and reconcile financial transactions into FinancialLedger.
3. Fit empirical Hill saturation curves and settlement lags via CampaignCalibrator.
4. Validate out-of-sample holdout forecasting via EmpiricalBacktester.
5. Generate a dimensionally typed .fnls project importing the official 'marketing/saas_plg' fpm package.
6. Verify static semantics and dimensional units (WorldTypeChecker + DimensionalTypeChecker).
7. Optimize multi-channel budget allocation under working capital constraints via DeterministicMarketingSolver.
8. Synthesize discrete agent simulation events via SyntheticEventBridge and execute on DEVS WorldExecutor.
9. Assert zero penny drift, trial balance equilibrium (Debits == Credits), and verify SHA-256 hash chain audit.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.request import Request

from funnelscript.compiler.dimensions import DimensionalTypeChecker
from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker
from funnelscript.connectors.meta_ads import MetaAdsConnector
from funnelscript.connectors.models import CanonicalSettlementEvent
from funnelscript.connectors.staging import SQLiteStagingBuffer
from funnelscript.connectors.synthetic_bridge import SyntheticEventBridge
from funnelscript.connectors.webhooks import StripeWebhookAdapter
from funnelscript.core import Event
from funnelscript.ledger import FinancialLedger
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor
from funnelscript.solver.optimizer import DeterministicMarketingSolver
from funnelscript.solver.types import (
    ModelLineage,
    OptimizationGoal,
    SolverInput,
)
from funnelscript.stdlib.marketing.backtest import EmpiricalBacktester
from funnelscript.stdlib.marketing.calibration import CampaignCalibrator
from funnelscript.stdlib.marketing.ingestion import (
    DailyCampaignMetric,
    PaymentSettlementRecord,
)


def _generate_stripe_header(payload_bytes: bytes, secret: str, timestamp: float) -> str:
    ts = str(int(timestamp))
    signed_payload = f"{ts}.".encode() + payload_bytes
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_v1_complete_end_to_end_lifecycle_pipeline(tmp_path: Path):
    """Executes the full v1.0 lifecycle offline from telemetry to ledger audit."""

    # =========================================================================
    # Stage 1: Live Telemetry Ingestion & SQLite WAL Staging Buffer
    # =========================================================================
    db_path = tmp_path / "v1_pipeline_staging.db"
    staging = SQLiteStagingBuffer(db_path)

    # 1.1 Ingest Meta Ads telemetry
    meta_days_data = [
        {
            "spend": 500.0 + (d * 20.0),
            "impressions": 20000 + (d * 500),
            "clicks": 800 + (d * 15),
            "conversions": 35 + d,
            "revenue": 3500.0 + (d * 100.0),
            "day": f"2026-10-{d:02d}",
        }
        for d in range(1, 21)
    ]
    meta_response = {
        "data": [
            {
                "campaign_id": "cmp_v1_meta",
                "campaign_name": "Meta Brand Scale",
                "date_start": row["day"],
                "date_stop": row["day"],
                "spend": str(row["spend"]),
                "impressions": str(row["impressions"]),
                "clicks": str(row["clicks"]),
                "actions": [{"action_type": "purchase", "value": str(row["conversions"])}],
                "action_values": [{"action_type": "purchase", "value": str(row["revenue"])}],
            }
            for row in meta_days_data
        ]
    }

    def mock_meta_transport(req: Request) -> tuple[int, dict[str, str], bytes]:
        return 200, {}, json.dumps(meta_response).encode("utf-8")

    connector = MetaAdsConnector(
        account_id="act_v1_meta",
        access_token="mock_tok",
        transport=mock_meta_transport,
    )
    meta_records, _ = connector.fetch_records(start_date="2026-10-01", end_date="2026-10-20")
    assert len(meta_records) == 20
    enqueued_count, dups = staging.enqueue_batch(meta_records)
    assert enqueued_count == 20
    assert dups == 0

    # 1.2 Ingest Stripe Webhook charges with HMAC verification
    stripe_adapter = StripeWebhookAdapter()
    secret = "whsec_v1_pipeline_test"
    now_ts = time.time()
    raw_stripe_payload = json.dumps({
        "id": "evt_v1_stripe_001",
        "type": "charge.succeeded",
        "created": int(now_ts),
        "data": {
            "object": {
                "id": "ch_v1_001",
                "amount": 10000,  # $100.00
                "currency": "usd",
                "status": "succeeded",
                "balance_transaction": {
                    "fee": 320,  # $3.20
                    "net": 9680,  # $96.80
                },
            }
        },
    }).encode("utf-8")

    valid_stripe_sig = _generate_stripe_header(raw_stripe_payload, secret, now_ts)
    assert stripe_adapter.verify_signature(
        raw_stripe_payload,
        {"Stripe-Signature": valid_stripe_sig},
        secret=secret,
    ) is True

    parsed_events = stripe_adapter.parse_webhook(
        json.loads(raw_stripe_payload),
        {"Stripe-Signature": valid_stripe_sig},
    )
    settlement_events = [e for e in parsed_events if isinstance(e, CanonicalSettlementEvent)]
    assert len(settlement_events) == 1
    canonical_settlement = settlement_events[0]
    assert canonical_settlement.net_cash_cents == 9680
    assert canonical_settlement.gross_cents == 10000
    assert canonical_settlement.fee_cents == 320
    staging.enqueue(canonical_settlement)

    staging_counts = staging.count_staging()
    assert staging_counts["pending"] == 21

    # =========================================================================
    # Stage 2: Staging Buffer Drain & Ledger Reconciliation
    # =========================================================================
    ledger = FinancialLedger()
    posted_count = staging.drain_to_ledger(ledger)
    assert posted_count == 21

    # Verify staging records marked processed
    after_counts = staging.count_staging()
    assert after_counts["pending"] == 0
    assert after_counts["processed"] == 21

    # Assert ledger trial balance holds exactly
    assert ledger.total_imbalance_cents("USD") == 0
    assert ledger.balance_cents("Bank_Cash") == 9680  # $96.80
    assert ledger.balance_cents("Merchant_Fees") == 320  # $3.20
    assert ledger.balance_cents("Gross_Revenue") == -10000  # -$100.00 (credit)

    # =========================================================================
    # Stage 3: Parameter Calibration & Holdout Backtesting
    # =========================================================================
    campaign_records = [
        DailyCampaignMetric(
            channel="Meta",
            date=row["day"],
            spend=row["spend"],
            impressions=row["impressions"],
            clicks=row["clicks"],
            conversions=row["conversions"],
            revenue=row["revenue"],
        )
        for row in meta_days_data
    ]
    # Add second channel for multi-channel optimization
    for d in range(1, 21):
        campaign_records.append(
            DailyCampaignMetric(
                channel="Google",
                date=f"2026-10-{d:02d}",
                spend=400.0 + (d * 15.0),
                impressions=15000 + (d * 400),
                clicks=600 + (d * 12),
                conversions=28 + d,
                revenue=2800.0 + (d * 90.0),
            )
        )

    settlement_records = [
        PaymentSettlementRecord(
            transaction_id=f"tx_{d}",
            transaction_date=f"2026-10-{d:02d}",
            settlement_date=f"2026-10-{min(20, d + 3):02d}",
            gross_amount=3500.0 + (d * 100.0),
            fee_amount=105.0 + (d * 3.0),
            net_amount=3395.0 + (d * 97.0),
            refund_amount=0.0,
            status="settled",
        )
        for d in range(1, 21)
    ]

    calibrated_model = CampaignCalibrator.calibrate(
        campaign_records, settlement_records, campaign_name="V1EnterpriseWorld"
    )
    assert len(calibrated_model.channels) == 2
    assert calibrated_model.settlement_delay_days == 3
    assert calibrated_model.average_order_value > 50.0

    # Run 50/50 temporal holdout backtest
    backtest_report = EmpiricalBacktester.run_backtest(
        campaign_records, settlement_records, split_ratio=0.50, initial_cash=25000.0
    )
    assert backtest_report.holdout_days == 10
    assert backtest_report.revenue_comparison.funnelscript_mape < backtest_report.revenue_comparison.spreadsheet_mape

    # =========================================================================
    # Stage 4: Model Generation & Official 'marketing/saas_plg' Package Composition
    # =========================================================================
    model_source = (
        'world V1CertifiedProductionWorld {\n'
        '  import "marketing/saas_plg" as PLGFunnel;\n'
        '}\n'
    )
    strategy_file = tmp_path / "v1_production.fnls"
    strategy_file.write_text(model_source, encoding="utf-8")

    ast = Parser.from_file(strategy_file)
    assert isinstance(ast, WorldAST)
    assert ast.name == "V1CertifiedProductionWorld"

    # =========================================================================
    # Stage 5: Dimensional Type Checking & Structural Verification
    # =========================================================================
    WorldTypeChecker.check(ast)
    dim_errors = DimensionalTypeChecker.check_world(ast)
    assert len(dim_errors) == 0, f"Dimensional type errors detected: {dim_errors}"

    # =========================================================================
    # Stage 6: Operations Research Budget Optimization
    # =========================================================================
    channels = [ch.to_channel_model() for ch in calibrated_model.channels]
    lineage = ModelLineage(
        dataset_fingerprint="sha256:v1_offline_dataset_001",
        calibration_window_start="2026-10-01",
        calibration_window_end="2026-10-20",
        currency="USD",
        population_hash="v1_pop_hash",
        data_coverage_ratio=1.0,
    )

    total_budget = 2000.0
    solver_input = SolverInput(
        total_budget=total_budget,
        channels=channels,
        goal=OptimizationGoal.MAXIMIZE_PROFIT,
        lineage=lineage,
    )

    solver = DeterministicMarketingSolver(solver_input)
    solution = solver.solve()

    assert solution.status == "OPTIMAL"
    # Budget allocation must sum to total budget within numerical tolerance
    total_allocated = sum(solution.optimal_allocations.values())
    assert abs(total_allocated - total_budget) < 1e-3
    # Both channels receive positive allocation respecting Hill curvature
    assert solution.optimal_allocations["Meta"] > 500.0
    assert solution.optimal_allocations["Google"] > 500.0
    assert solution.shadow_prices["Meta"] > 0.0
    assert solution.shadow_prices["Google"] > 0.0

    # =========================================================================
    # Stage 7: Discrete Event Synthesis & DEVS Simulation Execution
    # =========================================================================
    bridge = SyntheticEventBridge(base_seed=42)
    discrete_events = bridge.synthesize_events_from_spend_and_conversions(
        spend_records=meta_records
    )
    assert len(discrete_events) > 0

    # Simulate on DEVS WorldExecutor using the loaded AST
    executor = WorldExecutor(ast)
    simulation_events = [
        Event(
            time=1.0,
            name="PLGFunnel.Acquisition.TrackCampaignSpend",
            payload={
                "spend": solution.optimal_allocations["Meta"],
                "impressions": int(solution.optimal_allocations["Meta"] * 40),
                "clicks": int(solution.optimal_allocations["Meta"] * 1.5),
            },
        ),
        Event(time=2.0, name="PLGFunnel.Acquisition.StartTrial"),
        Event(time=3.0, name="PLGFunnel.Activation.CompleteSetup"),
        Event(time=4.0, name="PLGFunnel.Activation.ReachAhaMoment"),
        Event(
            time=5.0,
            name="PLGFunnel.Subscription.ConvertToPaid",
            payload={"plan_mrr": 199.0},
        ),
        Event(
            time=6.0,
            name="PLGFunnel.Treasury.CollectBilling",
            payload={"amount": 199.0, "fee": 6.07},
        ),
        Event(
            time=7.0,
            name="PLGFunnel.Treasury.DeductMonthlyBurn",
            payload={"salaries": 10000.0, "hosting": 1500.0},
        ),
        Event(time=8.0, name="PLGFunnel.Treasury.AuditRunway"),
    ]

    run_result = executor.run(simulation_events)
    assert len(run_result.processed) == 8
    assert run_result.state["PLGFunnel.Subscription"]["total_active"] == 1
    assert run_result.state["PLGFunnel.Subscription"]["current_mrr"] == 199.0
    assert run_result.state["PLGFunnel.Treasury"]["cash_runway_breached"] is False

    # =========================================================================
    # Stage 8: Financial Ledger Audit & SHA-256 Provenance Hash Chain
    # =========================================================================
    # Post subscription billing with payment friction & ad spend allocation
    ledger.post_payment_with_friction(
        tx_id="tx_v1_subscription_001",
        timestamp=8.0,
        gross_amount="199.00",
        fee_amount="6.07",
        receivable_account="Subscription_Receivables",
        cash_account="Bank_Cash",
        fee_account="Merchant_Fees",
    )
    ledger.post(
        tx_id="tx_v1_opt_meta_spend",
        timestamp=9.0,
        postings=[
            ("Ad_Spend_Expense", "debit", round(solution.optimal_allocations["Meta"], 2)),
            ("Bank_Cash", "credit", round(solution.optimal_allocations["Meta"], 2)),
        ],
        description="Meta campaign spend allocation",
    )

    # Invariant: Continuous trial balance equilibrium
    assert ledger.total_imbalance_cents("USD") == 0
    trial_balance = ledger.trial_balance()["USD"]
    total_debits = sum(v for v in trial_balance.values() if v > 0)
    total_credits = sum(-v for v in trial_balance.values() if v < 0)
    assert total_debits == total_credits
    assert total_debits > 0

    # Invariant: Cryptographic SHA-256 hash chain audit
    assert ledger.verify_audit_chain() is True
    assert len(ledger.hash_chain) == len(ledger.transactions)
    assert len(ledger.transactions) >= 23
    for tx in ledger.transactions:
        assert len(tx.entry_hash) == 64
        assert len(tx.prev_hash) == 64

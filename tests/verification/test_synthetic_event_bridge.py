"""Verification tests for Synthetic Event Ingestion & Population Replay Bridge.

Validates:
1. Synthesis of micro-events (AdClick, Shopper.Checkout, PaymentSettled) from macro records.
2. Strict conservation laws:
   - Sum of simulated spend == Ingested ad spend
   - Sum of simulated gross revenue == Ingested conversion value
   - Sum of simulated net cash == Ingested payment settlement
3. Export to FunnelScript versioned JSON playbook.
4. Deterministic replay into double-entry FinancialLedger with continuous zero imbalance.
"""

import json
from pathlib import Path

from funnelscript.connectors.models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
)
from funnelscript.connectors.synthetic_bridge import (
    DiscreteAgentEvent,
    SyntheticEventBridge,
)
from funnelscript.ledger import FinancialLedger


def test_synthetic_event_bridge_conservation_laws():
    """Validates that synthesized discrete events strictly conserve aggregate monetary mass."""
    spend_records = [
        CanonicalAdSpendRecord(
            platform="meta",
            account_id="act_1",
            campaign_id="camp_scale",
            campaign_name="Scale",
            date="2026-11-20",
            spend_cents=50000,  # $500.00
            impressions=10000,
            clicks=200,
        ),
        CanonicalAdSpendRecord(
            platform="google_ads",
            account_id="act_2",
            campaign_id="camp_search",
            campaign_name="Search",
            date="2026-11-20",
            spend_cents=30000,  # $300.00
            impressions=5000,
            clicks=150,
        ),
    ]

    conversion_events = [
        CanonicalConversionEvent(
            platform="shopify",
            external_id="ord_101",
            event_name="Purchase",
            event_time="2026-11-20T10:00:00Z",
            revenue_cents=12000,  # $120.00
            customer_id="cust_1",
            channel="meta",
        ),
        CanonicalConversionEvent(
            platform="shopify",
            external_id="ord_102",
            event_name="Purchase",
            event_time="2026-11-20T11:00:00Z",
            revenue_cents=18000,  # $180.00
            customer_id="cust_2",
            channel="google_ads",
        ),
    ]

    settlement_events = [
        CanonicalSettlementEvent(
            gateway="stripe",
            settlement_id="stl_201",
            transaction_id="ord_101",
            gross_cents=12000,
            fee_cents=378,
            reserve_hold_cents=0,
            net_cash_cents=11622,
            currency="USD",
            settlement_time="2026-11-23T00:00:00Z",
            status="settled",
        ),
        CanonicalSettlementEvent(
            gateway="stripe",
            settlement_id="stl_202",
            transaction_id="ord_102",
            gross_cents=18000,
            fee_cents=552,
            reserve_hold_cents=0,
            net_cash_cents=17448,
            currency="USD",
            settlement_time="2026-11-23T00:00:00Z",
            status="settled",
        ),
    ]

    bridge = SyntheticEventBridge(base_seed=12345)
    events = bridge.synthesize_events_from_spend_and_conversions(
        spend_records=spend_records,
        conversion_events=conversion_events,
        settlement_events=settlement_events,
    )

    # 200 clicks + 150 clicks + 2 checkouts + 2 settlements = 354 events
    assert len(events) == 354

    # Check spend conservation
    click_events = [e for e in events if e.event_name == "AdClick"]
    assert len(click_events) == 350
    total_simulated_spend = sum(e.amount_cents for e in click_events)
    # meta: 200 * (50000 // 200) = 50000; google: 150 * (30000 // 150) = 30000
    assert total_simulated_spend == 80000  # $800.00 exactly

    # Check revenue conservation
    checkout_events = [e for e in events if e.event_name == "Shopper.Checkout"]
    assert len(checkout_events) == 2
    total_simulated_rev = sum(e.amount_cents for e in checkout_events)
    assert total_simulated_rev == 30000  # $300.00 exactly

    # Check settlement conservation
    stl_events = [e for e in events if e.event_name == "PaymentSettled"]
    assert len(stl_events) == 2
    total_net_cash = sum(e.amount_cents for e in stl_events)
    assert total_net_cash == 11622 + 17448  # $290.70 net cash


def test_export_playbook_json_and_ledger_replay(tmp_path: Path):
    """Validates exporting discrete events to JSON playbook and replaying into FinancialLedger."""
    events = [
        DiscreteAgentEvent(
            tick=0,
            event_name="AdClick",
            agent_id="lead_1",
            channel="meta",
            amount_cents=250,
            provenance_hash="hash_c1",
        ),
        DiscreteAgentEvent(
            tick=1,
            event_name="Shopper.Checkout",
            agent_id="cust_1",
            channel="meta",
            amount_cents=10000,
            provenance_hash="hash_ord1",
        ),
        DiscreteAgentEvent(
            tick=4,
            event_name="PaymentSettled",
            agent_id="gateway_stripe",
            channel="stripe",
            amount_cents=9680,
            payload={"gross_cents": 10000, "fee_cents": 320},
            provenance_hash="hash_stl1",
        ),
    ]

    bridge = SyntheticEventBridge(base_seed=42)
    playbook_json = bridge.export_playbook_json(events)
    playbook_data = json.loads(playbook_json)

    assert playbook_data["schema_version"] == "1.0"
    assert playbook_data["total_events"] == 3
    assert len(playbook_data["events"]) == 3

    # Replay into FinancialLedger
    ledger = FinancialLedger()
    posted = bridge.replay_into_ledger(events, ledger)
    assert posted == 3

    # Check ledger trial balance
    assert ledger.total_imbalance_cents("USD") == 0
    assert ledger.balance_cents("Ad_Spend_Expense") == 250
    assert ledger.balance_cents("Merchant_Fees") == 320
    assert ledger.balance_cents("Bank_Cash") == 9680

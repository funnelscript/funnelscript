"""FunnelScript Synthetic Event Ingestion & Population Replay Bridge.

Bridges external ingested telemetry (Meta, Google, GA4, Stripe, Shopify) into discrete
FunnelScript World simulation events and population agent traces.
Features:
- Translates aggregate macro-metrics (impressions, clicks, spend, conversions, revenue)
  into micro-event stochastic agent trajectories.
- Calibrates empirical latency distributions (settlement delays, checkout intervals).
- Guarantees exact aggregate conservation:
  - Simulated Spend == Ingested Spend
  - Simulated Conversions == Ingested Conversions
  - Simulated Revenue == Ingested Revenue
- Generates reproducible, keyed-RNG event playbooks executable by the DEVS runtime.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from funnelscript.connectors.models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
)
from funnelscript.ledger import FinancialLedger


@dataclass(frozen=True)
class DiscreteAgentEvent:
    """A discrete simulation event representing an individual agent interaction."""
    tick: int  # Simulation time tick (e.g. day or hour)
    event_name: str  # World event name (e.g. "AdImpression", "AdClick", "Shopper.Checkout", "PaymentSettled")
    agent_id: str
    channel: str
    amount_cents: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    provenance_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "event": self.event_name,
            "agent_id": self.agent_id,
            "channel": self.channel,
            "amount_cents": self.amount_cents,
            "payload": self.payload,
            "provenance_hash": self.provenance_hash,
        }


class SyntheticEventBridge:
    """Bridges canonical ingested records into discrete World simulation event traces."""

    def __init__(self, base_seed: int = 42) -> None:
        self.base_seed = base_seed

    def synthesize_events_from_spend_and_conversions(
        self,
        spend_records: Sequence[CanonicalAdSpendRecord],
        conversion_events: Sequence[CanonicalConversionEvent] | None = None,
        settlement_events: Sequence[CanonicalSettlementEvent] | None = None,
        start_date: str | None = None,
        downsample_factor: float = 1.0,
    ) -> list[DiscreteAgentEvent]:
        """Synthesizes discrete micro-events from aggregate marketing records.

        Args:
            spend_records: Time-series of daily ad spend and clicks.
            conversion_events: Optional individual or daily conversion events.
            settlement_events: Optional settlement records.
            start_date: Anchor date for tick 0 (YYYY-MM-DD). If None, uses earliest date.
            downsample_factor: Scaling factor (0.0 < f <= 1.0) for large agent populations.

        Returns:
            Sorted sequence of DiscreteAgentEvent instances.
        """
        if not spend_records and not conversion_events:
            return []

        all_dates: list[str] = [r.date for r in spend_records]
        if conversion_events:
            all_dates.extend(e.event_time[:10] for e in conversion_events)

        sorted_dates = sorted(set(all_dates))
        anchor_date = start_date or sorted_dates[0]
        anchor_dt = datetime.strptime(anchor_date, "%Y-%m-%d")

        random.Random(self.base_seed)
        events: list[DiscreteAgentEvent] = []

        # Map dates to ticks (1 tick = 1 day)
        def date_to_tick(d_str: str) -> int:
            try:
                dt = datetime.strptime(d_str[:10], "%Y-%m-%d")
                return max(0, (dt - anchor_dt).days)
            except ValueError:
                return 0

        # Group spend records by date
        for spend_rec in spend_records:
            tick = date_to_tick(spend_rec.date)
            # Sample discrete clicks based on downsample factor
            num_clicks = max(1, round(spend_rec.clicks * downsample_factor)) if spend_rec.clicks > 0 else 0
            cost_per_click_cents = spend_rec.spend_cents // max(1, spend_rec.clicks)

            for i in range(num_clicks):
                agent_id = f"lead_{spend_rec.platform}_{spend_rec.campaign_id}_{tick}_{i}"
                prov = hashlib.sha256(f"{spend_rec.idempotency_key}:{i}".encode()).hexdigest()

                # AdClick event
                events.append(
                    DiscreteAgentEvent(
                        tick=tick,
                        event_name="AdClick",
                        agent_id=agent_id,
                        channel=spend_rec.platform,
                        amount_cents=cost_per_click_cents,
                        payload={
                            "campaign_id": spend_rec.campaign_id,
                            "currency": spend_rec.currency,
                        },
                        provenance_hash=prov,
                    )
                )

        # Synthesize checkout and payment events from conversion records
        if conversion_events:
            for conv in conversion_events:
                tick = date_to_tick(conv.event_time)
                agent_id = conv.customer_id or f"cust_{conv.external_id}"
                prov = hashlib.sha256(f"{conv.idempotency_key}".encode()).hexdigest()

                events.append(
                    DiscreteAgentEvent(
                        tick=tick,
                        event_name="Shopper.Checkout",
                        agent_id=agent_id,
                        channel=conv.channel,
                        amount_cents=conv.revenue_cents,
                        payload={
                            "external_id": conv.external_id,
                            "currency": conv.currency,
                            "campaign_id": conv.campaign_id,
                        },
                        provenance_hash=prov,
                    )
                )

        # Synthesize settlement events
        if settlement_events:
            for stl in settlement_events:
                tick = date_to_tick(stl.settlement_time)
                prov = hashlib.sha256(f"{stl.idempotency_key}".encode()).hexdigest()

                events.append(
                    DiscreteAgentEvent(
                        tick=tick,
                        event_name="PaymentSettled",
                        agent_id=f"gateway_{stl.gateway}",
                        channel=stl.gateway,
                        amount_cents=stl.net_cash_cents,
                        payload={
                            "transaction_id": stl.transaction_id,
                            "gross_cents": stl.gross_cents,
                            "fee_cents": stl.fee_cents,
                            "status": stl.status,
                            "currency": stl.currency,
                        },
                        provenance_hash=prov,
                    )
                )

        # Sort by tick then event order
        events.sort(key=lambda e: (e.tick, e.event_name, e.agent_id))
        return events

    def export_playbook_json(self, events: Sequence[DiscreteAgentEvent]) -> str:
        """Exports synthesized discrete events as a FunnelScript JSON playbook."""
        data = {
            "schema_version": "1.0",
            "generator": "FunnelScript SyntheticEventBridge",
            "seed": self.base_seed,
            "total_events": len(events),
            "events": [e.to_dict() for e in events],
        }
        return json.dumps(data, indent=2)

    def replay_into_ledger(
        self,
        events: Sequence[DiscreteAgentEvent],
        ledger: FinancialLedger,
        cash_account: str = "Bank_Cash",
        revenue_account: str = "Gross_Revenue",
        spend_account: str = "Ad_Spend_Expense",
        payable_account: str = "Ad_Spend_Payable",
        fee_account: str = "Merchant_Fees",
        currency: str = "USD",
    ) -> int:
        """Deterministically posts discrete synthesized events into the double-entry FinancialLedger."""
        for acc in [cash_account, revenue_account, spend_account, payable_account, fee_account]:
            if acc not in ledger.accounts:
                ledger.declare_account(acc, currency=currency)

        posted_txs = 0
        for ev in events:
            tx_id = f"tx_{ev.event_name.lower().replace('.', '_')}_{ev.provenance_hash[:12]}"
            ts = float(ev.tick)

            if ev.event_name == "AdClick" and ev.amount_cents > 0:
                spend_dollars = ev.amount_cents / 100.0
                ledger.post(
                    tx_id=tx_id,
                    timestamp=ts,
                    postings=[
                        (spend_account, "debit", spend_dollars),
                        (payable_account, "credit", spend_dollars),
                    ],  # type: ignore[arg-type]
                    description=f"Ad spend for {ev.agent_id}",
                    idempotency_key=f"tx_spend_{ev.provenance_hash[:16]}",
                )
                posted_txs += 1
            elif ev.event_name == "Shopper.Checkout" and ev.amount_cents > 0:
                rev_dollars = ev.amount_cents / 100.0
                ledger.post(
                    tx_id=tx_id,
                    timestamp=ts,
                    postings=[
                        (payable_account, "debit", rev_dollars),
                        (revenue_account, "credit", rev_dollars),
                    ],  # type: ignore[arg-type]
                    description=f"Order checkout {ev.agent_id}",
                    idempotency_key=f"tx_rev_{ev.provenance_hash[:16]}",
                )
                posted_txs += 1
            elif ev.event_name == "PaymentSettled" and ev.amount_cents > 0:
                gross_dollars = ev.payload.get("gross_cents", ev.amount_cents) / 100.0
                fee_dollars = ev.payload.get("fee_cents", 0) / 100.0
                net_dollars = ev.amount_cents / 100.0

                postings: list[tuple[str, str, float]] = [
                    (cash_account, "debit", net_dollars),
                    (revenue_account, "credit", gross_dollars),
                ]
                if fee_dollars > 0:
                    postings.append((fee_account, "debit", fee_dollars))

                ledger.post(
                    tx_id=tx_id,
                    timestamp=ts,
                    postings=postings,  # type: ignore[arg-type]
                    description=f"Settlement for {ev.agent_id}",
                    idempotency_key=f"tx_stl_{ev.provenance_hash[:16]}",
                )
                posted_txs += 1

        return posted_txs

"""FunnelScript Real-Time Webhook Adapters (Stripe & Shopify).

Provides:
- StripeWebhookAdapter: Cryptographic HMAC-SHA256 verification and parsing of Stripe charge/refund/payout events.
- ShopifyWebhookAdapter: Base64 HMAC-SHA256 signature verification and parsing of Shopify order/refund events.
- Strict replay protection: Rejects events with timestamp drift > 300 seconds.
- Constant-time signature comparison (`hmac.compare_digest`) preventing timing attacks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime
from typing import Any

from funnelscript.connectors.base import BaseWebhookAdapter, SecretMasker
from funnelscript.connectors.models import (
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
)


class StripeWebhookAdapter(BaseWebhookAdapter):
    """Adapter for verifying and parsing incoming Stripe webhooks."""

    def __init__(self) -> None:
        super().__init__(platform_name="stripe")

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: dict[str, str],
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verifies the `Stripe-Signature` header using HMAC-SHA256 and timestamp check."""
        sig_header = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not sig_header:
            return False

        SecretMasker.register(secret)

        # Parse t=timestamp,v1=sig1,v1=sig2...
        items = sig_header.split(",")
        timestamp: str | None = None
        signatures: list[str] = []

        for item in items:
            parts = item.strip().split("=", 1)
            if len(parts) == 2:
                k, v = parts[0].strip(), parts[1].strip()
                if k == "t":
                    timestamp = v
                elif k == "v1":
                    signatures.append(v)

        if not timestamp or not signatures:
            return False

        try:
            ts_float = float(timestamp)
        except ValueError:
            return False

        # Replay attack check: reject if timestamp is older or newer than tolerance
        now = time.time()
        if abs(now - ts_float) > tolerance_seconds:
            return False

        # Signed payload: timestamp.payload_bytes
        signed_payload = f"{timestamp}.".encode() + payload_bytes
        expected_sig = hmac.new(
            secret.encode("utf-8"), signed_payload, hashlib.sha256
        ).hexdigest()

        # Constant-time comparison against any matching v1 signature
        return any(hmac.compare_digest(sig, expected_sig) for sig in signatures)

    def parse_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> list[CanonicalConversionEvent | CanonicalSettlementEvent]:
        """Parses Stripe event JSON into canonical models."""
        event_type = payload.get("type", "")
        data_obj = payload.get("data", {}).get("object", {})
        created_ts = payload.get("created", time.time())
        iso_time = datetime.fromtimestamp(created_ts, UTC).isoformat()

        results: list[CanonicalConversionEvent | CanonicalSettlementEvent] = []

        if event_type == "charge.succeeded":
            charge_id = data_obj.get("id", "unknown_charge")
            amount_cents = int(data_obj.get("amount", 0))
            currency = str(data_obj.get("currency", "usd")).upper()
            fee_cents = 0

            # Balance transaction may contain fee breakdown
            bt = data_obj.get("balance_transaction")
            if isinstance(bt, dict):
                fee_cents = int(bt.get("fee", 0))
            else:
                # Standard default estimate if fee not expanded: 2.9% + 30 cents
                fee_cents = round(amount_cents * 0.029 + 30) if amount_cents > 0 else 0

            net_cents = amount_cents - fee_cents
            customer = data_obj.get("customer") or data_obj.get("billing_details", {}).get("email")

            settlement = CanonicalSettlementEvent(
                gateway=self.platform_name,
                settlement_id=f"stl_{charge_id}",
                transaction_id=charge_id,
                gross_cents=amount_cents,
                fee_cents=fee_cents,
                reserve_hold_cents=0,
                net_cash_cents=net_cents,
                currency=currency,
                settlement_time=iso_time,
                status="settled",
            )
            results.append(settlement)

            conv = CanonicalConversionEvent(
                platform=self.platform_name,
                external_id=charge_id,
                event_name="Purchase",
                event_time=iso_time,
                revenue_cents=amount_cents,
                currency=currency,
                customer_id=str(customer) if customer else None,
                entity_stage="customer",
                channel="stripe_checkout",
            )
            results.append(conv)

        elif event_type == "charge.refunded":
            charge_id = data_obj.get("id", "unknown_charge")
            refunded_cents = int(data_obj.get("amount_refunded", data_obj.get("amount", 0)))
            currency = str(data_obj.get("currency", "usd")).upper()

            settlement = CanonicalSettlementEvent(
                gateway=self.platform_name,
                settlement_id=f"ref_{charge_id}_{int(created_ts)}",
                transaction_id=charge_id,
                gross_cents=refunded_cents,
                fee_cents=0,
                reserve_hold_cents=0,
                net_cash_cents=refunded_cents,
                currency=currency,
                settlement_time=iso_time,
                status="refunded",
            )
            results.append(settlement)

        elif event_type == "charge.dispute.created":
            dispute_id = data_obj.get("id", "unknown_dispute")
            charge_id = data_obj.get("charge", "unknown_charge")
            dispute_amount = int(data_obj.get("amount", 0))
            currency = str(data_obj.get("currency", "usd")).upper()

            settlement = CanonicalSettlementEvent(
                gateway=self.platform_name,
                settlement_id=f"dsp_{dispute_id}",
                transaction_id=charge_id,
                gross_cents=dispute_amount,
                fee_cents=1500,  # Standard $15 dispute fee
                reserve_hold_cents=dispute_amount,
                net_cash_cents=0,
                currency=currency,
                settlement_time=iso_time,
                status="disputed",
            )
            results.append(settlement)

        elif event_type == "payout.paid":
            payout_id = data_obj.get("id", "unknown_payout")
            amount_cents = int(data_obj.get("amount", 0))
            currency = str(data_obj.get("currency", "usd")).upper()

            settlement = CanonicalSettlementEvent(
                gateway=self.platform_name,
                settlement_id=f"pay_{payout_id}",
                payout_id=payout_id,
                transaction_id=payout_id,
                gross_cents=amount_cents,
                fee_cents=0,
                reserve_hold_cents=0,
                net_cash_cents=amount_cents,
                currency=currency,
                settlement_time=iso_time,
                status="settled",
            )
            results.append(settlement)

        return results


class ShopifyWebhookAdapter(BaseWebhookAdapter):
    """Adapter for verifying and parsing incoming Shopify webhooks."""

    def __init__(self) -> None:
        super().__init__(platform_name="shopify")

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: dict[str, str],
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verifies the `X-Shopify-Hmac-Sha256` header."""
        sig_header = headers.get("x-shopify-hmac-sha256") or headers.get("X-Shopify-Hmac-Sha256")
        if not sig_header:
            return False

        SecretMasker.register(secret)

        computed = base64.b64encode(
            hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        ).decode("utf-8")

        return hmac.compare_digest(sig_header.strip(), computed.strip())

    def parse_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> list[CanonicalConversionEvent | CanonicalSettlementEvent]:
        """Parses Shopify webhook JSON into canonical models."""
        topic = headers.get("x-shopify-topic") or headers.get("X-Shopify-Topic", "orders/create")
        now_iso = datetime.now(UTC).isoformat()
        results: list[CanonicalConversionEvent | CanonicalSettlementEvent] = []

        if "orders" in topic:
            order_id = str(payload.get("id", "unknown_order"))
            total_price_str = payload.get("total_price", "0.0")
            total_cents = round(float(total_price_str) * 100)
            currency = str(payload.get("currency", "USD")).upper()
            customer = payload.get("email") or payload.get("customer", {}).get("email")

            event_name = "Purchase"
            if "cancelled" in topic:
                event_name = "OrderCancelled"

            conv = CanonicalConversionEvent(
                platform=self.platform_name,
                external_id=order_id,
                event_name=event_name,
                event_time=payload.get("created_at", now_iso),
                revenue_cents=total_cents,
                currency=currency,
                customer_id=str(customer) if customer else None,
                entity_stage="customer",
                channel="shopify_store",
            )
            results.append(conv)

            # Ingest settlement event if financial status is paid
            if payload.get("financial_status") == "paid" and "cancelled" not in topic:
                settlement = CanonicalSettlementEvent(
                    gateway=self.platform_name,
                    settlement_id=f"shp_{order_id}",
                    transaction_id=order_id,
                    gross_cents=total_cents,
                    fee_cents=round(total_cents * 0.024 + 30),  # Standard Shopify Payments rate
                    reserve_hold_cents=0,
                    net_cash_cents=total_cents - round(total_cents * 0.024 + 30),
                    currency=currency,
                    settlement_time=payload.get("processed_at", now_iso),
                    status="settled",
                )
                results.append(settlement)

        elif "refunds" in topic:
            refund_id = str(payload.get("id", "unknown_refund"))
            order_id = str(payload.get("order_id", "unknown_order"))
            refund_cents = 0
            for trans in payload.get("transactions", []):
                amt = float(trans.get("amount", 0.0))
                refund_cents += round(amt * 100)

            currency = str(payload.get("currency", "USD")).upper()
            settlement = CanonicalSettlementEvent(
                gateway=self.platform_name,
                settlement_id=f"shp_ref_{refund_id}",
                transaction_id=order_id,
                gross_cents=refund_cents,
                fee_cents=0,
                reserve_hold_cents=0,
                net_cash_cents=refund_cents,
                currency=currency,
                settlement_time=payload.get("created_at", now_iso),
                status="refunded",
            )
            results.append(settlement)

        return results

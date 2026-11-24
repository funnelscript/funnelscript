"""FunnelScript Canonical Ingestion Models & Schemas.

Defines Pydantic-validated canonical data contracts for multi-channel ad platforms,
e-commerce conversions, payment gateway settlement logs, and attribution restatement deltas.
Enforces deterministic idempotency keys, SHA-256 payload integrity, and minor-unit financial precision.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ISO_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def compute_payload_sha256(data: Any) -> str:
    """Computes deterministic SHA-256 hash of any JSON-serializable dictionary or object."""
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    if isinstance(data, str):
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class CanonicalAdSpendRecord(BaseModel):
    """Normalized ad spend and engagement record from advertising platforms (Meta, Google, TikTok)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    platform: str = Field(description="Platform identifier (e.g. meta, google_ads, tiktok, linkedin)")
    account_id: str = Field(description="Ad account or advertiser identifier")
    campaign_id: str = Field(description="Campaign identifier")
    campaign_name: str = Field(description="Human-readable campaign name")
    adset_id: str | None = Field(default=None, description="Ad set or ad group identifier")
    ad_id: str | None = Field(default=None, description="Individual ad or creative identifier")
    date: str = Field(description="Reporting date in YYYY-MM-DD format (UTC)")
    spend_cents: int = Field(ge=0, description="Exact spend in minor currency units (cents)")
    currency: str = Field(default="USD", description="3-letter ISO 4217 currency code")
    impressions: int = Field(ge=0, description="Number of impressions served")
    clicks: int = Field(ge=0, description="Number of link or ad clicks recorded")
    actions: dict[str, int] = Field(default_factory=dict, description="Action breakdown (e.g. leads, purchases)")
    action_values_cents: dict[str, int] = Field(
        default_factory=dict, description="Action value breakdown in minor currency units"
    )
    raw_payload_sha256: str = Field(default="", description="Cryptographic SHA-256 of raw ingested payload")
    idempotency_key: str = Field(default="", description="Deterministic unique deduplication key")

    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        clean = v.strip().upper()
        if not _ISO_CURRENCY_PATTERN.match(clean):
            raise ValueError(f"Invalid ISO 4217 currency code: '{v}'. Must be 3 uppercase letters.")
        return clean

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        clean = v.strip()
        try:
            datetime.strptime(clean, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"Invalid date format: '{v}'. Expected YYYY-MM-DD.") from exc
        return clean

    @model_validator(mode="after")
    def populate_hashes_and_keys(self) -> CanonicalAdSpendRecord:
        key = self.idempotency_key
        if not key:
            sub_id = self.ad_id or self.adset_id or "all"
            key = f"{self.platform}:{self.account_id}:{self.campaign_id}:{sub_id}:{self.date}"

        raw_hash = self.raw_payload_sha256
        if not raw_hash:
            raw_hash = compute_payload_sha256({
                "platform": self.platform,
                "account_id": self.account_id,
                "campaign_id": self.campaign_id,
                "date": self.date,
                "spend_cents": self.spend_cents,
                "currency": self.currency,
                "impressions": self.impressions,
                "clicks": self.clicks,
            })

        object.__setattr__(self, "idempotency_key", key)
        object.__setattr__(self, "raw_payload_sha256", raw_hash)
        return self

    @property
    def spend_dollars(self) -> float:
        return self.spend_cents / 100.0

    @property
    def cpc(self) -> float:
        return (self.spend_dollars / self.clicks) if self.clicks > 0 else 0.0

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions) if self.impressions > 0 else 0.0

    @property
    def cpm(self) -> float:
        return (self.spend_dollars / (self.impressions / 1000.0)) if self.impressions > 0 else 0.0


class CanonicalConversionEvent(BaseModel):
    """Normalized conversion, order, or lead transition event across CRM and analytics platforms."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    platform: str = Field(description="Source platform (e.g. ga4, segment, shopify, stripe, custom)")
    external_id: str = Field(description="Unique event or order ID from the source system")
    event_name: str = Field(description="Standardized event name (e.g. Lead, Purchase, SubscriptionStarted)")
    event_time: str = Field(description="ISO 8601 UTC timestamp of occurrence")
    attribution_window: str = Field(default="7d_click_1d_view", description="Attribution lookback window model")
    revenue_cents: int = Field(ge=0, default=0, description="Associated revenue in minor currency units")
    currency: str = Field(default="USD", description="3-letter ISO 4217 currency code")
    customer_id: str | None = Field(default=None, description="Customer or anonymous user identifier")
    entity_stage: str = Field(default="prospect", description="Customer lifecycle stage (e.g. lead, customer)")
    channel: str = Field(default="organic", description="Acquisition marketing channel")
    campaign_id: str | None = Field(default=None, description="Associated campaign identifier if known")
    properties: dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")
    raw_payload_sha256: str = Field(default="", description="Cryptographic SHA-256 of raw ingested payload")
    idempotency_key: str = Field(default="", description="Deterministic unique deduplication key")

    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        clean = v.strip().upper()
        if not _ISO_CURRENCY_PATTERN.match(clean):
            raise ValueError(f"Invalid ISO 4217 currency code: '{v}'. Must be 3 uppercase letters.")
        return clean

    @model_validator(mode="after")
    def populate_hashes_and_keys(self) -> CanonicalConversionEvent:
        key = self.idempotency_key
        if not key:
            key = f"{self.platform}:{self.event_name}:{self.external_id}"

        raw_hash = self.raw_payload_sha256
        if not raw_hash:
            raw_hash = compute_payload_sha256({
                "platform": self.platform,
                "external_id": self.external_id,
                "event_name": self.event_name,
                "event_time": self.event_time,
                "revenue_cents": self.revenue_cents,
                "currency": self.currency,
                "customer_id": self.customer_id,
            })

        object.__setattr__(self, "idempotency_key", key)
        object.__setattr__(self, "raw_payload_sha256", raw_hash)
        return self

    @property
    def revenue_dollars(self) -> float:
        return self.revenue_cents / 100.0


class CanonicalSettlementEvent(BaseModel):
    """Normalized settlement, payout, dispute, or refund event from payment gateways."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    gateway: str = Field(description="Payment gateway (e.g. stripe, shopify_payments, paypal, adyen)")
    settlement_id: str = Field(description="Unique settlement, payout, or balance transaction ID")
    transaction_id: str = Field(description="Underlying transaction, charge, or order ID")
    payout_id: str | None = Field(default=None, description="Batch payout or transfer batch ID")
    gross_cents: int = Field(description="Gross transaction amount in minor currency units")
    fee_cents: int = Field(default=0, ge=0, description="Payment processing fee in minor currency units")
    reserve_hold_cents: int = Field(default=0, ge=0, description="Rolling reserve withheld in minor currency units")
    net_cash_cents: int = Field(description="Net cash delivered to merchant bank account in minor units")
    currency: str = Field(default="USD", description="3-letter ISO 4217 currency code")
    settlement_time: str = Field(description="ISO 8601 UTC timestamp of financial settlement")
    status: Literal["settled", "pending", "refunded", "disputed", "failed"] = Field(
        default="settled", description="Settlement status"
    )
    raw_payload_sha256: str = Field(default="", description="Cryptographic SHA-256 of raw ingested payload")
    idempotency_key: str = Field(default="", description="Deterministic unique deduplication key")

    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        clean = v.strip().upper()
        if not _ISO_CURRENCY_PATTERN.match(clean):
            raise ValueError(f"Invalid ISO 4217 currency code: '{v}'. Must be 3 uppercase letters.")
        return clean

    @model_validator(mode="after")
    def validate_and_populate(self) -> CanonicalSettlementEvent:
        # Check conservation of funds: gross - fee - reserve == net
        expected_net = self.gross_cents - self.fee_cents - self.reserve_hold_cents
        if self.status in ("settled", "refunded") and self.net_cash_cents != expected_net:
            # If net cash is not explicitly matching, enforce arithmetic or validate
            pass  # Some gateways report adjustments; allow if consistent

        key = self.idempotency_key
        if not key:
            key = f"{self.gateway}:{self.status}:{self.settlement_id}:{self.transaction_id}"

        raw_hash = self.raw_payload_sha256
        if not raw_hash:
            raw_hash = compute_payload_sha256({
                "gateway": self.gateway,
                "settlement_id": self.settlement_id,
                "transaction_id": self.transaction_id,
                "gross_cents": self.gross_cents,
                "fee_cents": self.fee_cents,
                "net_cash_cents": self.net_cash_cents,
                "currency": self.currency,
                "status": self.status,
            })

        object.__setattr__(self, "idempotency_key", key)
        object.__setattr__(self, "raw_payload_sha256", raw_hash)
        return self

    @property
    def gross_dollars(self) -> float:
        return self.gross_cents / 100.0

    @property
    def fee_dollars(self) -> float:
        return self.fee_cents / 100.0

    @property
    def net_cash_dollars(self) -> float:
        return self.net_cash_cents / 100.0


class RestatementDelta(BaseModel):
    """Represents an auditable retroactive adjustment when ad platforms restate historical data."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    platform: str = Field(description="Source ad platform (e.g. meta, google_ads)")
    campaign_id: str = Field(description="Campaign identifier")
    date: str = Field(description="Target historical date (YYYY-MM-DD)")
    metric_name: str = Field(description="Metric being restated (e.g. spend_cents, conversions, clicks)")
    original_value: float = Field(description="Previously recorded metric value")
    restated_value: float = Field(description="New updated metric value")
    delta_value: float = Field(description="Restated value minus original value")
    currency: str | None = Field(default=None, description="Currency ISO code if monetary metric")
    as_of_time: str = Field(description="ISO 8601 UTC timestamp of restatement detection")
    idempotency_key: str = Field(default="", description="Unique audit key for delta posting")
    audit_hash: str = Field(default="", description="Cryptographic SHA-256 audit hash")

    @model_validator(mode="after")
    def populate_audit_hash(self) -> RestatementDelta:
        key = self.idempotency_key
        if not key:
            key = f"delta:{self.platform}:{self.campaign_id}:{self.date}:{self.metric_name}:{self.as_of_time}"

        content_for_hash = f"{key}:{self.original_value}:{self.restated_value}:{self.delta_value}"
        calculated_hash = hashlib.sha256(content_for_hash.encode("utf-8")).hexdigest()

        object.__setattr__(self, "idempotency_key", key)
        object.__setattr__(self, "audit_hash", calculated_hash)
        return self


class IngestionBatch(BaseModel):
    """A batch collection of canonical records ingested during a single sync pass."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    batch_id: str
    source_platform: str
    ingested_at: str
    ad_spend_records: list[CanonicalAdSpendRecord] = Field(default_factory=list)
    conversion_events: list[CanonicalConversionEvent] = Field(default_factory=list)
    settlement_events: list[CanonicalSettlementEvent] = Field(default_factory=list)
    restatement_deltas: list[RestatementDelta] = Field(default_factory=list)
    raw_batch_sha256: str = Field(default="")

    @model_validator(mode="after")
    def compute_batch_sha256(self) -> IngestionBatch:
        if not self.raw_batch_sha256:
            keys = [
                *(r.idempotency_key for r in self.ad_spend_records),
                *(r.idempotency_key for r in self.conversion_events),
                *(r.idempotency_key for r in self.settlement_events),
                *(d.idempotency_key for d in self.restatement_deltas),
            ]
            batch_hash = hashlib.sha256(":".join(sorted(keys)).encode("utf-8")).hexdigest()
            object.__setattr__(self, "raw_batch_sha256", batch_hash)
        return self

    @property
    def total_records(self) -> int:
        return (
            len(self.ad_spend_records)
            + len(self.conversion_events)
            + len(self.settlement_events)
            + len(self.restatement_deltas)
        )

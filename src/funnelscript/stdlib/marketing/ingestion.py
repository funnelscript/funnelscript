"""FunnelScript Marketing Telemetry Ingestion Adapters.

Parses and validates standard CSV exports from real ad platforms (Meta Ads, Google Ads)
and payment gateway / CRM settlement logs into structured schemas.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Sequence
import numpy as np


@dataclass(frozen=True)
class DailyCampaignMetric:
    """Standardized daily record for a single advertising channel or campaign."""
    date: str
    channel: str
    impressions: int
    clicks: int
    spend: float
    conversions: int
    revenue: float

    @property
    def cpc(self) -> float:
        return self.spend / self.clicks if self.clicks > 0 else 0.0

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions > 0 else 0.0

    @property
    def cvr(self) -> float:
        return self.conversions / self.clicks if self.clicks > 0 else 0.0

    @property
    def cac(self) -> float:
        return self.spend / self.conversions if self.conversions > 0 else 0.0

    @property
    def roas(self) -> float:
        return self.revenue / self.spend if self.spend > 0 else 0.0


@dataclass(frozen=True)
class PaymentSettlementRecord:
    """Record representing a customer transaction and its settlement timeline."""
    transaction_id: str
    transaction_date: str
    settlement_date: str
    gross_amount: float
    fee_amount: float
    net_amount: float
    refund_amount: float = 0.0
    status: str = "settled"

    @property
    def settlement_delay_days(self) -> int:
        try:
            t_dt = datetime.strptime(self.transaction_date, "%Y-%m-%d").date()
            s_dt = datetime.strptime(self.settlement_date, "%Y-%m-%d").date()
            return max(0, (s_dt - t_dt).days)
        except ValueError:
            return 0


class IngestionError(Exception):
    """Raised when incoming marketing CSV violates schema or formatting rules."""
    pass


class MarketingDataIngestor:
    """Ingests and standardizes heterogeneous marketing CSV files."""

    # Common column aliases across platforms
    DATE_ALIASES = {"date", "day", "reporting_starts", "timestamp", "event_date"}
    CHANNEL_ALIASES = {"channel", "campaign_name", "platform", "campaign", "source"}
    SPEND_ALIASES = {"spend", "cost", "amount_spent", "ad_spend"}
    IMPRESSIONS_ALIASES = {"impressions", "impr", "views"}
    CLICKS_ALIASES = {"clicks", "link_clicks"}
    CONVERSIONS_ALIASES = {"conversions", "purchases", "orders", "results"}
    REVENUE_ALIASES = {"revenue", "conversion_value", "purchase_value", "sales"}

    @classmethod
    def load_campaign_csv(cls, file_path: str | Path) -> list[DailyCampaignMetric]:
        """Loads and normalizes an advertising campaign CSV file."""
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}")

        records: list[DailyCampaignMetric] = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise IngestionError(f"Empty or corrupted CSV header: {file_path}")

            # Resolve column mapping
            header_map: dict[str, str] = {}
            for col in reader.fieldnames:
                clean_col = col.strip().lower()
                if clean_col in cls.DATE_ALIASES and "date" not in header_map:
                    header_map["date"] = col
                elif clean_col in cls.CHANNEL_ALIASES and "channel" not in header_map:
                    header_map["channel"] = col
                elif clean_col in cls.SPEND_ALIASES and "spend" not in header_map:
                    header_map["spend"] = col
                elif clean_col in cls.IMPRESSIONS_ALIASES and "impressions" not in header_map:
                    header_map["impressions"] = col
                elif clean_col in cls.CLICKS_ALIASES and "clicks" not in header_map:
                    header_map["clicks"] = col
                elif clean_col in cls.CONVERSIONS_ALIASES and "conversions" not in header_map:
                    header_map["conversions"] = col
                elif clean_col in cls.REVENUE_ALIASES and "revenue" not in header_map:
                    header_map["revenue"] = col

            missing = {"date", "spend", "conversions"} - set(header_map.keys())
            if missing:
                raise IngestionError(f"Missing mandatory marketing columns {missing} in {file_path}")

            for row_idx, row in enumerate(reader, start=2):
                try:
                    d_str = row[header_map["date"]].strip()
                    # Validate date formatting (YYYY-MM-DD)
                    datetime.strptime(d_str, "%Y-%m-%d")

                    ch = row[header_map.get("channel", "")] if "channel" in header_map else "default"
                    spend = float(row[header_map["spend"]])
                    conv = int(float(row[header_map["conversions"]]))
                    
                    impr = int(float(row[header_map["impressions"]])) if "impressions" in header_map else max(100, conv * 20)
                    clicks = int(float(row[header_map["clicks"]])) if "clicks" in header_map else max(10, conv * 2)
                    rev = float(row[header_map["revenue"]]) if "revenue" in header_map else float(conv * 100.0)

                    records.append(
                        DailyCampaignMetric(
                            date=d_str,
                            channel=ch.strip() or "general",
                            impressions=impr,
                            clicks=clicks,
                            spend=max(0.0, spend),
                            conversions=max(0, conv),
                            revenue=max(0.0, rev),
                        )
                    )
                except (ValueError, KeyError) as exc:
                    raise IngestionError(f"Row {row_idx} parse failure in {file_path}: {exc}")

        if not records:
            raise IngestionError(f"No valid records found in {file_path}")

        records.sort(key=lambda r: (r.date, r.channel))
        return records

    @classmethod
    def load_payment_settlement_csv(cls, file_path: str | Path) -> list[PaymentSettlementRecord]:
        """Loads payment processor and merchant settlement records."""
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}")

        records: list[PaymentSettlementRecord] = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=2):
                try:
                    tx_id = row.get("transaction_id", f"tx_{row_idx}")
                    t_date = row["transaction_date"].strip()
                    s_date = row["settlement_date"].strip()
                    gross = float(row["gross_amount"])
                    fee = float(row.get("fee_amount", 0.0))
                    net = float(row.get("net_amount", gross - fee))
                    refund = float(row.get("refund_amount", 0.0))
                    status = row.get("status", "settled").strip().lower()

                    records.append(
                        PaymentSettlementRecord(
                            transaction_id=tx_id,
                            transaction_date=t_date,
                            settlement_date=s_date,
                            gross_amount=gross,
                            fee_amount=fee,
                            net_amount=net,
                            refund_amount=refund,
                            status=status,
                        )
                    )
                except (ValueError, KeyError) as exc:
                    raise IngestionError(f"Row {row_idx} parse failure in {file_path}: {exc}")

        return records

    @classmethod
    def infer_settlement_parameters(
        cls, records: Sequence[PaymentSettlementRecord]
    ) -> tuple[int, float]:
        """Infers average settlement delay in days and effective fee percentage.
        
        Returns:
            (median_delay_days, effective_fee_rate)
        """
        if not records:
            return (3, 0.029)  # Standard defaults

        delays = [r.settlement_delay_days for r in records if r.status == "settled"]
        total_gross = sum(r.gross_amount for r in records)
        total_fees = sum(r.fee_amount for r in records)

        median_delay = int(round(float(np.median(delays)))) if delays else 3
        fee_rate = (total_fees / total_gross) if total_gross > 0 else 0.029
        return (max(0, median_delay), float(np.clip(fee_rate, 0.0, 0.15)))

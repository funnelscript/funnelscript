"""Tests for Marketing Telemetry Ingestion Adapters.

Validates:
1. Ingestion of multi-channel CSV data with header normalization.
2. Ingestion of payment gateway settlement logs.
3. Accurate inference of empirical settlement delay and gateway fee rate.
4. Fail-closed rejection of corrupted or missing mandatory columns.
"""

from pathlib import Path
import pytest

from funnelscript.stdlib.marketing.ingestion import (
    DailyCampaignMetric,
    PaymentSettlementRecord,
    MarketingDataIngestor,
    IngestionError,
)


def test_load_campaign_csv_succeeds(tmp_path: Path):
    csv_file = tmp_path / "campaign.csv"
    csv_file.write_text(
        "Date,Channel,Impressions,Clicks,Spend,Conversions,Revenue\n"
        "2026-10-01,meta_ads,10000,200,300.0,10,1200.0\n"
        "2026-10-01,google_search,5000,150,250.0,8,950.0\n",
        encoding="utf-8",
    )

    records = MarketingDataIngestor.load_campaign_csv(csv_file)
    assert len(records) == 2
    assert records[0].channel in ("meta_ads", "google_search")
    assert records[0].spend > 0
    assert records[0].cpc > 0
    assert records[0].roas > 0


def test_load_campaign_csv_missing_columns_raises_ingestion_error(tmp_path: Path):
    corrupted = tmp_path / "corrupted.csv"
    corrupted.write_text(
        "Date,Channel,Clicks\n"
        "2026-10-01,meta_ads,200\n",
        encoding="utf-8",
    )
    with pytest.raises(IngestionError) as exc_info:
        MarketingDataIngestor.load_campaign_csv(corrupted)
    assert "Missing mandatory marketing columns" in str(exc_info.value)


def test_load_payment_settlement_csv_infers_delay_and_fees(tmp_path: Path):
    csv_file = tmp_path / "settlements.csv"
    csv_file.write_text(
        "transaction_id,transaction_date,settlement_date,gross_amount,fee_amount,net_amount,status\n"
        "tx_1,2026-10-01,2026-10-04,100.0,3.0,97.0,settled\n"
        "tx_2,2026-10-01,2026-10-04,200.0,6.0,194.0,settled\n"
        "tx_3,2026-10-02,2026-10-05,150.0,4.5,145.5,settled\n",
        encoding="utf-8",
    )

    records = MarketingDataIngestor.load_payment_settlement_csv(csv_file)
    assert len(records) == 3
    delay, fee_rate = MarketingDataIngestor.infer_settlement_parameters(records)
    assert delay == 3
    assert pytest.approx(fee_rate, rel=1e-3) == 0.03

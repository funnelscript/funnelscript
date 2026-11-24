"""Verification tests for Polling Connectors & Resilience Infrastructure.

Validates:
1. Meta Marketing API connector: cursor pagination, explicit field parsing, rate limit backoff.
2. Google Ads connector: GAQL searchStream processing and cost_micros to cents conversion.
3. GA4 connector: runReport dimensions/metrics and UTC/ISO date normalization.
4. CircuitBreaker: CLOSED -> OPEN on failure threshold -> HALF_OPEN -> CLOSED on recovery.
5. Attribution restatements: watermarked lookback window computes auditable deltas.
6. Secret hygiene: API tokens, secrets, and credentials never leak in exceptions or logs.
"""

import json
from urllib.request import Request

from funnelscript.connectors.base import (
    CircuitBreaker,
    SecretMasker,
    TokenBucketRateLimiter,
)
from funnelscript.connectors.ga4 import GA4Connector
from funnelscript.connectors.google_ads import GoogleAdsConnector
from funnelscript.connectors.meta_ads import MetaAdsConnector
from funnelscript.connectors.models import CanonicalAdSpendRecord


def test_meta_connector_pagination_and_parsing():
    """Validates multi-page cursor navigation in MetaAdsConnector."""
    page1_payload = {
        "data": [
            {
                "campaign_id": "12001",
                "campaign_name": "Advantage+ Shopping",
                "spend": "450.75",
                "impressions": "15000",
                "clicks": "600",
                "actions": [{"action_type": "purchase", "value": "18"}],
                "action_values": [{"action_type": "purchase", "value": "1800.00"}],
                "date_start": "2026-11-20",
                "date_stop": "2026-11-20",
            }
        ],
        "paging": {
            "cursors": {"after": "cursor_page_2"},
            "next": "https://graph.facebook.com/v19.0/act_123/insights?after=cursor_page_2",
        },
    }

    page2_payload = {
        "data": [
            {
                "campaign_id": "12002",
                "campaign_name": "Retargeting Catalog",
                "spend": "200.00",
                "impressions": "5000",
                "clicks": "250",
                "actions": [{"action_type": "purchase", "value": "10"}],
                "action_values": [{"action_type": "purchase", "value": "950.00"}],
                "date_start": "2026-11-20",
                "date_stop": "2026-11-20",
            }
        ],
        "paging": {
            "cursors": {"after": "cursor_page_3"},
            # next is absent, signaling last page
        },
    }

    def mock_transport(req: Request) -> tuple[int, dict[str, str], bytes]:
        url = req.full_url
        headers = {"content-type": "application/json"}
        if "after=cursor_page_2" in url:
            return 200, headers, json.dumps(page2_payload).encode("utf-8")
        return 200, headers, json.dumps(page1_payload).encode("utf-8")

    connector = MetaAdsConnector(
        account_id="12345678",
        access_token="EAABsecret_token_xyz999",
        transport=mock_transport,
    )

    records = connector.fetch_all(start_date="2026-11-20", end_date="2026-11-20")
    assert len(records) == 2
    assert records[0].campaign_id == "12001"
    assert records[0].spend_cents == 45075
    assert records[0].actions["purchase"] == 18
    assert records[0].action_values_cents["purchase"] == 180000

    assert records[1].campaign_id == "12002"
    assert records[1].spend_cents == 20000


def test_meta_connector_rate_limit_backoff_and_header_parsing():
    """Validates throttling when Meta rate-limit headers exceed safe threshold."""
    rate_limiter = TokenBucketRateLimiter()

    # Meta header showing 92% call count usage
    usage_hdr = json.dumps({"12345": [{"call_count": 92, "total_cputime": 40, "total_time": 50, "estimated_time_to_regain_access": 1}]})
    delay = rate_limiter.update_from_meta_headers(usage_hdr)
    assert delay >= 5.0  # Safe backoff delay triggered


def test_circuit_breaker_state_transitions():
    """Validates CircuitBreaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=0.1, half_open_success_threshold=2)

    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.can_execute() is True

    # 3 failures trip the breaker
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.STATE_CLOSED
    cb.record_failure()
    assert cb.state == CircuitBreaker.STATE_OPEN
    assert cb.can_execute() is False

    # Wait for recovery timeout
    import time
    time.sleep(0.12)
    assert cb.state == CircuitBreaker.STATE_HALF_OPEN
    assert cb.can_execute() is True

    # 2 consecutive successes in HALF_OPEN restore to CLOSED
    cb.record_success()
    assert cb.state == CircuitBreaker.STATE_HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitBreaker.STATE_CLOSED


def test_attribution_restatements_with_lookback_window():
    """Validates that retrospective revisions produce RestatementDelta records without corrupting history."""
    # Existing historical records synced 3 days ago
    key = "meta:act_123:camp_100:all:2026-11-18"
    existing_record = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_123",
        campaign_id="camp_100",
        campaign_name="Scale",
        date="2026-11-18",
        spend_cents=10000,
        impressions=5000,
        clicks=200,
        idempotency_key=key,
    )
    existing_map = {key: existing_record}

    # Meta now restates spend from 10000 cents ($100) to 12500 cents ($125) and clicks from 200 to 240
    restated_payload = {
        "data": [
            {
                "campaign_id": "camp_100",
                "campaign_name": "Scale",
                "spend": "125.00",
                "impressions": "5000",
                "clicks": "240",
                "actions": [],
                "action_values": [],
                "date_start": "2026-11-18",
                "date_stop": "2026-11-18",
            }
        ],
        "paging": {},
    }

    def mock_transport(req: Request) -> tuple[int, dict[str, str], bytes]:
        return 200, {"content-type": "application/json"}, json.dumps(restated_payload).encode("utf-8")

    connector = MetaAdsConnector(
        account_id="123",
        access_token="secret",
        transport=mock_transport,
    )

    new_records, deltas = connector.sync_with_lookback(
        start_date="2026-11-21",
        end_date="2026-11-21",
        existing_records=existing_map,
        lookback_window_days=7,
    )

    # Historical record was already existing, so not in new_records
    assert len(new_records) == 0
    # Two deltas emitted: spend_cents and clicks
    assert len(deltas) == 2
    delta_spend = next(d for d in deltas if d.metric_name == "spend_cents")
    assert delta_spend.original_value == 10000.0
    assert delta_spend.restated_value == 12500.0
    assert delta_spend.delta_value == 2500.0  # +$25.00 adjustment

    delta_clicks = next(d for d in deltas if d.metric_name == "clicks")
    assert delta_clicks.delta_value == 40.0


def test_google_ads_connector_cost_micros_conversion():
    """Validates GAQL SearchStream parsing and cost_micros to integer cents."""
    search_stream_response = [
        {
            "results": [
                {
                    "campaign": {"id": "987654", "name": "Brand Search"},
                    "segments": {"date": "2026-11-20"},
                    "metrics": {
                        "costMicros": 125500000,  # $125.50 = 125,500,000 micros
                        "impressions": 4000,
                        "clicks": 320,
                        "conversions": 15.0,
                        "conversionsValue": 1500.0,
                    },
                }
            ]
        }
    ]

    def mock_transport(req: Request) -> tuple[int, dict[str, str], bytes]:
        return 200, {"content-type": "application/json"}, json.dumps(search_stream_response).encode("utf-8")

    connector = GoogleAdsConnector(
        customer_id="123-456-7890",
        developer_token="dev_tok_xyz",
        oauth_token="oauth_tok_abc",
        transport=mock_transport,
    )

    records, _ = connector.fetch_records(start_date="2026-11-20", end_date="2026-11-20")
    assert len(records) == 1
    rec = records[0]
    assert rec.campaign_id == "987654"
    assert rec.campaign_name == "Brand Search"
    assert rec.spend_cents == 12550  # Exactly 12,550 cents ($125.50)
    assert rec.impressions == 4000
    assert rec.clicks == 320
    assert rec.actions["conversions"] == 15
    assert rec.action_values_cents["conversions"] == 150000


def test_ga4_connector_run_report():
    """Validates GA4 runReport parsing, YYYYMMDD date normalization, and conversion mapping."""
    ga4_response = {
        "rowCount": 1,
        "rows": [
            {
                "dimensionValues": [
                    {"value": "20261120"},
                    {"value": "Organic Search"},
                    {"value": "Summer_Promo"},
                ],
                "metricValues": [
                    {"value": "1200"},   # sessions
                    {"value": "45"},     # conversions
                    {"value": "3500.50"}, # totalRevenue
                    {"value": "980"},    # activeUsers
                ],
            }
        ],
    }

    def mock_transport(req: Request) -> tuple[int, dict[str, str], bytes]:
        return 200, {"content-type": "application/json"}, json.dumps(ga4_response).encode("utf-8")

    connector = GA4Connector(
        property_id="properties/321654",
        credentials_json="dummy_creds_json",
        transport=mock_transport,
    )

    records, cursor = connector.fetch_records(start_date="2026-11-20", end_date="2026-11-20")
    assert len(records) == 1
    conv = records[0]
    assert conv.platform == "ga4"
    assert conv.event_time.startswith("2026-11-20")
    assert conv.revenue_cents == 350050  # $3,500.50
    assert conv.channel == "Organic Search"
    assert conv.campaign_id == "Summer_Promo"
    assert cursor is None


def test_secret_hygiene_and_masking():
    """Validates SecretMasker guarantees credentials never appear in plain text."""
    secret_key = "super_secret_live_key_999888"
    SecretMasker.register(secret_key)

    raw_log = f"Failed to authenticate with token {secret_key} on endpoint"
    masked = SecretMasker.mask(raw_log)

    assert secret_key not in masked
    assert "sup***88" in masked or "***REDACTED***" in masked
    SecretMasker.clear()

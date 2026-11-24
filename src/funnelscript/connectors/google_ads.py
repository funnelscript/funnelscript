"""FunnelScript Google Ads (Search Stream API) Ingestion Connector.

Queries Google Ads API (`googleAds:searchStream`) for search and display campaign performance.
Features:
- GAQL (Google Ads Query Language) stream processing.
- `cost_micros` ($10^-6$) conversion to integer cents ($10^-2$).
- Conversions and conversion value extraction.
- Secret hygiene for developer token and customer IDs.
- 100% offline mock transport support for CI testing.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from funnelscript.connectors.base import (
    BasePollingConnector,
    CircuitBreaker,
    SecretMasker,
    TokenBucketRateLimiter,
    execute_with_retry,
)
from funnelscript.connectors.models import CanonicalAdSpendRecord

GOOGLE_ADS_API_VERSION = "v16"
GOOGLE_ADS_BASE_URL = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"


class GoogleAdsConnector(BasePollingConnector):
    """Polling connector for Google Ads Search Stream API."""

    def __init__(
        self,
        customer_id: str,
        developer_token: str | None = None,
        oauth_token: str | None = None,
        transport: Callable[[Request], tuple[int, dict[str, str], bytes]] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        clean_cid = customer_id.replace("-", "").strip()
        super().__init__(
            platform_name="google_ads",
            account_id=clean_cid,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )
        dev_token = developer_token or os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        token = oauth_token or os.environ.get("GOOGLE_ADS_OAUTH_TOKEN", "")
        self._dev_token = dev_token
        self._oauth_token = token
        SecretMasker.register(dev_token)
        SecretMasker.register(token)
        self._transport = transport or self._default_transport

    def _default_transport(self, req: Request) -> tuple[int, dict[str, str], bytes]:
        try:
            with urlopen(req, timeout=30.0) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.status, headers, resp.read()
        except HTTPError as exc:
            headers = {k.lower(): v for k, v in exc.headers.items()}
            return exc.code, headers, exc.read()

    def fetch_records(
        self,
        start_date: str,
        end_date: str,
        cursor: str | None = None,
    ) -> tuple[list[CanonicalAdSpendRecord], str | None]:
        """Queries Google Ads searchStream API using GAQL."""
        gaql_query = (
            f"SELECT campaign.id, campaign.name, segments.date, "
            f"metrics.cost_micros, metrics.impressions, metrics.clicks, "
            f"metrics.conversions, metrics.conversions_value "
            f"FROM campaign "
            f"WHERE segments.date BETWEEN '{start_date}' AND '{end_date}' "
            f"ORDER BY segments.date ASC"
        )

        url = f"{GOOGLE_ADS_BASE_URL}/customers/{self.account_id}/googleAds:searchStream"
        req = Request(
            url,
            data=json.dumps({"query": gaql_query}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "FunnelScript-Connector/1.0",
                "developer-token": self._dev_token,
                "Authorization": f"Bearer {self._oauth_token}",
            },
            method="POST",
        )

        def call_api() -> tuple[int, dict[str, str], bytes]:
            return self._transport(req)

        status_code, _headers, body = execute_with_retry(
            call_api,
            max_retries=3,
            initial_backoff=0.2,
            circuit_breaker=self.circuit_breaker,
        )

        if status_code >= 400:
            error_data = {}
            try:
                error_data = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            msg = SecretMasker.mask(f"Google Ads API error {status_code}: {error_data}")
            raise RuntimeError(msg)

        data = json.loads(body.decode("utf-8"))
        batches = data if isinstance(data, list) else [data]
        records: list[CanonicalAdSpendRecord] = []

        for batch in batches:
            for result in batch.get("results", []):
                campaign = result.get("campaign", {})
                c_id = str(campaign.get("id", "unknown"))
                c_name = campaign.get("name", "Unknown Campaign")
                segments = result.get("segments", {})
                d_date = segments.get("date", start_date)

                metrics = result.get("metrics", {})
                cost_micros = int(metrics.get("costMicros", 0))
                # 1 micro = 10^-6 currency unit; 1 cent = 10^-2 currency unit
                # cost_cents = cost_micros / 10000
                spend_cents = round(cost_micros / 10000.0)

                impressions = int(metrics.get("impressions", 0))
                clicks = int(metrics.get("clicks", 0))
                conversions = int(float(metrics.get("conversions", 0)))
                conv_value = float(metrics.get("conversionsValue", 0.0))
                conv_value_cents = round(conv_value * 100)

                actions = {"conversions": conversions} if conversions > 0 else {}
                action_values = {"conversions": conv_value_cents} if conv_value_cents > 0 else {}

                rec = CanonicalAdSpendRecord(
                    platform=self.platform_name,
                    account_id=self.account_id,
                    campaign_id=c_id,
                    campaign_name=c_name,
                    date=d_date,
                    spend_cents=spend_cents,
                    currency="USD",
                    impressions=impressions,
                    clicks=clicks,
                    actions=actions,
                    action_values_cents=action_values,
                )
                records.append(rec)

        return records, None

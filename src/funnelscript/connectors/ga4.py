"""FunnelScript Google Analytics 4 (GA4 Data API) Ingestion Connector.

Queries GA4 Data API v1beta (`runReport`) for traffic, conversion, and e-commerce revenue data.
Features:
- Channel grouping and campaign breakdown extraction.
- Date format normalization (YYYYMMDD to YYYY-MM-DD).
- Exact minor currency unit conversion (cents).
- Secret hygiene for OAuth credentials.
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
from funnelscript.connectors.models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
)

GA4_API_BASE_URL = "https://analyticsdata.googleapis.com/v1beta"


class GA4Connector(BasePollingConnector):
    """Polling connector for Google Analytics 4 Data API."""

    def __init__(
        self,
        property_id: str,
        credentials_json: str | None = None,
        transport: Callable[[Request], tuple[int, dict[str, str], bytes]] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        super().__init__(
            platform_name="ga4",
            account_id=property_id,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )
        creds = credentials_json or os.environ.get("GA4_CREDENTIALS_JSON", "")
        self._credentials_json = creds
        SecretMasker.register(creds)
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
    ) -> tuple[list[CanonicalConversionEvent | CanonicalAdSpendRecord], str | None]:
        """Queries GA4 Data API runReport endpoint."""
        offset = int(cursor) if cursor else 0
        limit = 100

        body_payload = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [
                {"name": "date"},
                {"name": "sessionDefaultChannelGroup"},
                {"name": "campaignName"},
            ],
            "metrics": [
                {"name": "sessions"},
                {"name": "conversions"},
                {"name": "totalRevenue"},
                {"name": "activeUsers"},
            ],
            "offset": offset,
            "limit": limit,
        }

        url = f"{GA4_API_BASE_URL}/properties/{self.account_id}:runReport"
        req = Request(
            url,
            data=json.dumps(body_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "FunnelScript-Connector/1.0",
                "Authorization": f"Bearer {self._credentials_json}",
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
            msg = SecretMasker.mask(f"GA4 Data API error {status_code}: {error_data}")
            raise RuntimeError(msg)

        data = json.loads(body.decode("utf-8"))
        rows = data.get("rows", [])
        records: list[CanonicalConversionEvent | CanonicalAdSpendRecord] = []

        for row in rows:
            dim_values = [d.get("value", "") for d in row.get("dimensionValues", [])]
            metric_values = [m.get("value", "0") for m in row.get("metricValues", [])]

            raw_date = dim_values[0] if len(dim_values) > 0 else "19700101"
            # Normalize YYYYMMDD to YYYY-MM-DD
            if len(raw_date) == 8 and raw_date.isdigit():
                d_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
            else:
                d_str = raw_date

            channel = dim_values[1] if len(dim_values) > 1 else "Direct"
            campaign = dim_values[2] if len(dim_values) > 2 else "(not set)"

            sessions = int(metric_values[0]) if len(metric_values) > 0 else 0
            conversions = int(float(metric_values[1])) if len(metric_values) > 1 else 0
            revenue_val = float(metric_values[2]) if len(metric_values) > 2 else 0.0
            revenue_cents = round(revenue_val * 100)

            # Emit CanonicalConversionEvent
            conv_event = CanonicalConversionEvent(
                platform=self.platform_name,
                external_id=f"ga4_{self.account_id}_{channel}_{campaign}_{d_str}",
                event_name="Purchase" if revenue_cents > 0 else "Key_Event",
                event_time=f"{d_str}T00:00:00Z",
                attribution_window="ga4_data_driven",
                revenue_cents=revenue_cents,
                currency="USD",
                entity_stage="customer" if revenue_cents > 0 else "prospect",
                channel=channel,
                campaign_id=campaign,
                properties={"sessions": sessions, "conversions": conversions},
            )
            records.append(conv_event)

        total_rows = int(data.get("rowCount", len(rows)))
        next_offset = offset + len(rows)
        next_cursor = str(next_offset) if next_offset < total_rows and len(rows) == limit else None

        return records, next_cursor

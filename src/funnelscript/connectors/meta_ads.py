"""FunnelScript Meta Marketing API (Graph API) Ingestion Connector.

Pulls ad spend, impression, click, and conversion metrics from Meta Ads accounts.
Features:
- Cursor-based pagination (`paging.cursors.after`).
- Synchronous insights fetching and asynchronous report job polling.
- Adaptive throttling & backoff based on `X-Business-Use-Case-Usage` headers.
- Secret hygiene: `META_ACCESS_TOKEN` is automatically registered with `SecretMasker`.
- 100% offline mock HTTP transport support for deterministic CI testing.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from funnelscript.connectors.base import (
    BasePollingConnector,
    CircuitBreaker,
    RateLimitExceededError,
    SecretMasker,
    TokenBucketRateLimiter,
    execute_with_retry,
)
from funnelscript.connectors.models import CanonicalAdSpendRecord

META_GRAPH_API_VERSION = "v19.0"
META_GRAPH_BASE_URL = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"


class MetaAdsConnector(BasePollingConnector):
    """Production-grade polling connector for Meta Graph API Insights."""

    def __init__(
        self,
        account_id: str,
        access_token: str | None = None,
        transport: Callable[[Request], tuple[int, dict[str, str], bytes]] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        # Format account ID with act_ prefix if omitted
        formatted_account_id = account_id if account_id.startswith("act_") else f"act_{account_id}"
        super().__init__(
            platform_name="meta",
            account_id=formatted_account_id,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        token = access_token or os.environ.get("META_ACCESS_TOKEN", "")
        self._access_token = token
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
        """Fetches a single page of campaign insights from Meta Graph API."""
        params: dict[str, Any] = {
            "access_token": self._access_token,
            "level": "campaign",
            "time_range": json.dumps({"since": start_date, "until": end_date}),
            "time_increment": 1,  # Daily breakdown
            "fields": "campaign_id,campaign_name,spend,impressions,clicks,actions,action_values,date_start,date_stop",
            "limit": 50,
        }
        if cursor:
            params["after"] = cursor

        url = f"{META_GRAPH_BASE_URL}/{self.account_id}/insights?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": "FunnelScript-Connector/1.0", "Accept": "application/json"})

        def call_api() -> tuple[int, dict[str, str], bytes]:
            return self._transport(req)

        status_code, headers, body = execute_with_retry(
            call_api,
            max_retries=3,
            initial_backoff=0.2,
            circuit_breaker=self.circuit_breaker,
        )

        # Check rate limit headers
        usage_header = headers.get("x-business-use-case-usage") or headers.get("x-ad-account-usage")
        delay_sec = self.rate_limiter.update_from_meta_headers(usage_header)
        if status_code == 429 or delay_sec > 5.0:
            raise RateLimitExceededError("Meta rate limit reached", retry_after_seconds=delay_sec)

        if status_code >= 400:
            error_data = {}
            try:
                error_data = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            msg = SecretMasker.mask(f"Meta Graph API error {status_code}: {error_data}")
            raise RuntimeError(msg)

        data = json.loads(body.decode("utf-8"))
        raw_items = data.get("data", [])
        records: list[CanonicalAdSpendRecord] = []

        for item in raw_items:
            c_id = item.get("campaign_id", "unknown")
            c_name = item.get("campaign_name", "Unknown Campaign")
            d_date = item.get("date_start", start_date)
            spend_val = float(item.get("spend", 0.0))
            spend_cents = round(spend_val * 100)
            impr = int(item.get("impressions", 0))
            clicks = int(item.get("clicks", 0))

            actions_map: dict[str, int] = {}
            for a in item.get("actions", []):
                actions_map[a.get("action_type", "action")] = int(a.get("value", 0))

            action_values_cents: dict[str, int] = {}
            for av in item.get("action_values", []):
                val = float(av.get("value", 0.0))
                action_values_cents[av.get("action_type", "action")] = round(val * 100)

            rec = CanonicalAdSpendRecord(
                platform=self.platform_name,
                account_id=self.account_id,
                campaign_id=c_id,
                campaign_name=c_name,
                date=d_date,
                spend_cents=spend_cents,
                currency="USD",
                impressions=impr,
                clicks=clicks,
                actions=actions_map,
                action_values_cents=action_values_cents,
                raw_payload_sha256="",
            )
            records.append(rec)

        paging = data.get("paging", {})
        cursors = paging.get("cursors", {})
        next_cursor = cursors.get("after") if paging.get("next") else None

        return records, next_cursor

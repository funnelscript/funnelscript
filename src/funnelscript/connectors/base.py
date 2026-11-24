"""FunnelScript Base Ingestion Connector Contracts & Resilience Infrastructure.

Defines:
- BasePollingConnector: Abstract contract for pulling ad platform telemetry with pagination,
  rate-limit backoff, and retroactive attribution restatement handling.
- BaseWebhookAdapter: Abstract contract for real-time push ingestion with constant-time HMAC verification.
- Resilience components: TokenBucketRateLimiter, CircuitBreaker, ExponentialBackoff, and SecretMasker.
"""

from __future__ import annotations

import abc
import json
import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, TypeVar

from funnelscript.connectors.models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
    RestatementDelta,
)

logger = logging.getLogger("funnelscript.connectors")

T = TypeVar("T")


class SecretMasker:
    """Masks secret tokens and sensitive keys to prevent credential leakage in logs or exceptions."""

    _registered_secrets: ClassVar[set[str]] = set()

    @classmethod
    def register(cls, secret: str | None) -> None:
        if secret and len(secret) >= 4:
            cls._registered_secrets.add(secret.strip())

    @classmethod
    def mask(cls, text: str) -> str:
        masked = text
        for secret in cls._registered_secrets:
            if secret in masked:
                replacement = f"{secret[:3]}***{secret[-2:]}" if len(secret) > 6 else "***REDACTED***"
                masked = masked.replace(secret, replacement)
        return masked

    @classmethod
    def clear(cls) -> None:
        cls._registered_secrets.clear()


class RateLimitExceededError(Exception):
    """Raised when an API rate limit is reached and retry attempts are exhausted."""

    def __init__(self, message: str, retry_after_seconds: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class CircuitBreakerOpenError(Exception):
    """Raised when request is rejected because the circuit breaker is in OPEN state."""


class CircuitBreaker:
    """State machine guarding against cascading failures to external ad/payment APIs."""

    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 2,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self._state = self.STATE_CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_state_change = time.time()

    @property
    def state(self) -> str:
        if self._state == self.STATE_OPEN and time.time() - self._last_state_change >= self.recovery_timeout_seconds:
            self._transition_to(self.STATE_HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: str) -> None:
        self._state = new_state
        self._last_state_change = time.time()
        self._consecutive_successes = 0
        if new_state == self.STATE_CLOSED:
            self._consecutive_failures = 0

    def can_execute(self) -> bool:
        return self.state != self.STATE_OPEN

    def record_success(self) -> None:
        current = self.state
        if current == self.STATE_HALF_OPEN:
            self._consecutive_successes += 1
            if self._consecutive_successes >= self.half_open_success_threshold:
                self._transition_to(self.STATE_CLOSED)
        elif current == self.STATE_CLOSED:
            self._consecutive_failures = 0

    def record_failure(self) -> None:
        current = self.state
        if current == self.STATE_HALF_OPEN:
            self._transition_to(self.STATE_OPEN)
        elif current == self.STATE_CLOSED:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._transition_to(self.STATE_OPEN)


class TokenBucketRateLimiter:
    """Token bucket rate limiter supporting header-based dynamic quota throttling."""

    def __init__(self, capacity: int = 100, refill_rate_per_sec: float = 10.0) -> None:
        self.capacity = float(capacity)
        self.refill_rate = refill_rate_per_sec
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def consume(self, tokens: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def update_from_meta_headers(self, usage_header: str | None) -> float:
        """Parses Meta 'X-Business-Use-Case-Usage' header and returns recommended delay in seconds."""
        if not usage_header:
            return 0.0
        try:
            parsed = json.loads(usage_header)
            max_pct = 0.0
            max_delay = 0.0
            # Meta format: {"<id>": [{"call_count": X, "total_cputime": Y, "total_time": Z, "estimated_time_to_regain_access": W}]}
            for metrics_list in parsed.values():
                for m in metrics_list:
                    usage = max(m.get("call_count", 0), m.get("total_cputime", 0), m.get("total_time", 0))
                    max_pct = max(max_pct, usage)
                    regain = float(m.get("estimated_time_to_regain_access", 0))
                    max_delay = max(max_delay, regain)

            if max_pct >= 90:
                return max(max_delay * 60.0, 5.0)  # regain is in minutes, convert or default
            if max_pct >= 80:
                return 2.0
            return 0.0
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return 0.0


def execute_with_retry[T](
    func: Callable[[], T],
    max_retries: int = 3,
    initial_backoff: float = 0.5,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
    circuit_breaker: CircuitBreaker | None = None,
) -> T:
    """Executes a callable with exponential backoff, jitter, and circuit breaker protection."""
    if circuit_breaker and not circuit_breaker.can_execute():
        raise CircuitBreakerOpenError("Circuit breaker is OPEN; refusing to execute request.")

    attempt = 0
    backoff = initial_backoff
    last_exc: Exception | None = None

    while attempt <= max_retries:
        try:
            res = func()
            if circuit_breaker:
                circuit_breaker.record_success()
            return res
        except (RateLimitExceededError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            if circuit_breaker:
                circuit_breaker.record_failure()
            attempt += 1
            if attempt > max_retries:
                break

            sleep_duration = getattr(exc, "retry_after_seconds", 0.0) or backoff
            if jitter:
                sleep_duration += random.uniform(0.0, 0.2 * sleep_duration)

            time.sleep(sleep_duration)
            backoff *= backoff_multiplier
        except Exception:
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise

    raise last_exc or RuntimeError("Max retries exceeded")


class BasePollingConnector(abc.ABC):
    """Abstract contract for periodic batch polling of external marketing platforms."""

    def __init__(
        self,
        platform_name: str,
        account_id: str,
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.platform_name = platform_name
        self.account_id = account_id
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    @abc.abstractmethod
    def fetch_records(
        self,
        start_date: str,
        end_date: str,
        cursor: str | None = None,
    ) -> tuple[list[CanonicalAdSpendRecord | CanonicalConversionEvent], str | None]:
        """Fetches a single page of telemetry records for the specified date range.

        Returns:
            (records, next_page_cursor)
        """

    def fetch_all(
        self,
        start_date: str,
        end_date: str,
        max_pages: int = 50,
    ) -> list[CanonicalAdSpendRecord | CanonicalConversionEvent]:
        """Fetches all pages of records using cursor pagination."""
        all_records: list[CanonicalAdSpendRecord | CanonicalConversionEvent] = []
        cursor: str | None = None
        pages = 0

        while pages < max_pages:
            records, next_cursor = self.fetch_records(start_date, end_date, cursor=cursor)
            all_records.extend(records)
            pages += 1
            if not next_cursor:
                break
            cursor = next_cursor

        return all_records

    def sync_with_lookback(
        self,
        start_date: str,
        end_date: str,
        existing_records: dict[str, CanonicalAdSpendRecord],
        lookback_window_days: int = 7,
    ) -> tuple[list[CanonicalAdSpendRecord], list[RestatementDelta]]:
        """Performs watermarked sync with historical lookback window.

        Compares newly fetched records against existing records in the lookback window.
        When an ad platform retroactively changes numbers, emits an auditable RestatementDelta
        rather than mutating existing records without a trace.
        """
        # Calculate extended start date including lookback
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        lookback_dt = start_dt - timedelta(days=lookback_window_days)
        extended_start_date = lookback_dt.strftime("%Y-%m-%d")

        pulled_records = self.fetch_all(extended_start_date, end_date)
        spend_records = [r for r in pulled_records if isinstance(r, CanonicalAdSpendRecord)]

        new_or_unchanged: list[CanonicalAdSpendRecord] = []
        deltas: list[RestatementDelta] = []
        now_iso = datetime.now(UTC).isoformat()

        for rec in spend_records:
            key = rec.idempotency_key
            if key in existing_records:
                old = existing_records[key]
                # Check for retroactive revisions in metrics
                if old.spend_cents != rec.spend_cents:
                    delta_cents = rec.spend_cents - old.spend_cents
                    deltas.append(
                        RestatementDelta(
                            platform=self.platform_name,
                            campaign_id=rec.campaign_id,
                            date=rec.date,
                            metric_name="spend_cents",
                            original_value=float(old.spend_cents),
                            restated_value=float(rec.spend_cents),
                            delta_value=float(delta_cents),
                            currency=rec.currency,
                            as_of_time=now_iso,
                        )
                    )
                if old.clicks != rec.clicks:
                    deltas.append(
                        RestatementDelta(
                            platform=self.platform_name,
                            campaign_id=rec.campaign_id,
                            date=rec.date,
                            metric_name="clicks",
                            original_value=float(old.clicks),
                            restated_value=float(rec.clicks),
                            delta_value=float(rec.clicks - old.clicks),
                            currency=None,
                            as_of_time=now_iso,
                        )
                    )
                if old.impressions != rec.impressions:
                    deltas.append(
                        RestatementDelta(
                            platform=self.platform_name,
                            campaign_id=rec.campaign_id,
                            date=rec.date,
                            metric_name="impressions",
                            original_value=float(old.impressions),
                            restated_value=float(rec.impressions),
                            delta_value=float(rec.impressions - old.impressions),
                            currency=None,
                            as_of_time=now_iso,
                        )
                    )
            else:
                new_or_unchanged.append(rec)

        return new_or_unchanged, deltas


class BaseWebhookAdapter(abc.ABC):
    """Abstract contract for receiving and verifying real-time webhooks (Stripe, Shopify)."""

    def __init__(self, platform_name: str) -> None:
        self.platform_name = platform_name

    @abc.abstractmethod
    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: dict[str, str],
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verifies cryptographic signature using constant-time comparison and timestamp tolerance."""

    @abc.abstractmethod
    def parse_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> list[CanonicalConversionEvent | CanonicalSettlementEvent]:
        """Parses verified raw webhook JSON into canonical conversion or settlement events."""

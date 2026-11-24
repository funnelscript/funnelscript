"""Governance Circuit Breaker for Concordia Agent Simulations.

Enforces sliding-window budget limits, financial transaction ceilings,
mutation velocities, and consecutive failure thresholds with fail-closed semantics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto


class CircuitBreakerStatus(Enum):
    ARMED = auto()
    TRIPPED = auto()
    BYPASSED = auto()


@dataclass
class WindowBucket:
    timestamp: float
    token_cost_usd: float
    financial_mutation_cents: int
    mutation_count: int


@dataclass
class GovernanceCircuitBreaker:
    """Sliding-window rate & financial budget limiter with fail-closed protection."""

    max_token_cost_usd: float = 5.00
    max_financial_mutation_cents: int = 100_000  # $1,000.00
    max_mutations_per_window: int = 50
    window_duration_seconds: float = 3600.0  # 1 hour
    max_failure_streak: int = 3

    status: CircuitBreakerStatus = CircuitBreakerStatus.ARMED
    tripped_reason: str | None = None
    tripped_at: float | None = None

    _buckets: list[WindowBucket] = field(default_factory=list)
    _failure_streak: int = 0

    def check_safety(self, proposed_financial_cents: int = 0) -> tuple[bool, str | None]:
        """Verify whether agent operations are permitted under current budget."""
        self._prune_expired_buckets()

        if self.status == CircuitBreakerStatus.TRIPPED:
            return False, f"Circuit Breaker is TRIPPED: {self.tripped_reason}"

        if self.status == CircuitBreakerStatus.BYPASSED:
            return True, None

        total_cost, total_financial, total_mutations = self._calculate_totals()

        if total_cost >= self.max_token_cost_usd:
            self.trip(f"Token spend ceiling of ${self.max_token_cost_usd:.2f} exceeded (spent: ${total_cost:.2f})")
            return False, self.tripped_reason

        # Proactive ceiling check: current + proposed
        if (total_financial + proposed_financial_cents) > self.max_financial_mutation_cents:
            self.trip(
                f"Financial mutation ceiling of ${self.max_financial_mutation_cents / 100:.2f} exceeded "
                f"(current: ${total_financial / 100:.2f}, proposed: ${proposed_financial_cents / 100:.2f})"
            )
            return False, self.tripped_reason

        if total_mutations >= self.max_mutations_per_window:
            self.trip(f"Mutation velocity exceeded ({self.max_mutations_per_window} actions per window)")
            return False, self.tripped_reason

        if self._failure_streak >= self.max_failure_streak:
            self.trip(f"Failure streak threshold tripped ({self._failure_streak} consecutive errors)")
            return False, self.tripped_reason

        return True, None

    def record_usage(
        self,
        token_cost_usd: float = 0.0,
        financial_mutation_cents: int = 0,
        is_failure: bool = False,
    ) -> None:
        """Record usage and update sliding window state."""
        allowed, reason = self.check_safety(proposed_financial_cents=financial_mutation_cents)
        if not allowed and self.status == CircuitBreakerStatus.TRIPPED:
            raise PermissionError(f"Operation blocked: {reason}")

        if is_failure:
            self._failure_streak += 1
        else:
            self._failure_streak = 0

        self._buckets.append(
            WindowBucket(
                timestamp=time.time(),
                token_cost_usd=token_cost_usd,
                financial_mutation_cents=financial_mutation_cents,
                mutation_count=1 if (financial_mutation_cents > 0 or token_cost_usd > 0) else 0,
            )
        )

        # Immediate post-record check to trip if boundary exceeded
        self.check_safety()

    def trip(self, reason: str) -> None:
        """Trip circuit breaker immediately into fail-closed state."""
        self.status = CircuitBreakerStatus.TRIPPED
        self.tripped_reason = reason
        self.tripped_at = time.time()

    def reset(self, admin_key: str) -> bool:
        """Authorized supervisor reset."""
        if admin_key != "MASTER_OVERRIDE_KEY":
            return False
        self.status = CircuitBreakerStatus.ARMED
        self.tripped_reason = None
        self.tripped_at = None
        self._failure_streak = 0
        self._buckets.clear()
        return True

    def _prune_expired_buckets(self) -> None:
        cutoff = time.time() - self.window_duration_seconds
        self._buckets = [b for b in self._buckets if b.timestamp >= cutoff]

    def _calculate_totals(self) -> tuple[float, int, int]:
        cost = sum(b.token_cost_usd for b in self._buckets)
        fin = sum(b.financial_mutation_cents for b in self._buckets)
        mut = sum(b.mutation_count for b in self._buckets)
        return cost, fin, mut

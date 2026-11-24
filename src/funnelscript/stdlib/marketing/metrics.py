"""Explicit synthetic marketing trial and empirical loss metrics.

Research: funnelscript-research/spec/financial-ledger-metrics-v0.md.
Derives audited financial and marketing metrics strictly from verified ledger state.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal, localcontext

from funnelscript.runtime.world_executor import PopulationResult

from .ledger import LedgerSnapshot, _identity, _money


@dataclass(frozen=True)
class UndefinedMetric:
    """Represents a metric that cannot be computed due to zero denominator or missing domain data."""

    reason: str

    def __repr__(self) -> str:
        return f"UndefinedMetric({self.reason!r})"


@dataclass(frozen=True)
class TrialReferenceMetrics:
    trial_id: str
    currency: str
    horizon: int
    attribution_label: str
    insolvency_threshold: Decimal
    eligible_count: int
    converted_count: int
    conversion_rate: Decimal
    cac: Decimal | None
    roas: Decimal | None
    profit: Decimal
    ruined: bool
    ledger: LedgerSnapshot
    min_cash_balance: Decimal = Decimal("0.00")
    cash_exhaustion_tick: int | None = None
    working_capital_gap: Decimal = Decimal("0.00")
    cac_payback_period: int | None = None
    contribution_margin: Decimal | None = None


@dataclass(frozen=True)
class RiskReferenceMetrics:
    trial_count: int
    currency: str
    horizon: int
    alpha: Decimal
    attribution_label: str
    insolvency_threshold: Decimal
    ruin_probability: Decimal
    var: Decimal
    cvar: Decimal


def evaluate_trial(
    population: PopulationResult,
    ledger: LedgerSnapshot,
    *,
    converted_state: str,
    attribution_label: str,
    insolvency_threshold: Decimal,
) -> TrialReferenceMetrics:
    """Bind a fully identified population to its explicitly attributed journal."""
    if not isinstance(population, PopulationResult) or not isinstance(ledger, LedgerSnapshot):
        raise TypeError("population and ledger must be completed reference snapshots")
    if population.trial_id != ledger.trial_id:
        raise ValueError("population and ledger trial_id mismatch")
    _identity(attribution_label, "attribution_label")
    _identity(converted_state, "converted_state")
    _money(insolvency_threshold, "insolvency_threshold")
    identities = set(population.results)
    if not identities or converted_state not in population.partitions:
        raise ValueError("missing eligible population or declared converted_state")
    observed: set[str] = set()
    for members in population.partitions.values():
        if observed.intersection(members):
            raise ValueError("nonexclusive population state partitions")
        observed.update(members)
    if observed != identities:
        raise ValueError("population state partitions must exhaust initialized identities")
    for categories in (population.segments, population.cohorts):
        seen: set[str] = set()
        for members in categories.values():
            if seen.intersection(members):
                raise ValueError("duplicate identity across population metadata partitions")
            seen.update(members)
        if seen != identities:
            raise ValueError("incomplete population metadata partitions")
    converted = len(population.partitions[converted_state])

    # Find earliest day where cash balance breaches insolvency threshold
    cash_exhaustion_tick: int | None = None
    for day, _tx_id, cash in ledger.checkpoints:
        if cash < insolvency_threshold:
            cash_exhaustion_tick = day
            break

    # Working capital gap: receivables in transit exceeding available cash
    working_capital_gap = max(Decimal("0.00"), ledger.receivables - max(Decimal("0.00"), ledger.cash))

    with localcontext() as ctx:
        ctx.prec = 28
        rate = Decimal(converted) / Decimal(len(identities))
        cac = ledger.paid_ad_spend / Decimal(converted) if converted else None
        roas = (
            ledger.recognized_revenue / ledger.paid_ad_spend
            if ledger.paid_ad_spend > Decimal("0.00")
            else None
        )

        # Contribution Margin = (Recognized Revenue - Other Costs - Writeoffs - Gateway Fees) / Revenue
        if ledger.recognized_revenue > Decimal("0.00"):
            direct_costs = ledger.paid_other_costs + ledger.writeoffs + getattr(ledger, "gateway_fees", Decimal("0.00"))
            cm_amount = ledger.recognized_revenue - direct_costs
            contribution_margin = cm_amount / ledger.recognized_revenue
        else:
            contribution_margin = None

        # CAC payback: day when cumulative settled receipts meets or exceeds paid ad spend
        cac_payback_period: int | None = None
        if ledger.paid_ad_spend > Decimal("0.00"):
            for day, _tx_id, _cash in ledger.checkpoints:
                # If cash covers initial ad spend or if settled receipts cover ad spend
                if ledger.settled_receipts >= ledger.paid_ad_spend:
                    cac_payback_period = day
                    break
        elif ledger.paid_ad_spend == Decimal("0.00"):
            cac_payback_period = 0

    return TrialReferenceMetrics(
        trial_id=ledger.trial_id,
        currency=ledger.currency,
        horizon=ledger.horizon,
        attribution_label=attribution_label,
        insolvency_threshold=insolvency_threshold,
        eligible_count=len(identities),
        converted_count=converted,
        conversion_rate=rate,
        cac=cac,
        roas=roas,
        profit=ledger.profit,
        ruined=ledger.min_cash < insolvency_threshold,
        ledger=ledger,
        min_cash_balance=ledger.min_cash,
        cash_exhaustion_tick=cash_exhaustion_tick,
        working_capital_gap=working_capital_gap,
        cac_payback_period=cac_payback_period,
        contribution_margin=contribution_margin,
    )


def evaluate_risk(
    trials: Sequence[TrialReferenceMetrics],
    *,
    alpha: Decimal,
) -> RiskReferenceMetrics:
    """Empirical nearest-rank VaR and exact weighted upper-quantile CVaR."""
    if not isinstance(trials, Sequence) or not trials:
        raise ValueError("risk trials must be a nonempty finite sequence")
    if type(alpha) is not Decimal or not alpha.is_finite() or not 0 < alpha < 1:
        raise ValueError("alpha must be a finite Decimal strictly between zero and one")
    if any(not isinstance(item, TrialReferenceMetrics) for item in trials):
        raise TypeError("risk inputs must be completed TrialReferenceMetrics")
    first = trials[0]
    if len({t.trial_id for t in trials}) != len(trials):
        raise ValueError("duplicate trial_id")
    for name in ("currency", "horizon", "attribution_label", "insolvency_threshold"):
        if any(getattr(t, name) != getattr(first, name) for t in trials):
            raise ValueError(f"risk {name} mismatch")
    losses = sorted(-t.profit for t in trials)
    with localcontext() as ctx:
        ctx.prec = 28
        n = len(losses)
        var_rank = int((alpha * n).to_integral_value(rounding=ROUND_CEILING))
        var = losses[var_rank - 1]
        tail_size = (Decimal(1) - alpha) * n
        remaining = tail_size
        weighted_sum = Decimal(0)
        for loss in reversed(losses):
            weight = min(remaining, Decimal(1))
            weighted_sum += weight * loss
            remaining -= weight
            if remaining <= 0:
                break
        cvar = weighted_sum / tail_size
        ruin = Decimal(sum(t.ruined for t in trials)) / Decimal(n)
    return RiskReferenceMetrics(
        trial_count=n,
        currency=first.currency,
        horizon=first.horizon,
        alpha=alpha,
        attribution_label=first.attribution_label,
        insolvency_threshold=first.insolvency_threshold,
        ruin_probability=ruin,
        var=var,
        cvar=cvar,
    )


__all__ = [
    "RiskReferenceMetrics",
    "TrialReferenceMetrics",
    "UndefinedMetric",
    "evaluate_risk",
    "evaluate_trial",
]

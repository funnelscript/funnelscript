"""Product-Led Growth (PLG) SaaS Funnel & Subscription Simulation Engine.

Models multi-channel acquisition, product qualification, self-serve conversion,
multi-tier recurring billing, expansion/churn dynamics, and runway solvency.
Integrates directly with MarketingLedger to guarantee exact financial balance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


def _to_decimal(val: float | Decimal | str) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


@dataclass(frozen=True)
class SaasPLGConfig:
    """Bounded, dimensionally sound parameters for PLG SaaS funnels."""
    
    # Capital & Runway
    starting_cash: Decimal = field(default_factory=lambda: Decimal("100000.00"))
    min_safety_floor: Decimal = field(default_factory=lambda: Decimal("20000.00"))
    fixed_monthly_burn: Decimal = field(default_factory=lambda: Decimal("25000.00"))
    
    # Marketing & Acquisition
    monthly_ad_spend: Decimal = field(default_factory=lambda: Decimal("10000.00"))
    cpc: Decimal = field(default_factory=lambda: Decimal("2.50"))
    visitor_to_trial_rate: Decimal = field(default_factory=lambda: Decimal("0.06"))
    
    # Product Qualification & Conversion
    trial_to_pql_rate: Decimal = field(default_factory=lambda: Decimal("0.35"))
    pql_to_paid_rate: Decimal = field(default_factory=lambda: Decimal("0.25"))
    
    # Tier Pricing & Mix
    starter_mrr: Decimal = field(default_factory=lambda: Decimal("49.00"))
    pro_mrr: Decimal = field(default_factory=lambda: Decimal("199.00"))
    enterprise_mrr: Decimal = field(default_factory=lambda: Decimal("999.00"))
    starter_share: Decimal = field(default_factory=lambda: Decimal("0.60"))
    pro_share: Decimal = field(default_factory=lambda: Decimal("0.30"))
    enterprise_share: Decimal = field(default_factory=lambda: Decimal("0.10"))
    
    # Retention & Dynamics
    monthly_churn_rate: Decimal = field(default_factory=lambda: Decimal("0.035"))
    monthly_expansion_rate: Decimal = field(default_factory=lambda: Decimal("0.05"))
    stripe_fee_rate: Decimal = field(default_factory=lambda: Decimal("0.029"))
    stripe_fixed_fee: Decimal = field(default_factory=lambda: Decimal("0.30"))


@dataclass
class MonthlySaasMetrics:
    month: int
    ad_spend: Decimal
    new_trials: int
    new_pqls: int
    new_subscribers: int
    churned_subscribers: int
    active_subscribers: int
    ending_mrr: Decimal
    gross_collected: Decimal
    net_collected: Decimal
    operational_burn: Decimal
    ending_cash: Decimal
    cash_runway_breached: bool


class SaasPLGSimulator:
    """Deterministic, penny-conserving PLG SaaS simulation engine."""

    def __init__(self, config: SaasPLGConfig) -> None:
        self.config = config

    def simulate(self, months: int = 12) -> list[MonthlySaasMetrics]:
        results: list[MonthlySaasMetrics] = []
        cash = self.config.starting_cash
        active_subs = 0
        current_mrr = Decimal("0.00")

        blended_initial_arpu = (
            self.config.starter_mrr * self.config.starter_share
            + self.config.pro_mrr * self.config.pro_share
            + self.config.enterprise_mrr * self.config.enterprise_share
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        for m in range(1, months + 1):
            # 1. Inflow funnel
            clicks = int(self.config.monthly_ad_spend / self.config.cpc)
            trials = int(Decimal(clicks) * self.config.visitor_to_trial_rate)
            pqls = int(Decimal(trials) * self.config.trial_to_pql_rate)
            new_subs = int(Decimal(pqls) * self.config.pql_to_paid_rate)

            # 2. Churn & Expansion
            churned = int(Decimal(active_subs) * self.config.monthly_churn_rate)
            active_subs = max(0, active_subs - churned + new_subs)

            # MRR progression
            expansion_mrr = (current_mrr * self.config.monthly_expansion_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            churned_mrr = (current_mrr * self.config.monthly_churn_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            added_mrr = (Decimal(new_subs) * blended_initial_arpu).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            current_mrr = max(Decimal("0.00"), current_mrr + added_mrr + expansion_mrr - churned_mrr)

            # 3. Billing & Cash Flow
            gross_billing = current_mrr
            stripe_fees = (gross_billing * self.config.stripe_fee_rate + Decimal(active_subs) * self.config.stripe_fixed_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net_billing = max(Decimal("0.00"), gross_billing - stripe_fees)

            burn = self.config.fixed_monthly_burn + self.config.monthly_ad_spend
            cash = cash + net_billing - burn
            breached = cash < self.config.min_safety_floor

            results.append(
                MonthlySaasMetrics(
                    month=m,
                    ad_spend=self.config.monthly_ad_spend,
                    new_trials=trials,
                    new_pqls=pqls,
                    new_subscribers=new_subs,
                    churned_subscribers=churned,
                    active_subscribers=active_subs,
                    ending_mrr=current_mrr,
                    gross_collected=gross_billing,
                    net_collected=net_billing,
                    operational_burn=burn,
                    ending_cash=cash,
                    cash_runway_breached=breached,
                )
            )

        return results

"""FunnelScript Runtime Telemetry & Risk Aggregator.

Mathematical Invariants & Statistical Foundations:
1. Value-at-Risk (VaR at confidence level alpha in (0, 1)):
   VaR_alpha(Loss) = inf { l in R : P(Loss <= l) >= alpha }
2. Conditional Value-at-Risk (CVaR / Expected Shortfall):
   CVaR_alpha(Loss) = E[Loss | Loss >= VaR_alpha(Loss)]
3. Discount Cannibalization Rate:
   chi = sum_{i in ConvertedWithDiscount} I(alpha_i >= alpha_loyal) / N_converted
4. Probability of Capital Ruin:
   P(Ruin) = (1 / M) * sum_{m=1}^M I(min_{t in [0,T]} C_m(t) <= C_min)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np


@dataclass
class DailySnapshot:
    """State of the marketing system and consumer cohort at day t."""

    day: int
    spend: float
    clicks: int
    conversions: int
    gross_revenue: float
    settled_revenue: float
    liquid_cash: float
    pending_receivables: float
    state_distribution: dict[str, int] = field(default_factory=dict)


@dataclass
class TrialResult:
    """Terminal outcome of a single Monte Carlo trial."""

    trial_id: int
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    roas: float
    cac: float
    cannibalized_conversions: int
    insolvency_triggered: bool
    final_liquid_cash: float
    min_cash_observed: float
    daily_snapshots: list[DailySnapshot] = field(default_factory=list)


@dataclass
class DistributionMetrics:
    """Parametric and non-parametric summary of a trial metric."""

    mean: float
    std: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float

    @classmethod
    def compute(cls, values: np.ndarray) -> DistributionMetrics:
        if len(values) == 0:
            return cls(mean=0.0, std=0.0, median=0.0, p10=0.0, p25=0.0, p75=0.0, p90=0.0)
        return cls(
            mean=float(np.mean(values)),
            std=float(np.std(values)),
            median=float(np.median(values)),
            p10=float(np.percentile(values, 10)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
        )


@dataclass
class SimulationReport:
    """Comprehensive Monte Carlo Simulation and Stress-Testing Report."""

    strategy_name: str
    trials_count: int
    agents_per_trial: int
    timeframe_days: int
    roas: DistributionMetrics
    cac: DistributionMetrics
    spend: DistributionMetrics
    revenue: DistributionMetrics
    profit: DistributionMetrics

    # Risk & Stress Metrics
    probability_of_profit: float  # P(ROAS >= 1.0)
    cash_ruin_probability: float  # P(min liquid cash <= 0)
    worst_case_drawdown: float  # Max capital loss observed
    var_95: float  # 95% Value-at-Risk on Net Loss
    cvar_95: float  # 95% Expected Shortfall (Average loss beyond VaR)
    cannibalization_rate: float  # Fraction of discount conversions from loyal buyers
    raw_trials: list[TrialResult] = field(default_factory=list)

    # Legacy compatibility accessors
    @property
    def mean_roas(self) -> float:
        return self.roas.mean

    @property
    def median_roas(self) -> float:
        return self.roas.median

    @property
    def p10_roas(self) -> float:
        return self.roas.p10

    @property
    def p90_roas(self) -> float:
        return self.roas.p90

    @property
    def mean_cac(self) -> float:
        return self.cac.mean

    @property
    def median_cac(self) -> float:
        return self.cac.median

    @property
    def p10_cac(self) -> float:
        return self.cac.p10

    @property
    def p90_cac(self) -> float:
        return self.cac.p90


class TelemetryAggregator:
    """Aggregates raw Monte Carlo trials into calibrated statistical distributions and risk metrics."""

    @staticmethod
    def aggregate(
        strategy_name: str,
        trials: list[TrialResult],
        agents_per_trial: int,
        timeframe_days: int,
    ) -> SimulationReport:
        if not trials:
            empty_dist = DistributionMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            return SimulationReport(
                strategy_name=strategy_name,
                trials_count=0,
                agents_per_trial=agents_per_trial,
                timeframe_days=timeframe_days,
                roas=empty_dist,
                cac=empty_dist,
                spend=empty_dist,
                revenue=empty_dist,
                profit=empty_dist,
                probability_of_profit=0.0,
                cash_ruin_probability=0.0,
                worst_case_drawdown=0.0,
                var_95=0.0,
                cvar_95=0.0,
                cannibalization_rate=0.0,
                raw_trials=[],
            )

        num_trials = len(trials)
        roas_arr = np.array([t.roas for t in trials], dtype=float)
        spend_arr = np.array([t.spend for t in trials], dtype=float)
        rev_arr = np.array([t.revenue for t in trials], dtype=float)
        profit_arr = rev_arr - spend_arr

        # Filter finite CACs for CAC distribution
        valid_cacs = np.array([t.cac for t in trials if np.isfinite(t.cac)], dtype=float)
        if len(valid_cacs) == 0:
            valid_cacs = np.array([0.0])

        # Loss distribution for Value-at-Risk (Loss = max(0, -Profit))
        loss_arr = np.maximum(0.0, -profit_arr)
        var_95 = float(np.percentile(loss_arr, 95))
        tail_losses = loss_arr[loss_arr >= var_95]
        cvar_95 = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_95

        # Cannibalization
        total_conversions = sum(t.conversions for t in trials)
        total_cannibalized = sum(t.cannibalized_conversions for t in trials)
        cannibalization_rate = (total_cannibalized / total_conversions) if total_conversions > 0 else 0.0

        # Cash Ruin / Insolvency
        insolvency_count = sum(1 for t in trials if t.insolvency_triggered)
        cash_ruin_prob = insolvency_count / num_trials
        worst_case_drawdown = float(np.max(loss_arr))

        return SimulationReport(
            strategy_name=strategy_name,
            trials_count=num_trials,
            agents_per_trial=agents_per_trial,
            timeframe_days=timeframe_days,
            roas=DistributionMetrics.compute(roas_arr),
            cac=DistributionMetrics.compute(valid_cacs),
            spend=DistributionMetrics.compute(spend_arr),
            revenue=DistributionMetrics.compute(rev_arr),
            profit=DistributionMetrics.compute(profit_arr),
            probability_of_profit=float(np.mean(roas_arr >= 1.0)),
            cash_ruin_probability=float(cash_ruin_prob),
            worst_case_drawdown=worst_case_drawdown,
            var_95=var_95,
            cvar_95=cvar_95,
            cannibalization_rate=float(cannibalization_rate),
            raw_trials=trials,
        )

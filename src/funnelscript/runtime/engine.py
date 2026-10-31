"""FunnelScript High-Performance Vectorized Simulation Engine.

Research Anchors & Prior Art:
- Gillespie, D. T. (1977). Exact stochastic simulation of coupled chemical reactions.
- Law, A. M., & Kelton, W. D. (2000). Simulation Modeling and Analysis.
- SIMD Array Broadcasting under NumPy 2.x Architecture.

Falsifiable Hypotheses:
- H_{3.1} (Vectorized Throughput): NumPy vectorized array operations execute >= 500,000
  agent-days per second without scalar Python agent-iteration overhead.
- H_{3.2} (Liquidity Starvation): When initial capital C(0) < Delta_{settle} * Spend_{daily},
  the engine halts ad spend prior to revenue settlement, correctly triggering insolvency.
- H_{3.3} (Conservation of Mass): For all days t in [0, T], sum_{s in States} N_s(t) == N_{total}.

Mathematical Invariants:
1. Conservation of Mass:
   sum_{s in S} N_s(t) = N_{total}  forall t in [0, T]
2. Dynamic Cash Flow & Settlement Delay:
   C(t) = C(t-1) - Spend(t) + SettledRevenue(t - Delta_{settle})
   Spend(t) = 0 if C(t) < C_{min}
"""

from __future__ import annotations

from enum import IntEnum
import numpy as np

from funnelscript.models import StrategyAST, TouchpointNode
from funnelscript.runtime.telemetry import (
    DailySnapshot,
    SimulationReport,
    TelemetryAggregator,
    TrialResult,
)


class StateCode(IntEnum):
    COLD = 0
    AWARE = 1
    CONSIDERING = 2
    CART_ABANDONED = 3
    CONVERTED = 4
    CHURNED = 5


STATE_NAMES = {
    StateCode.COLD: "COLD",
    StateCode.AWARE: "AWARE",
    StateCode.CONSIDERING: "CONSIDERING",
    StateCode.CART_ABANDONED: "CART_ABANDONED",
    StateCode.CONVERTED: "CONVERTED",
    StateCode.CHURNED: "CHURNED",
}


class SimulationEngine:
    """Vectorized Discrete-Event Simulation Engine for FunnelScript Strategy ASTs."""

    def __init__(
        self,
        ast: StrategyAST,
        average_order_value: float = 120.0,
        payment_fee_pct: float = 0.029,
        min_operational_reserve: float = 50.0,
    ) -> None:
        self.ast = ast
        self.aov = average_order_value
        self.fee_multiplier = 1.0 - payment_fee_pct
        self.min_reserve = min_operational_reserve

        self.touchpoints: dict[str, TouchpointNode] = {tp.id: tp for tp in ast.entities.touchpoints}
        self.total_budget = ast.entities.budgets.total_budget
        self.max_cpc = ast.entities.budgets.max_cpc_limit
        self.initial_cash = getattr(ast.entities.budgets, "initial_cash", 10000.0)
        self.settlement_delay = getattr(ast.entities.budgets, "settlement_delay_days", 3)

    def run(
        self,
        num_trials: int = 100,
        agents_count: int | None = None,
        seed: int = 42,
        record_trajectories: bool = True,
    ) -> SimulationReport:
        """Executes Monte Carlo trials with vectorized agent dynamics."""
        sim_params = self.ast.simulation_engine.parameters
        count = agents_count or int(sim_params.get("virtual_agents_count", 10000))
        timeframe_days = int(sim_params.get("timeframe_days", 14))
        sigma = float(sim_params.get("randomness_factor_sigma", 0.15))

        trials: list[TrialResult] = []

        for trial_idx in range(num_trials):
            trial_seed = seed + trial_idx
            res = self._execute_trial(
                trial_id=trial_idx,
                count=count,
                timeframe_days=timeframe_days,
                sigma=sigma,
                seed=trial_seed,
                record_trajectories=record_trajectories,
            )
            trials.append(res)

        return TelemetryAggregator.aggregate(
            strategy_name=self.ast.strategy_name,
            trials=trials,
            agents_per_trial=count,
            timeframe_days=timeframe_days,
        )

    def _execute_trial(
        self,
        trial_id: int,
        count: int,
        timeframe_days: int,
        sigma: float,
        seed: int,
        record_trajectories: bool,
    ) -> TrialResult:
        rng = np.random.default_rng(seed)

        # 1. Vectorized Agent Population Initialization
        primary_aud = self.ast.entities.audiences[0]
        base_affinity = primary_aud.attributes.brand_affinity
        base_price_sens = primary_aud.attributes.price_sensitivity
        base_fomo = primary_aud.attributes.fomo_index

        # Psychographic tensors: shape (count,)
        affinity = np.clip(rng.normal(loc=base_affinity, scale=0.15, size=count), 0.01, 0.99)
        price_sens = np.clip(rng.normal(loc=base_price_sens, scale=0.15, size=count), 0.01, 0.99)
        fomo = np.clip(rng.normal(loc=base_fomo, scale=0.15, size=count), 0.01, 0.99)
        wallet = rng.lognormal(mean=5.0, sigma=0.6, size=count)

        # State tensor: shape (count,) as int8
        initial_code = StateCode.COLD if primary_aud.type == "cold" else StateCode.AWARE
        state = np.full(count, initial_code, dtype=np.int8)

        # Financial tracking
        liquid_cash = float(self.initial_cash)
        min_cash_observed = liquid_cash
        insolvency_triggered = False
        total_spend = 0.0
        total_clicks = 0
        total_conversions = 0
        total_cannibalized = 0

        # Circular/buffered receivables schedule: pending_receivables[payout_day] = cash
        buffer_len = timeframe_days + self.settlement_delay + 10
        receivables_schedule = np.zeros(buffer_len, dtype=float)

        daily_budget = self.total_budget / timeframe_days
        agents_per_day = max(1, count // timeframe_days)

        snapshots: list[DailySnapshot] = []

        # Volatility shock
        volatility_factor = max(0.2, 1.0 + float(rng.normal(0.0, sigma)))

        # 2. Daily Multi-Scale Timeline Loop
        for day in range(timeframe_days):
            # A. Payout Settlement: Matured receivables arrive in cash account
            matured_cash = receivables_schedule[day]
            liquid_cash += matured_cash

            # B. Liquidity Check: Minimum operational reserve invariant
            if liquid_cash < self.min_reserve:
                insolvency_triggered = True

            # Determine spend headroom for today
            day_target_spend = min(daily_budget, max(0.0, liquid_cash - self.min_reserve), max(0.0, self.total_budget - total_spend))
            if day_target_spend < daily_budget * 0.50 and total_spend < self.total_budget:
                insolvency_triggered = True

            day_spend = 0.0
            day_clicks = 0
            day_conversions = 0

            # Today's fresh audience cohort slice
            slice_start = day * agents_per_day
            slice_end = min(count, (day + 1) * agents_per_day)
            day_indices = np.arange(slice_start, slice_end)

            # C. Execute Logic Flow Steps
            if day_target_spend > 0.0 and len(day_indices) > 0:
                for step in self.ast.logic_flow:
                    if not isinstance(step, dict):
                        continue

                    action = step.get("action")
                    if action == "TriggerTraffic":
                        via_id = step.get("via", "")
                        dest_id = step.get("destination", "")
                        tp_ad = self.touchpoints.get(via_id)
                        tp_dest = self.touchpoints.get(dest_id)
                        if not tp_ad or not tp_dest:
                            continue

                        effective_cpc = min(self.max_cpc, tp_ad.base_cpc * volatility_factor)
                        ad_score = tp_ad.ad_creative_score
                        base_ctr = 0.035

                        # Ad CTR vector calculation
                        slice_fomo = fomo[day_indices]
                        slice_state = state[day_indices]
                        p_click = np.clip(base_ctr * (1.0 + slice_fomo * ad_score), 0.001, 0.25)

                        eligible = slice_state == StateCode.COLD
                        clicked_mask = (rng.random(len(day_indices)) < p_click) & eligible
                        clicked_indices = day_indices[clicked_mask]
                        num_clicks = len(clicked_indices)
                        traffic_cost = num_clicks * effective_cpc

                        # Budget cap bounding
                        if traffic_cost > day_target_spend and effective_cpc > 0:
                            allowed_clicks = int(day_target_spend / effective_cpc)
                            clicked_indices = clicked_indices[:allowed_clicks]
                            num_clicks = allowed_clicks
                            traffic_cost = num_clicks * effective_cpc

                        if num_clicks > 0:
                            day_spend += traffic_cost
                            total_spend += traffic_cost
                            liquid_cash -= traffic_cost
                            min_cash_observed = min(min_cash_observed, liquid_cash)
                            day_clicks += num_clicks
                            total_clicks += num_clicks
                            state[clicked_indices] = StateCode.AWARE

                            # Conversion evaluation on landing page
                            base_cr = tp_dest.base_conversion_rate
                            dest_affinity = affinity[clicked_indices]
                            dest_price_sens = price_sens[clicked_indices]
                            dest_wallet = wallet[clicked_indices]

                            # Wallet constraint: wallet must be >= product AOV
                            can_afford = dest_wallet >= self.aov
                            p_buy = np.clip(base_cr * (dest_affinity / dest_price_sens), 0.001, 0.60)
                            bought_mask = (rng.random(num_clicks) < p_buy) & can_afford

                            converted_sub = clicked_indices[bought_mask]
                            abandoned_sub = clicked_indices[~bought_mask]

                            state[converted_sub] = StateCode.CONVERTED
                            state[abandoned_sub] = StateCode.CART_ABANDONED

                            day_conversions += len(converted_sub)
                            total_conversions += len(converted_sub)

                    elif step.get("type") == "ConditionalBranch":
                        condition = step.get("condition", {})
                        if condition.get("user_action") == "AbandonCart":
                            for branch in step.get("true_branch", []):
                                if branch.get("action") == "ExecuteRetargeting":
                                    payload = branch.get("payload", {})
                                    discount_pct = float(payload.get("discount_percentage", 0.0)) / 100.0
                                    boost = float(branch.get("expected_impact", {}).get("conversion_boost", 0.02))

                                    abandoned_indices = np.where(state == StateCode.CART_ABANDONED)[0]
                                    if len(abandoned_indices) == 0:
                                        continue

                                    effective_price = self.aov * (1.0 - discount_pct)
                                    afford_retarget = wallet[abandoned_indices] >= effective_price

                                    adj_sens = np.maximum(0.05, price_sens[abandoned_indices] * (1.0 - discount_pct))
                                    p_recover = np.clip(
                                        (0.04 + boost) * (affinity[abandoned_indices] / adj_sens), 0.01, 0.70
                                    )
                                    recovered_mask = (rng.random(len(abandoned_indices)) < p_recover) & afford_retarget
                                    recovered_indices = abandoned_indices[recovered_mask]

                                    if len(recovered_indices) > 0:
                                        state[recovered_indices] = StateCode.CONVERTED
                                        day_conversions += len(recovered_indices)
                                        total_conversions += len(recovered_indices)

                                        # Cannibalization: Loyal customers (affinity > 0.75) who captured the discount
                                        loyal_mask = affinity[recovered_indices] > 0.75
                                        num_cannibalized = int(np.sum(loyal_mask))
                                        total_cannibalized += num_cannibalized

            # D. Revenue Settlement & Working Capital Update
            gross_rev_today = day_conversions * self.aov
            settled_today = gross_rev_today * self.fee_multiplier
            payout_day = day + self.settlement_delay
            if payout_day < buffer_len:
                receivables_schedule[payout_day] += settled_today

            # Pending uncollected receivables sum
            pending_total = float(np.sum(receivables_schedule[day + 1 :]))

            if record_trajectories:
                # State distribution for Mass Conservation Invariant verification
                state_counts = {
                    STATE_NAMES[s]: int(np.sum(state == s)) for s in StateCode
                }
                snapshots.append(
                    DailySnapshot(
                        day=day,
                        spend=day_spend,
                        clicks=day_clicks,
                        conversions=day_conversions,
                        gross_revenue=gross_rev_today,
                        settled_revenue=matured_cash,
                        liquid_cash=liquid_cash,
                        pending_receivables=pending_total,
                        state_distribution=state_counts,
                    )
                )

        # 3. Final Outcomes
        total_revenue = total_conversions * self.aov
        roas = (total_revenue / total_spend) if total_spend > 0 else 0.0
        cac = (total_spend / total_conversions) if total_conversions > 0 else float("inf")

        return TrialResult(
            trial_id=trial_id,
            spend=total_spend,
            impressions=count,
            clicks=total_clicks,
            conversions=total_conversions,
            revenue=total_revenue,
            roas=roas,
            cac=cac,
            cannibalized_conversions=total_cannibalized,
            insolvency_triggered=insolvency_triggered,
            final_liquid_cash=liquid_cash,
            min_cash_observed=min_cash_observed,
            daily_snapshots=snapshots,
        )

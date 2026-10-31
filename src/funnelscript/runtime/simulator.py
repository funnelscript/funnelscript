from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from funnelscript.models import StrategyAST, TouchpointNode
from funnelscript.runtime.agents import AgentPopulation, ConsumerState


@dataclass
class TrialResult:
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


@dataclass
class SimulationReport:
    strategy_name: str
    trials_count: int
    agents_per_trial: int
    timeframe_days: int
    mean_roas: float
    median_roas: float
    p10_roas: float
    p90_roas: float
    mean_cac: float
    median_cac: float
    p10_cac: float
    p90_cac: float
    probability_of_profit: float  # P(ROAS >= 1.0)
    cash_ruin_probability: float  # P(Insolvency) where liquid cash drops <= 0
    worst_case_drawdown: float  # Maximum capital loss observed
    cannibalization_rate: float  # % of discount conversions from loyal buyers
    raw_trials: list[TrialResult] = field(default_factory=list)


class MonteCarloSimulator:
    """Multi-Scale Discrete-Event Simulation Engine with Working Capital & Settlement Latency."""

    def __init__(self, ast: StrategyAST, average_order_value: float = 120.0) -> None:
        self.ast = ast
        self.aov = average_order_value
        self.touchpoint_map: dict[str, TouchpointNode] = {tp.id: tp for tp in ast.entities.touchpoints}
        self.budget_cap = ast.entities.budgets.total_budget
        self.max_cpc = ast.entities.budgets.max_cpc_limit
        self.initial_cash = getattr(ast.entities.budgets, "initial_cash", 10000.0)
        self.settlement_delay = getattr(ast.entities.budgets, "settlement_delay_days", 3)

    def run(self, num_trials: int = 100, agents_count: int | None = None, seed: int = 42) -> SimulationReport:
        """Executes Monte Carlo trials with discrete daily/hourly event cycles."""
        sim_params = self.ast.simulation_engine.parameters
        count = agents_count or int(sim_params.get("virtual_agents_count", 10000))
        timeframe_days = int(sim_params.get("timeframe_days", 14))
        sigma = float(sim_params.get("randomness_factor_sigma", 0.15))

        trials: list[TrialResult] = []

        for i in range(num_trials):
            trial_seed = seed + i
            trial_res = self._execute_single_trial(count, timeframe_days, sigma, trial_seed)
            trials.append(trial_res)

        roas_arr = np.array([t.roas for t in trials])
        cac_arr = np.array([t.cac for t in trials if t.cac < float("inf")])
        if len(cac_arr) == 0:
            cac_arr = np.array([0.0])

        spend_arr = np.array([t.spend for t in trials])
        rev_arr = np.array([t.revenue for t in trials])
        losses = np.maximum(0.0, spend_arr - rev_arr)

        cannibalized_total = sum(t.cannibalized_conversions for t in trials)
        conversions_total = sum(t.conversions for t in trials)
        cannibalization_rate = (cannibalized_total / conversions_total) if conversions_total > 0 else 0.0

        insolvency_count = sum(1 for t in trials if t.insolvency_triggered)
        cash_ruin_prob = insolvency_count / num_trials

        return SimulationReport(
            strategy_name=self.ast.strategy_name,
            trials_count=num_trials,
            agents_per_trial=count,
            timeframe_days=timeframe_days,
            mean_roas=float(np.mean(roas_arr)),
            median_roas=float(np.median(roas_arr)),
            p10_roas=float(np.percentile(roas_arr, 10)),
            p90_roas=float(np.percentile(roas_arr, 90)),
            mean_cac=float(np.mean(cac_arr)),
            median_cac=float(np.median(cac_arr)),
            p10_cac=float(np.percentile(cac_arr, 10)),
            p90_cac=float(np.percentile(cac_arr, 90)),
            probability_of_profit=float(np.mean(roas_arr >= 1.0)),
            cash_ruin_probability=float(cash_ruin_prob),
            worst_case_drawdown=float(np.max(losses)),
            cannibalization_rate=float(cannibalization_rate),
            raw_trials=trials,
        )

    def _execute_single_trial(self, count: int, timeframe_days: int, sigma: float, trial_seed: int) -> TrialResult:
        rng = np.random.default_rng(trial_seed)

        primary_aud = self.ast.entities.audiences[0]
        pop = AgentPopulation.generate_from_audience(primary_aud, count=count, seed=trial_seed)

        total_spend = 0.0
        total_clicks = 0
        total_conversions = 0
        cannibalized = 0

        # Working Capital Dynamics
        liquid_cash = self.initial_cash
        min_cash_observed = liquid_cash
        insolvency_triggered = False

        # Revenue payout settlement schedule: pending_receivables[payout_day] = cash
        max_buffer_days = timeframe_days + self.settlement_delay + 5
        pending_receivables = np.zeros(max_buffer_days, dtype=float)

        daily_budget = self.budget_cap / timeframe_days

        # Market volatility shock factor
        volatility_multiplier = max(0.2, 1.0 + rng.normal(0.0, sigma))

        # --- Multi-Scale Time Loop (Day by Day) ---
        for day in range(timeframe_days):
            # 1. Payout settlement: Collect receivables matured on this day
            liquid_cash += pending_receivables[day]

            # 2. Check liquidity constraint: Minimum operational balance required ($50 or 1 click)
            if liquid_cash < 50.0:
                insolvency_triggered = True
                continue

            # Planned ad spend for today
            day_target_spend = min(daily_budget, liquid_cash, max(0.0, self.budget_cap - total_spend))
            if day_target_spend < daily_budget * 0.50 and total_spend < self.budget_cap:
                # Cash starvation: Available cash covers less than 50% of intended daily spend
                insolvency_triggered = True

            if day_target_spend <= 0:
                continue

            day_clicks = 0
            day_conversions = 0

            # Execute logic flow steps for today's cohort slice
            agents_per_day = max(1, count // timeframe_days)
            day_slice_start = day * agents_per_day
            day_slice_end = min(count, (day + 1) * agents_per_day)
            day_indices = np.arange(day_slice_start, day_slice_end)

            for step in self.ast.logic_flow:
                if not isinstance(step, dict):
                    continue

                action = step.get("action")
                if action == "TriggerTraffic":
                    via_id = step.get("via", "")
                    dest_id = step.get("destination", "")
                    tp_ad = self.touchpoint_map.get(via_id)
                    tp_dest = self.touchpoint_map.get(dest_id)
                    if not tp_ad or not tp_dest:
                        continue

                    effective_cpc = min(self.max_cpc, tp_ad.base_cpc * volatility_multiplier)
                    ad_quality = tp_ad.ad_creative_score

                    # Hourly click probability: P(Click) = base_ctr * (1 + fomo * ad_quality)
                    base_ctr = 0.035
                    slice_fomo = pop.fomo_index[day_indices]
                    slice_state = pop.state[day_indices]

                    p_click = np.clip(base_ctr * (1.0 + slice_fomo * ad_quality), 0.001, 0.25)
                    click_events = (rng.random(len(day_indices)) < p_click) & (slice_state == ConsumerState.COLD)

                    matched_click_idx = day_indices[click_events]
                    num_clicks = len(matched_click_idx)
                    cost = num_clicks * effective_cpc

                    # Cap cost to day target
                    if cost > day_target_spend and effective_cpc > 0:
                        allowed_clicks = int(day_target_spend / effective_cpc)
                        matched_click_idx = matched_click_idx[:allowed_clicks]
                        num_clicks = allowed_clicks
                        cost = num_clicks * effective_cpc

                    total_spend += cost
                    liquid_cash -= cost
                    min_cash_observed = min(min_cash_observed, liquid_cash)
                    total_clicks += num_clicks
                    day_clicks += num_clicks

                    pop.state[matched_click_idx] = ConsumerState.AWARE

                    # Immediate Conversion on landing page
                    base_cr = tp_dest.base_conversion_rate
                    slice_affinity = pop.brand_affinity[matched_click_idx]
                    slice_sens = pop.price_sensitivity[matched_click_idx]

                    p_buy = np.clip(base_cr * (slice_affinity / slice_sens), 0.001, 0.60)
                    buy_events = rng.random(len(matched_click_idx)) < p_buy

                    converted_idx = matched_click_idx[buy_events]
                    abandoned_idx = matched_click_idx[~buy_events]

                    pop.state[converted_idx] = ConsumerState.CONVERTED
                    pop.state[abandoned_idx] = ConsumerState.CART_ABANDONED

                    day_conversions += len(converted_idx)
                    total_conversions += len(converted_idx)

                elif step.get("type") == "ConditionalBranch":
                    condition = step.get("condition", {})
                    if condition.get("user_action") == "AbandonCart":
                        for branch in step.get("true_branch", []):
                            if branch.get("action") == "ExecuteRetargeting":
                                payload = branch.get("payload", {})
                                discount_pct = float(payload.get("discount_percentage", 0.0)) / 100.0
                                boost = float(branch.get("expected_impact", {}).get("conversion_boost", 0.02))

                                # Find all agents currently in CART_ABANDONED
                                abandon_mask = pop.state == ConsumerState.CART_ABANDONED
                                abandon_indices = np.where(abandon_mask)[0]
                                if len(abandon_indices) == 0:
                                    continue

                                eff_sens = np.maximum(
                                    0.05, pop.price_sensitivity[abandon_indices] * (1.0 - discount_pct)
                                )
                                p_recover = np.clip(
                                    (0.04 + boost) * (pop.brand_affinity[abandon_indices] / eff_sens), 0.01, 0.70
                                )

                                recovered = rng.random(len(abandon_indices)) < p_recover
                                recovered_idx = abandon_indices[recovered]

                                pop.state[recovered_idx] = ConsumerState.CONVERTED
                                day_conversions += len(recovered_idx)
                                total_conversions += len(recovered_idx)

                                # Cannibalization count: loyal buyers (>0.75 affinity) taking the discount
                                loyal_cannibalized = recovered_idx[pop.brand_affinity[recovered_idx] > 0.75]
                                cannibalized += len(loyal_cannibalized)

            # 3. Schedule settlement for today's conversions
            day_gross_revenue = day_conversions * self.aov
            payout_day = day + self.settlement_delay
            if payout_day < max_buffer_days:
                # Deduct 2.9% payment processing fee
                net_settled = day_gross_revenue * 0.971
                pending_receivables[payout_day] += net_settled

        # End of simulation financial calculations
        total_revenue = total_conversions * self.aov
        roas = (total_revenue / total_spend) if total_spend > 0 else 0.0
        cac = (total_spend / total_conversions) if total_conversions > 0 else float("inf")

        return TrialResult(
            spend=total_spend,
            impressions=count,
            clicks=total_clicks,
            conversions=total_conversions,
            revenue=total_revenue,
            roas=roas,
            cac=cac,
            cannibalized_conversions=cannibalized,
            insolvency_triggered=insolvency_triggered,
            final_liquid_cash=liquid_cash,
            min_cash_observed=min_cash_observed,
        )

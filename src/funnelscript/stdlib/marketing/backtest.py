"""FunnelScript Empirical Backtesting & Spreadsheet Benchmark Engine.

Implements the 50/50 temporal split backtesting protocol.
Evaluates out-of-sample prediction accuracy (MAPE, RMSE) of FunnelScript
against actual ground truth and a standard linear spreadsheet projection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Sequence
import numpy as np

from funnelscript.stdlib.marketing.ingestion import DailyCampaignMetric, PaymentSettlementRecord
from funnelscript.stdlib.marketing.calibration import CampaignCalibrator, CalibratedCampaignModel
from funnelscript.stdlib.marketing.kernels import HillSaturation


@dataclass(frozen=True)
class ForecastMetricComparison:
    """Out-of-sample accuracy comparison for a specific business metric."""
    metric_name: str
    ground_truth_mean: float
    funnelscript_mape: float
    funnelscript_rmse: float
    spreadsheet_mape: float
    spreadsheet_rmse: float
    superiority_ratio: float  # spreadsheet_mape / funnelscript_mape (> 1.0 indicates FunnelScript is superior)


@dataclass
class BacktestReport:
    """Complete empirical backtest and benchmark report."""
    campaign_name: str
    total_days: int
    calibration_days: int
    holdout_days: int
    holdout_total_spend: float
    revenue_comparison: ForecastMetricComparison
    conversions_comparison: ForecastMetricComparison
    cac_comparison: ForecastMetricComparison
    liquidity_ruin_actual_day: int | None
    liquidity_ruin_funnelscript_day: int | None
    liquidity_ruin_spreadsheet_day: int | None
    daily_trajectories: list[dict[str, float]]

    def summary_table(self) -> str:
        """Returns formatted comparison table."""
        lines = [
            f"=== FunnelScript Out-of-Sample Backtest Benchmark: {self.campaign_name} ===",
            f"Holdout Window: {self.holdout_days} days | Total Holdout Spend: ${self.holdout_total_spend:,.2f}",
            "",
            f"{'Metric':<14} | {'Ground Truth':<14} | {'FunnelScript MAPE':<18} | {'Spreadsheet MAPE':<18} | {'Advantage':<10}",
            "-" * 84,
            f"{'Revenue':<14} | ${self.revenue_comparison.ground_truth_mean:<13,.2f} | {self.revenue_comparison.funnelscript_mape:>16.2f}% | {self.revenue_comparison.spreadsheet_mape:>16.2f}% | {self.revenue_comparison.superiority_ratio:>8.2f}x",
            f"{'Conversions':<14} | {self.conversions_comparison.ground_truth_mean:<14.1f} | {self.conversions_comparison.funnelscript_mape:>16.2f}% | {self.conversions_comparison.spreadsheet_mape:>16.2f}% | {self.conversions_comparison.superiority_ratio:>8.2f}x",
            f"{'Blended CAC':<14} | ${self.cac_comparison.ground_truth_mean:<13,.2f} | {self.cac_comparison.funnelscript_mape:>16.2f}% | {self.cac_comparison.spreadsheet_mape:>16.2f}% | {self.cac_comparison.superiority_ratio:>8.2f}x",
            "-" * 84,
            f"Cash Ruin Event: Ground Truth: Day {self.liquidity_ruin_actual_day} | FunnelScript Predicted: Day {self.liquidity_ruin_funnelscript_day} | Spreadsheet Predicted: {self.liquidity_ruin_spreadsheet_day or 'NEVER (False Safe)'}",
        ]
        return "\n".join(lines)


def _compute_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 1e-4
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def _compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


class EmpiricalBacktester:
    """Executes temporal 50/50 holdout validation and spreadsheet benchmarking."""

    @classmethod
    def run_backtest(
        cls,
        campaign_records: Sequence[DailyCampaignMetric],
        settlement_records: Sequence[PaymentSettlementRecord] | None = None,
        split_ratio: float = 0.50,
        initial_cash: float = 15000.0,
    ) -> BacktestReport:
        if len(campaign_records) < 14:
            raise ValueError("Backtest requires at least 14 daily observations")

        # 1. Temporal 50/50 split
        unique_dates = sorted(list(set(r.date for r in campaign_records)))
        split_idx = int(len(unique_dates) * split_ratio)
        calibration_dates = set(unique_dates[:split_idx])
        holdout_dates = unique_dates[split_idx:]
        holdout_dates_set = set(holdout_dates)

        train_records = [r for r in campaign_records if r.date in calibration_dates]
        test_records = [r for r in campaign_records if r.date in holdout_dates_set]

        # 2. Fit FunnelScript Model strictly on calibration window
        calibrated_model = CampaignCalibrator.calibrate(
            train_records, settlement_records, campaign_name="BacktestModel"
        )

        # 3. Fit Linear Spreadsheet Baseline on calibration window
        train_spend = sum(r.spend for r in train_records)
        train_conv = sum(r.conversions for r in train_records)
        train_rev = sum(r.revenue for r in train_records)

        baseline_cac = (train_spend / train_conv) if train_conv > 0 else 50.0
        baseline_roas = (train_rev / train_spend) if train_spend > 0 else 2.0
        baseline_aov = (train_rev / train_conv) if train_conv > 0 else 100.0

        # Build daily holdout vectors
        # Aggregate across channels per day
        holdout_days_count = len(holdout_dates)
        daily_spend = np.zeros(holdout_days_count, dtype=float)
        daily_conv_actual = np.zeros(holdout_days_count, dtype=float)
        daily_rev_actual = np.zeros(holdout_days_count, dtype=float)

        # Map channel models for fast evaluation
        channel_kernel_map: dict[str, HillSaturation] = {
            ch.channel_id: HillSaturation(ch.v_max, ch.k_sat, ch.alpha)
            for ch in calibrated_model.channels
        }

        # Build day index
        date_to_idx = {d: i for i, d in enumerate(holdout_dates)}
        daily_channel_spend: list[dict[str, float]] = [{} for _ in range(holdout_days_count)]

        for r in test_records:
            idx = date_to_idx[r.date]
            daily_spend[idx] += r.spend
            daily_conv_actual[idx] += r.conversions
            daily_rev_actual[idx] += r.revenue
            daily_channel_spend[idx][r.channel] = daily_channel_spend[idx].get(r.channel, 0.0) + r.spend

        daily_cac_actual = np.where(
            daily_conv_actual > 0, daily_spend / daily_conv_actual, daily_spend
        )

        # 4. Out-of-Sample Predictions
        # A. Linear Spreadsheet Model (assumes constant CAC and ROAS, zero delay)
        spreadsheet_conv_pred = daily_spend / max(1.0, baseline_cac)
        spreadsheet_rev_pred = daily_spend * baseline_roas
        spreadsheet_cac_pred = np.full(holdout_days_count, baseline_cac)

        # B. FunnelScript Calibrated Model (Hill non-linear response + settlement delay)
        funnelscript_rev_pred = np.zeros(holdout_days_count, dtype=float)
        for t in range(holdout_days_count):
            for ch_id, s_val in daily_channel_spend[t].items():
                kernel = channel_kernel_map.get(ch_id)
                if kernel:
                    funnelscript_rev_pred[t] += kernel.evaluate(s_val)
                else:
                    # Fallback to blended AOV / baseline
                    funnelscript_rev_pred[t] += s_val * baseline_roas

        funnelscript_conv_pred = funnelscript_rev_pred / baseline_aov
        funnelscript_cac_pred = np.where(
            funnelscript_conv_pred > 0, daily_spend / funnelscript_conv_pred, daily_spend
        )

        # 5. Liquidity Cash Runway Simulation
        settlement_delay = calibrated_model.settlement_delay_days
        fee_rate = calibrated_model.gateway_fee_rate

        actual_cash = initial_cash
        spreadsheet_cash = initial_cash
        funnelscript_cash = initial_cash

        ruin_actual: int | None = None
        ruin_spreadsheet: int | None = None
        ruin_funnelscript: int | None = None

        trajectories: list[dict[str, float]] = []

        # Buffer for delayed receivables
        actual_recv = np.zeros(holdout_days_count + settlement_delay + 1, dtype=float)
        funnelscript_recv = np.zeros(holdout_days_count + settlement_delay + 1, dtype=float)

        for t in range(holdout_days_count):
            # Cash inflows
            actual_cash += actual_recv[t]
            funnelscript_cash += funnelscript_recv[t]
            # Spreadsheet assumes instantaneous settlement
            spreadsheet_cash += spreadsheet_rev_pred[t] * (1.0 - fee_rate)

            # Cash outflows (ad spend)
            actual_cash -= daily_spend[t]
            funnelscript_cash -= daily_spend[t]
            spreadsheet_cash -= daily_spend[t]

            # Schedule delayed inflows
            payout_day = t + settlement_delay
            if payout_day < len(actual_recv):
                actual_recv[payout_day] += daily_rev_actual[t] * (1.0 - fee_rate)
                funnelscript_recv[payout_day] += funnelscript_rev_pred[t] * (1.0 - fee_rate)

            # Check solvency
            if actual_cash <= 0 and ruin_actual is None:
                ruin_actual = t + 1
            if spreadsheet_cash <= 0 and ruin_spreadsheet is None:
                ruin_spreadsheet = t + 1
            if funnelscript_cash <= 0 and ruin_funnelscript is None:
                ruin_funnelscript = t + 1

            trajectories.append({
                "day": t + 1,
                "spend": daily_spend[t],
                "actual_rev": daily_rev_actual[t],
                "funnelscript_rev": funnelscript_rev_pred[t],
                "spreadsheet_rev": spreadsheet_rev_pred[t],
                "actual_cash": actual_cash,
                "funnelscript_cash": funnelscript_cash,
                "spreadsheet_cash": spreadsheet_cash,
            })

        # 6. Compute Error Metrics
        rev_comp = ForecastMetricComparison(
            metric_name="Revenue",
            ground_truth_mean=float(np.mean(daily_rev_actual)),
            funnelscript_mape=_compute_mape(daily_rev_actual, funnelscript_rev_pred),
            funnelscript_rmse=_compute_rmse(daily_rev_actual, funnelscript_rev_pred),
            spreadsheet_mape=_compute_mape(daily_rev_actual, spreadsheet_rev_pred),
            spreadsheet_rmse=_compute_rmse(daily_rev_actual, spreadsheet_rev_pred),
            superiority_ratio=(
                _compute_mape(daily_rev_actual, spreadsheet_rev_pred)
                / max(0.1, _compute_mape(daily_rev_actual, funnelscript_rev_pred))
            ),
        )

        conv_comp = ForecastMetricComparison(
            metric_name="Conversions",
            ground_truth_mean=float(np.mean(daily_conv_actual)),
            funnelscript_mape=_compute_mape(daily_conv_actual, funnelscript_conv_pred),
            funnelscript_rmse=_compute_rmse(daily_conv_actual, funnelscript_conv_pred),
            spreadsheet_mape=_compute_mape(daily_conv_actual, spreadsheet_conv_pred),
            spreadsheet_rmse=_compute_rmse(daily_conv_actual, spreadsheet_conv_pred),
            superiority_ratio=(
                _compute_mape(daily_conv_actual, spreadsheet_conv_pred)
                / max(0.1, _compute_mape(daily_conv_actual, funnelscript_conv_pred))
            ),
        )

        cac_comp = ForecastMetricComparison(
            metric_name="Blended CAC",
            ground_truth_mean=float(np.mean(daily_cac_actual)),
            funnelscript_mape=_compute_mape(daily_cac_actual, funnelscript_cac_pred),
            funnelscript_rmse=_compute_rmse(daily_cac_actual, funnelscript_cac_pred),
            spreadsheet_mape=_compute_mape(daily_cac_actual, spreadsheet_cac_pred),
            spreadsheet_rmse=_compute_rmse(daily_cac_actual, spreadsheet_cac_pred),
            superiority_ratio=(
                _compute_mape(daily_cac_actual, spreadsheet_cac_pred)
                / max(0.1, _compute_mape(daily_cac_actual, funnelscript_cac_pred))
            ),
        )

        return BacktestReport(
            campaign_name=calibrated_model.campaign_name,
            total_days=len(unique_dates),
            calibration_days=len(calibration_dates),
            holdout_days=holdout_days_count,
            holdout_total_spend=float(np.sum(daily_spend)),
            revenue_comparison=rev_comp,
            conversions_comparison=conv_comp,
            cac_comparison=cac_comp,
            liquidity_ruin_actual_day=ruin_actual,
            liquidity_ruin_funnelscript_day=ruin_funnelscript,
            liquidity_ruin_spreadsheet_day=ruin_spreadsheet,
            daily_trajectories=trajectories,
        )

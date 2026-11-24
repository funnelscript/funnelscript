from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

from funnelscript.solver.types import (
    ChannelModel,
    EmpiricalSupportMetadata,
    SpendSupportClassification,
)


class CanonicalResponseEvaluator:
    """
    Canonical economic response evaluation path.
    All simulation, optimization objectives, and telemetry endpoints
    evaluate through this single implementation to ensure zero semantic drift.
    """

    def __init__(self, channels: List[ChannelModel], total_budget: float):
        self.channels = channels
        self.total_budget = total_budget
        self.m = len(channels)

        # Vectorized parameters
        self.v_max = np.array([ch.v_max for ch in channels], dtype=float)
        self.k_sat = np.array([ch.k_sat for ch in channels], dtype=float)
        self.alpha = np.array([ch.alpha for ch in channels], dtype=float)

    def evaluate_channel_revenues(self, w: np.ndarray) -> np.ndarray:
        """Evaluates revenue per channel given simplex weight vector w."""
        spend = self.total_budget * w
        # Handle zero or negative spend cleanly
        valid = spend > 0.0
        rev = np.zeros(self.m, dtype=float)
        
        if np.any(valid):
            s_val = spend[valid]
            k_val = self.k_sat[valid]
            a_val = self.alpha[valid]
            v_val = self.v_max[valid]

            s_pow = s_val ** a_val
            k_pow = k_val ** a_val
            rev[valid] = v_val * s_pow / (k_pow + s_pow)

        return rev

    def evaluate_revenue(self, w: np.ndarray) -> float:
        """Total revenue across all channels."""
        return float(np.sum(self.evaluate_channel_revenues(w)))

    def evaluate_profit(self, w: np.ndarray) -> float:
        """Total net profit: Total Revenue - Total Budget."""
        return self.evaluate_revenue(w) - self.total_budget

    def evaluate_conversions(self, w: np.ndarray, avg_ticket: float = 100.0) -> float:
        """Expected conversion volume derived from revenue and average ticket price."""
        revenue = self.evaluate_revenue(w)
        return float(revenue / max(avg_ticket, 1e-4))

    def evaluate_cac(self, w: np.ndarray, avg_ticket: float = 100.0) -> float:
        """Blended Customer Acquisition Cost (CAC) = Total Budget / Total Conversions."""
        conversions = self.evaluate_conversions(w, avg_ticket)
        if conversions <= 0.0:
            return float("inf")
        return float(self.total_budget / conversions)

    def analytical_gradient(self, w: np.ndarray) -> np.ndarray:
        """
        Computes exact analytical gradient d(Revenue)/dw.
        d(R_i)/dw_i = B * V_max * alpha * spend^(alpha-1) * K^alpha / (K^alpha + spend^alpha)^2
        """
        spend = self.total_budget * w
        grad = np.zeros(self.m, dtype=float)
        valid = spend > 1e-9

        if np.any(valid):
            s_val = spend[valid]
            k_val = self.k_sat[valid]
            a_val = self.alpha[valid]
            v_val = self.v_max[valid]

            k_pow = k_val ** a_val
            s_pow = s_val ** a_val
            denom = (k_pow + s_pow) ** 2

            ds_dw = self.total_budget
            dr_ds = v_val * a_val * (s_val ** (a_val - 1.0)) * k_pow / denom
            grad[valid] = dr_ds * ds_dw

        return grad

    def classify_spend_support(self, w: np.ndarray) -> Dict[str, EmpiricalSupportMetadata]:
        """
        Classifies spend recommendations to prevent prior-dominated posteriors
        from being presented as empirical evidence.
        """
        spend = self.total_budget * w
        diagnostics: Dict[str, EmpiricalSupportMetadata] = {}

        for i, ch in enumerate(self.channels):
            alloc = float(spend[i])
            min_obs = ch.empirical_support.min_observed_spend
            max_obs = ch.empirical_support.max_observed_spend

            if alloc > max_obs * 1.01:
                ratio = alloc / max(max_obs, 1.0)
                classification = SpendSupportClassification.EXTRAPOLATED_PRIOR
            elif alloc < min_obs * 0.99:
                ratio = alloc / max(min_obs, 1.0)
                classification = SpendSupportClassification.EXTRAPOLATED_PRIOR
            else:
                ratio = 1.0
                classification = SpendSupportClassification.EMPIRICALLY_SUPPORTED

            diagnostics[ch.channel_id] = EmpiricalSupportMetadata(
                min_observed_spend=min_obs,
                max_observed_spend=max_obs,
                observations_count=ch.empirical_support.observations_count,
                classification=classification,
                extrapolation_ratio=float(ratio),
            )

        return diagnostics

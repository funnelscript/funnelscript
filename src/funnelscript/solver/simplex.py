from __future__ import annotations

from typing import List, Tuple
import numpy as np

from funnelscript.solver.types import ChannelModel, RegisteredAction
from funnelscript.solver.errors import SimplexFeasibilityError


def project_onto_simplex(v: np.ndarray) -> np.ndarray:
    """
    Computes Euclidean projection of vector v onto the probability simplex:
    { w in R^n : sum(w) = 1, w >= 0 }
    Deterministic O(n log n) algorithm.
    """
    n = len(v)
    if n == 0:
        return np.array([], dtype=float)
    if n == 1:
        return np.array([1.0], dtype=float)

    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    indices = np.arange(1, n + 1)
    cond = u * indices > (cssv - 1.0)
    nonzeros = np.nonzero(cond)[0]
    if len(nonzeros) == 0:
        # Fallback to uniform
        return np.ones(n, dtype=float) / n
    rho = nonzeros[-1]
    theta = (cssv[rho] - 1.0) / float(rho + 1)
    w = np.maximum(v - theta, 0.0)
    # Ensure numerical stability
    s = np.sum(w)
    if s > 0:
        w = w / s
    else:
        w = np.ones(n, dtype=float) / n
    return w


def compute_scale_invariant_step(w: np.ndarray, rel_eps: float = 1e-7) -> np.ndarray:
    """
    Computes scale-invariant finite-difference steps for variables on the simplex.
    Eliminates magnitude dependency compared to raw monetary stepping.
    """
    return rel_eps * np.maximum(np.abs(w), 1.0 / len(w))


def normalize_bounds_to_simplex(
    channels: List[ChannelModel], total_budget: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Normalizes raw dollar min/max channel bounds to unit simplex bounds w_i in [l_i, u_i].
    Validates feasibility: sum(l_i) <= 1.0 <= sum(u_i).
    """
    if total_budget <= 0.0:
        raise SimplexFeasibilityError(
            code="ERR_SIMPLEX_ZERO_BUDGET",
            message=f"Total budget must be strictly positive, got {total_budget}",
            remediation="Specify a positive marketing budget allocation.",
            remediation_action=RegisteredAction.EXPAND_BUDGET_ENVELOPE,
        )

    m = len(channels)
    lower_w = np.zeros(m, dtype=float)
    upper_w = np.zeros(m, dtype=float)

    for i, ch in enumerate(channels):
        lower_w[i] = ch.min_spend / total_budget
        upper_w[i] = ch.max_spend / total_budget

        if lower_w[i] > upper_w[i]:
            raise SimplexFeasibilityError(
                code="ERR_SIMPLEX_INVERTED_BOUNDS",
                message=f"Channel '{ch.channel_id}' min_spend ({ch.min_spend}) exceeds max_spend ({ch.max_spend})",
                remediation="Adjust channel configuration so min_spend <= max_spend.",
                remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
            )

    sum_min = float(np.sum(lower_w))
    sum_max = float(np.sum(upper_w))

    if sum_min > 1.0 + 1e-9:
        total_min_required = sum(ch.min_spend for ch in channels)
        raise SimplexFeasibilityError(
            code="ERR_SIMPLEX_MIN_BOUNDS_EXCEED_BUDGET",
            message=(
                f"Sum of minimum channel requirements ({total_min_required:,.2f}) "
                f"exceeds total budget ({total_budget:,.2f}). Sum of lower weights: {sum_min:.4f} > 1.0"
            ),
            remediation="Lower channel min_spend requirements or increase total budget envelope.",
            remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
        )

    if sum_max < 1.0 - 1e-9:
        total_max_allowed = sum(ch.max_spend for ch in channels)
        raise SimplexFeasibilityError(
            code="ERR_SIMPLEX_MAX_BOUNDS_BELOW_BUDGET",
            message=(
                f"Sum of maximum channel allocations ({total_max_allowed:,.2f}) "
                f"is less than total budget ({total_budget:,.2f}). Sum of upper weights: {sum_max:.4f} < 1.0"
            ),
            remediation="Increase channel max_spend limits or decrease total budget.",
            remediation_action=RegisteredAction.EXPAND_BUDGET_ENVELOPE,
        )

    # Clamp upper bounds to 1.0
    upper_w = np.minimum(upper_w, 1.0)
    lower_w = np.maximum(lower_w, 0.0)

    return lower_w, upper_w

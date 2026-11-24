from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Tuple
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, NonlinearConstraint, minimize

from funnelscript.solver.types import (
    OptimizationGoal,
    RegisteredAction,
    SolverInput,
    SolverResult,
)
from funnelscript.solver.errors import ConvergenceError
from funnelscript.solver.simplex import (
    compute_scale_invariant_step,
    normalize_bounds_to_simplex,
    project_onto_simplex,
)
from funnelscript.solver.evaluator import CanonicalResponseEvaluator


class DeterministicMarketingSolver:
    """
    Deterministic mathematical programming solver for marketing mix optimization.
    Solves continuous NLP on the normalized unit simplex w in Δ^(m-1).
    """

    def __init__(self, input_data: SolverInput):
        self.input_data = input_data
        self.evaluator = CanonicalResponseEvaluator(
            channels=input_data.channels,
            total_budget=input_data.total_budget,
        )
        self.m = len(input_data.channels)

    def _build_objective(self):
        """Constructs objective function and analytical gradient for scipy.optimize.minimize."""
        goal = self.input_data.goal
        budget = self.input_data.total_budget
        ticket = self.input_data.avg_ticket_value

        if goal == OptimizationGoal.MAXIMIZE_PROFIT:
            def fun(w: np.ndarray) -> float:
                rev = self.evaluator.evaluate_revenue(w)
                return -(rev - budget)

            def jac(w: np.ndarray) -> np.ndarray:
                return -self.evaluator.analytical_gradient(w)

        elif goal == OptimizationGoal.MAXIMIZE_CONVERSIONS:
            def fun(w: np.ndarray) -> float:
                rev = self.evaluator.evaluate_revenue(w)
                conversions = rev / ticket
                return -conversions

            def jac(w: np.ndarray) -> np.ndarray:
                return -(self.evaluator.analytical_gradient(w) / ticket)

        elif goal == OptimizationGoal.MINIMIZE_CAC:
            def fun(w: np.ndarray) -> float:
                return self.evaluator.evaluate_cac(w, ticket)

            def jac(w: np.ndarray) -> np.ndarray:
                # Finite difference with scale-invariant relative step
                eps_vec = compute_scale_invariant_step(w, rel_eps=1e-7)
                grad = np.zeros(self.m, dtype=float)
                f0 = fun(w)
                for i in range(self.m):
                    w_step = np.copy(w)
                    w_step[i] += eps_vec[i]
                    grad[i] = (fun(w_step) - f0) / eps_vec[i]
                return grad
        else:
            raise ValueError(f"Unsupported optimization goal: {goal}")

        return fun, jac

    def solve(self) -> SolverResult:
        m = self.m
        budget = self.input_data.total_budget
        lower_w, upper_w = normalize_bounds_to_simplex(self.input_data.channels, budget)

        # 1. Simplex bounds: l_i <= w_i <= u_i
        bounds = Bounds(lb=lower_w, ub=upper_w)

        # 2. Equality constraint: sum(w) = 1.0
        simplex_eq = LinearConstraint(
            A=np.ones((1, m), dtype=float),
            lb=1.0,
            ub=1.0,
        )

        constraints = [simplex_eq]

        # 3. Optional CAC ceiling constraint: CAC(w) <= cac_ceiling
        if self.input_data.cac_ceiling is not None:
            ceiling = self.input_data.cac_ceiling
            ticket = self.input_data.avg_ticket_value
            # CAC = B / (Rev / ticket) <= ceiling <=> Rev >= (B * ticket) / ceiling
            min_rev_required = (budget * ticket) / ceiling

            def cac_constraint_fn(w: np.ndarray) -> float:
                rev = self.evaluator.evaluate_revenue(w)
                return rev - min_rev_required

            def cac_constraint_jac(w: np.ndarray) -> np.ndarray:
                return self.evaluator.analytical_gradient(w)

            constraints.append(
                NonlinearConstraint(
                    fun=cac_constraint_fn,
                    lb=0.0,
                    ub=np.inf,
                    jac=cac_constraint_jac,
                )
            )

        # Initial point: projected mid-point of bounds
        mid_point = (lower_w + upper_w) / 2.0
        w0 = project_onto_simplex(mid_point)
        # Ensure w0 respects bounds
        w0 = np.clip(w0, lower_w, upper_w)
        w0 = project_onto_simplex(w0)

        obj_fun, obj_jac = self._build_objective()

        res = minimize(
            fun=obj_fun,
            x0=w0,
            method="SLSQP",
            jac=obj_jac,
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 1000, "disp": False},
        )

        if not res.success:
            # Check if infeasible due to CAC ceiling
            if self.input_data.cac_ceiling is not None:
                raise ConvergenceError(
                    code="ERR_SOLVER_CAC_CEILING_INFEASIBLE",
                    message=(
                        f"Solver failed to achieve CAC ceiling of ${self.input_data.cac_ceiling:.2f} "
                        f"within channel bounds: {res.message}"
                    ),
                    remediation="Relax CAC ceiling or increase channel max_spend on high-converting surfaces.",
                    remediation_action=RegisteredAction.ADJUST_CAC_CEILING,
                )
            raise ConvergenceError(
                code="ERR_SOLVER_CONVERGENCE_FAILURE",
                message=f"Numerical solver failed to converge: {res.message}",
                remediation="Relax channel min/max bounds or adjust budget envelope.",
                remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
            )

        optimal_w = project_onto_simplex(res.x)
        # Final clip within numerical bounds
        optimal_w = np.clip(optimal_w, lower_w, upper_w)
        optimal_w = optimal_w / np.sum(optimal_w)

        allocations: Dict[str, float] = {}
        for i, ch in enumerate(self.input_data.channels):
            allocations[ch.channel_id] = float(optimal_w[i] * budget)

        expected_revenue = self.evaluator.evaluate_revenue(optimal_w)
        expected_profit = self.evaluator.evaluate_profit(optimal_w)
        expected_cac = self.evaluator.evaluate_cac(
            optimal_w, self.input_data.avg_ticket_value
        )

        # Extract shadow prices (Lagrange multipliers)
        shadow_prices: Dict[str, float] = {}
        multipliers = getattr(res, "v", None)
        for i, ch in enumerate(self.input_data.channels):
            if multipliers is not None and i < len(multipliers):
                shadow_prices[ch.channel_id] = float(multipliers[i])
            else:
                # Approximate marginal revenue d(Revenue)/d(spend_i)
                grad_i = self.evaluator.analytical_gradient(optimal_w)[i] / budget
                shadow_prices[ch.channel_id] = float(grad_i)

        diagnostics = self.evaluator.classify_spend_support(optimal_w)

        # Registered next actions based on diagnostics
        next_actions: List[RegisteredAction] = [RegisteredAction.REBALANCE_BUDGET]
        for ch_id, diag in diagnostics.items():
            if diag.extrapolation_ratio > 1.05:
                if RegisteredAction.COLLECT_EMPIRICAL_SPEND not in next_actions:
                    next_actions.append(RegisteredAction.COLLECT_EMPIRICAL_SPEND)

        # Compute deterministic physical artifact checksum
        artifact_payload = {
            "dataset_fingerprint": self.input_data.lineage.dataset_fingerprint,
            "population_hash": self.input_data.lineage.population_hash,
            "currency": self.input_data.currency,
            "total_budget": budget,
            "optimal_allocations": allocations,
            "expected_net_profit": expected_profit,
            "expected_blended_cac": expected_cac,
        }
        canonical_str = json.dumps(artifact_payload, sort_keys=True)
        artifact_checksum = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        return SolverResult(
            status="OPTIMAL",
            optimal_weights=optimal_w,
            optimal_allocations=allocations,
            expected_revenue=expected_revenue,
            expected_net_profit=expected_profit,
            expected_blended_cac=expected_cac,
            shadow_prices=shadow_prices,
            channel_diagnostics=diagnostics,
            artifact_checksum=artifact_checksum,
            next_actions=next_actions,
        )

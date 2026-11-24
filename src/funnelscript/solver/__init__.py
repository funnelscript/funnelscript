"""
FunnelScript Operations Research (OR) Decision Engine & Solver.
Decoupled prescriptive mathematical programming module.
"""

from funnelscript.solver.types import (
    ChannelModel,
    EmpiricalSupportMetadata,
    ModelLineage,
    OptimizationGoal,
    RegisteredAction,
    SolverInput,
    SolverResult,
    SpendSupportClassification,
)
from funnelscript.solver.errors import (
    ConvergenceError,
    LineageMismatchError,
    PreflightAdmissionError,
    SimplexFeasibilityError,
    SolverDomainError,
)
from funnelscript.solver.lineage import validate_lineage
from funnelscript.solver.admission import PreflightAdmissionGate
from funnelscript.solver.simplex import (
    compute_scale_invariant_step,
    normalize_bounds_to_simplex,
    project_onto_simplex,
)
from funnelscript.solver.evaluator import CanonicalResponseEvaluator
from funnelscript.solver.optimizer import DeterministicMarketingSolver
from funnelscript.solver.sensitivity import (
    FunnelBottleneckSensitivity,
    analyze_funnel_bottlenecks,
)
from funnelscript.solver.service import FunnelScriptSolverService

__all__ = [
    "ChannelModel",
    "EmpiricalSupportMetadata",
    "ModelLineage",
    "OptimizationGoal",
    "RegisteredAction",
    "SolverInput",
    "SolverResult",
    "SpendSupportClassification",
    "SolverDomainError",
    "LineageMismatchError",
    "PreflightAdmissionError",
    "SimplexFeasibilityError",
    "ConvergenceError",
    "validate_lineage",
    "PreflightAdmissionGate",
    "compute_scale_invariant_step",
    "normalize_bounds_to_simplex",
    "project_onto_simplex",
    "CanonicalResponseEvaluator",
    "DeterministicMarketingSolver",
    "FunnelBottleneckSensitivity",
    "analyze_funnel_bottlenecks",
    "FunnelScriptSolverService",
]

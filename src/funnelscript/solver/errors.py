from __future__ import annotations

from typing import Optional
from funnelscript.solver.types import RegisteredAction


class SolverDomainError(Exception):
    """Base domain exception with machine-readable error code and remediation."""

    def __init__(
        self,
        code: str,
        message: str,
        remediation: str,
        remediation_action: Optional[RegisteredAction] = None,
    ):
        super().__init__(f"[{code}] {message} - Remediation: {remediation}")
        self.code = code
        self.message = message
        self.remediation = remediation
        self.remediation_action = remediation_action


class LineageMismatchError(SolverDomainError):
    """Raised when model lineage checks fail closed."""
    pass


class PreflightAdmissionError(SolverDomainError):
    """Raised when solver preflight admission validation fails."""
    pass


class SimplexFeasibilityError(SolverDomainError):
    """Raised when channel bounds violate unit simplex feasibility."""
    pass


class ConvergenceError(SolverDomainError):
    """Raised when the numerical optimization solver fails to find a feasible optimum."""
    pass

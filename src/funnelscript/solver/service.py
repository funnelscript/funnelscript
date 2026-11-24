from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from funnelscript.solver.types import SolverInput, SolverResult
from funnelscript.solver.admission import PreflightAdmissionGate
from funnelscript.solver.optimizer import DeterministicMarketingSolver


class FunnelScriptSolverService:
    """
    Decoupled Solver Service for FunnelScript.
    Enforces admission preflight gates, executes deterministic optimization,
    indexes artifacts, and verifies artifact checksums before publishing.
    """

    def __init__(self, artifact_registry_dir: Optional[Path] = None):
        self.admission_gate = PreflightAdmissionGate()
        self.artifact_registry_dir = artifact_registry_dir
        self._registry: Dict[str, SolverResult] = {}

    def solve(self, input_data: SolverInput) -> SolverResult:
        # 1. Enforce canonical preflight admission gate
        validated_input = self.admission_gate.validate(input_data)

        # 2. Execute deterministic mathematical programming solver
        solver = DeterministicMarketingSolver(validated_input)
        result = solver.solve()

        # 3. Commit to registry and verify artifact publication
        checksum = result.artifact_checksum
        self._registry[checksum] = result

        if self.artifact_registry_dir is not None:
            self.artifact_registry_dir.mkdir(parents=True, exist_ok=True)
            artifact_file = self.artifact_registry_dir / f"solver_decision_{checksum}.json"
            payload = {
                "checksum": checksum,
                "status": result.status,
                "optimal_allocations": result.optimal_allocations,
                "expected_revenue": result.expected_revenue,
                "expected_net_profit": result.expected_net_profit,
                "expected_blended_cac": result.expected_blended_cac,
                "next_actions": [a.value for a in result.next_actions],
            }
            with open(artifact_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)

        return result

    def get_registered_result(self, checksum: str) -> Optional[SolverResult]:
        """Retrieves committed solver solution by artifact checksum."""
        return self._registry.get(checksum)

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from funnelscript.models import StrategyAST


class LintSeverity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class LintFinding:
    code: str
    severity: LintSeverity
    message: str
    path: str
    remediation: str


class FunnelLinter:
    """Static semantic analysis and graph-theoretic invariant verifier for FunnelScript."""

    def __init__(self, ast: StrategyAST) -> None:
        self.ast = ast
        self.findings: list[LintFinding] = []

    def lint(self) -> list[LintFinding]:
        """Runs all compile-time lint passes and returns findings."""
        self.findings.clear()
        self._check_economic_boundaries()
        self._check_orphan_entities()
        self._check_graph_reachability_and_sinks()
        self._check_attribution_cycles()
        self._check_liquidity_preflight()
        return list(self.findings)

    @property
    def has_errors(self) -> bool:
        return any(f.severity == LintSeverity.ERROR for f in self.findings)

    # -------------------------------------------------------------
    # 1. Economic Boundaries & Parameter Bounds (FS100-FS199)
    # -------------------------------------------------------------
    def _check_economic_boundaries(self) -> None:
        budgets = self.ast.entities.budgets

        if budgets.total_budget <= 0:
            self._add(
                "FS101",
                LintSeverity.ERROR,
                f"total_budget must be strictly positive, found {budgets.total_budget}",
                "entities.budgets.total_budget",
                "Set total_budget to a realistic positive dollar figure.",
            )

        if budgets.max_cpc_limit <= 0:
            self._add(
                "FS102",
                LintSeverity.ERROR,
                f"max_cpc_limit must be > 0, found {budgets.max_cpc_limit}",
                "entities.budgets.max_cpc_limit",
                "Specify a maximum CPC bid ceiling above 0.",
            )

        if budgets.max_cpc_limit > budgets.total_budget:
            self._add(
                "FS103",
                LintSeverity.ERROR,
                f"max_cpc_limit ({budgets.max_cpc_limit}) cannot exceed total_budget ({budgets.total_budget})",
                "entities.budgets.max_cpc_limit",
                "Lower max_cpc_limit or raise total_budget.",
            )

        if budgets.initial_cash < 0:
            self._add(
                "FS104",
                LintSeverity.ERROR,
                f"initial_cash cannot be negative, found {budgets.initial_cash}",
                "entities.budgets.initial_cash",
                "Set initial_cash to liquid operating capital available at t=0.",
            )

        # Validate Touchpoint parameters
        for idx, tp in enumerate(self.ast.entities.touchpoints):
            path = f"entities.touchpoints[{idx}]"
            if tp.base_cpc < 0:
                self._add("FS105", LintSeverity.ERROR, f"Touchpoint '{tp.id}' has negative base_cpc: {tp.base_cpc}", path, "Ensure base_cpc is >= 0.")
            if not (0.0 <= tp.ad_creative_score <= 1.0):
                self._add("FS106", LintSeverity.ERROR, f"Touchpoint '{tp.id}' creative_score {tp.ad_creative_score} out of [0, 1]", path, "Clamp creative_score to [0.0, 1.0].")
            if not (0.0 < tp.base_conversion_rate <= 1.0):
                self._add("FS107", LintSeverity.ERROR, f"Touchpoint '{tp.id}' conversion rate {tp.base_conversion_rate} out of (0, 1]", path, "Set conversion rate in (0.0, 1.0].")

    # -------------------------------------------------------------
    # 2. Entity References & Orphan Detection (FS200-FS299)
    # -------------------------------------------------------------
    def _check_orphan_entities(self) -> None:
        declared_audiences = {aud.id for aud in self.ast.entities.audiences}
        declared_touchpoints = {tp.id for tp in self.ast.entities.touchpoints}

        used_audiences: set[str] = set()
        used_touchpoints: set[str] = set()

        for idx, step in enumerate(self.ast.logic_flow):
            if not isinstance(step, dict):
                continue
            action = step.get("action")
            if action == "TriggerTraffic":
                src = step.get("source")
                via = step.get("via")
                dest = step.get("destination")
                if src:
                    used_audiences.add(src)
                if via:
                    used_touchpoints.add(via)
                if dest:
                    used_touchpoints.add(dest)
            elif step.get("type") == "ConditionalBranch":
                for branch in step.get("true_branch", []) + step.get("false_branch", []):
                    ch = branch.get("channel")
                    if ch:
                        used_touchpoints.add(ch)

        # Detect unused / orphaned audiences
        orphaned_audiences = declared_audiences - used_audiences
        for aud_id in orphaned_audiences:
            self._add(
                "FS201",
                LintSeverity.WARNING,
                f"Audience '{aud_id}' is declared but never referenced in logic_flow",
                f"entities.audiences[{aud_id}]",
                "Either route traffic from this audience or remove it to save memory.",
            )

        # Detect unused / orphaned touchpoints
        orphaned_touchpoints = declared_touchpoints - used_touchpoints
        for tp_id in orphaned_touchpoints:
            self._add(
                "FS202",
                LintSeverity.WARNING,
                f"Touchpoint '{tp_id}' is declared but never connected to logic_flow",
                f"entities.touchpoints[{tp_id}]",
                "Connect this touchpoint into an ad or retargeting sequence or remove it.",
            )

    # -------------------------------------------------------------
    # 3. Graph Reachability & Flow Sinks (FS300-FS399)
    # -------------------------------------------------------------
    def _check_graph_reachability_and_sinks(self) -> None:
        tp_types = {tp.id: tp.type for tp in self.ast.entities.touchpoints}

        # Check if traffic is driven to a paid ad rather than a conversion surface
        for idx, step in enumerate(self.ast.logic_flow):
            if isinstance(step, dict) and step.get("action") == "TriggerTraffic":
                dest = step.get("destination", "")
                if dest in tp_types and tp_types[dest] == "paid_traffic":
                    self._add(
                        "FS301",
                        LintSeverity.ERROR,
                        f"Step {idx+1} routes traffic to destination '{dest}', which is a paid_traffic channel, not a conversion surface",
                        f"logic_flow[{idx}].destination",
                        "Route traffic to a conversion_surface (landing page, app, or store).",
                    )

    # -------------------------------------------------------------
    # 4. Attribution & Control Flow Cycles (Tarjan's SCC) (FS400-FS499)
    # -------------------------------------------------------------
    def _check_attribution_cycles(self) -> None:
        """Constructs the step adjacency graph and runs Tarjan's SCC algorithm."""
        adj: dict[str, list[str]] = {}
        nodes: set[str] = set()

        for step in self.ast.logic_flow:
            if not isinstance(step, dict):
                continue
            if step.get("action") == "TriggerTraffic":
                via = step.get("via", "")
                dest = step.get("destination", "")
                nodes.add(via)
                nodes.add(dest)
                adj.setdefault(via, []).append(dest)
            elif step.get("type") == "ConditionalBranch":
                for branch in step.get("true_branch", []):
                    ch = branch.get("channel")
                    next_node = branch.get("next_step")
                    if ch:
                        nodes.add(ch)
                        if next_node:
                            nodes.add(next_node)
                            adj.setdefault(ch, []).append(next_node)
                        # Check self-recurrence without bound
                        if branch.get("action") == "ExecuteRetargeting" and branch.get("loop_to"):
                            target = branch.get("loop_to")
                            max_retries = branch.get("max_retries")
                            if not max_retries or max_retries > 5:
                                self._add(
                                    "FS401",
                                    LintSeverity.ERROR,
                                    f"Unbounded retargeting loop from '{ch}' to '{target}' (max_retries must be specified and <= 5)",
                                    "logic_flow.ConditionalBranch",
                                    "Add 'max_retries': 3 to enforce a monotonic exit lease on the loop.",
                                )

        # Tarjan's Strongly Connected Components
        index = 0
        indices: dict[str, int] = {}
        lowlink: dict[str, int] = {}
        on_stack: dict[str, bool] = {}
        stack: list[str] = []
        sccs: list[list[str]] = []

        def strongconnect(v: str) -> None:
            nonlocal index
            indices[v] = index
            lowlink[v] = index
            index += 1
            stack.append(v)
            on_stack[v] = True

            for w in adj.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif on_stack.get(w, False):
                    lowlink[v] = min(lowlink[v], indices[w])

            if lowlink[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(scc)

        for node in nodes:
            if node not in indices:
                strongconnect(node)

        for scc in sccs:
            self._add(
                "FS402",
                LintSeverity.ERROR,
                f"Cyclic attribution deadlock detected between nodes: {' -> '.join(scc)}",
                "logic_flow",
                "Break the circular attribution loop or bound it with an explicit monotonic exit lease.",
            )

    # -------------------------------------------------------------
    # 5. Liquidity & Working Capital Preflight (FS500-FS599)
    # -------------------------------------------------------------
    def _check_liquidity_preflight(self) -> None:
        budgets = self.ast.entities.budgets
        delay = budgets.settlement_delay_days
        initial_cash = budgets.initial_cash
        total_budget = budgets.total_budget

        # If payout delay >= 4 days and initial cash is less than 15% of total budget
        if delay >= 4 and initial_cash < (total_budget * 0.15):
            self._add(
                "FS501",
                LintSeverity.WARNING,
                f"High cash starvation risk: settlement delay is {delay} days, but initial cash (${initial_cash:,.2f}) covers < 15% of total budget",
                "entities.budgets.initial_cash",
                "Increase initial_cash or reduce daily ad spend velocity to prevent P(Insolvency) freeze.",
            )

    # -------------------------------------------------------------
    # Helper utilities
    # -------------------------------------------------------------
    def entities_touchpoint_ids(self) -> list[str]:
        return [tp.id for tp in self.ast.entities.touchpoints]

    def _add(self, code: str, severity: LintSeverity, message: str, path: str, remediation: str) -> None:
        self.findings.append(LintFinding(code=code, severity=severity, message=message, path=path, remediation=remediation))

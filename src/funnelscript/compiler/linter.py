from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from funnelscript.compiler.diagnostics import TraitConformanceError
from funnelscript.compiler.dimensions import DimensionParser
from funnelscript.compiler.world_ast import (
    EntityDefinition,
    LiteralExpression,
    PayloadFieldExpression,
    PostStatementDefinition,
    ReferenceExpression,
    TraitDefinition,
    TraitMemberDefinition,
    WorldAST,
)
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


class WorldLinter:
    """Static Trait resolution, conformance, and dimensional invariant verifier for WorldAST."""

    def __init__(self, world: WorldAST) -> None:
        self.world = world
        self.errors: list[TraitConformanceError] = []

    def lint(self) -> list[TraitConformanceError]:
        self.errors.clear()
        traits: dict[str, TraitDefinition] = {
            d.name: d for d in self.world.declarations if isinstance(d, TraitDefinition)
        }
        for decl in self.world.declarations:
            if isinstance(decl, EntityDefinition):
                self._check_entity_traits(decl, traits)
                self._check_entity_postings(decl)
        from funnelscript.compiler.dimensions import DimensionalTypeChecker
        dim_errors = DimensionalTypeChecker.check_world(self.world)
        self.errors.extend(dim_errors)
        return list(self.errors)

    def check(self) -> None:
        errors = self.lint()
        if errors:
            raise errors[0]

    def _check_entity_traits(self, entity: EntityDefinition, traits: dict[str, TraitDefinition]) -> None:
        # Check for diamond collisions across implemented traits
        member_sources: dict[str, list[tuple[str, TraitMemberDefinition]]] = {}
        for trait_name in entity.implements:
            base_trait_name = trait_name.split(".")[-1]
            trait_def = traits.get(trait_name) or traits.get(base_trait_name)
            if not trait_def:
                self.errors.append(
                    TraitConformanceError(
                        code="FNL-O301",
                        message=f"Entity '{entity.name}' implements unknown trait '{trait_name}'",
                        span=entity.span,
                        remediation=f"Declare or import trait '{trait_name}' before implementing it.",
                    )
                )
                continue

            for member in trait_def.members:
                member_sources.setdefault(member.name, []).append((trait_name, member))

        # Check FNL-O304: Diamond collision
        for member_name, sources in member_sources.items():
            if len(sources) > 1:
                types = {src[1].type_name for src in sources if src[1].type_name is not None}
                if len(types) > 1:
                    trait_names = ", ".join(f"'{src[0]}'" for src in sources)
                    self.errors.append(
                        TraitConformanceError(
                            code="FNL-O304",
                            message=f"Ambiguous Trait diamond collision: member '{member_name}' is defined with conflicting signatures by {trait_names} without disambiguation",
                            span=entity.span,
                            remediation=f"Explicitly qualify '{member_name}' in entity '{entity.name}' or harmonize trait member types.",
                        )
                    )

        # Build entity member maps
        entity_fields: dict[str, str] = {}
        entity_field_spans: dict[str, Any] = {}
        for s in entity.states:
            entity_fields[s.name] = s.type_name
            entity_field_spans[s.name] = s.span
        for p in entity.primitives:
            entity_fields[p.name] = p.type_spec
            entity_field_spans[p.name] = p.span

        entity_handlers: set[str] = set()
        for h in entity.handlers:
            clean = h.event.removeprefix("on_")
            entity_handlers.add(h.event)
            entity_handlers.add(clean)
            entity_handlers.add(clean.capitalize())
        for r in entity.rules:
            entity_handlers.add(r.event)
            entity_handlers.add(f"on_{r.event.lower()}")

        # Check FNL-O301 and FNL-O302
        for trait_name in entity.implements:
            base_trait_name = trait_name.split(".")[-1]
            trait_def = traits.get(trait_name) or traits.get(base_trait_name)
            if not trait_def:
                candidates = [t for name, t in traits.items() if name.endswith(f".{base_trait_name}")]
                if candidates:
                    trait_def = candidates[0]
            if not trait_def:
                continue

            for member in trait_def.members:
                if member.kind == "field":
                    if member.name not in entity_fields:
                        self.errors.append(
                            TraitConformanceError(
                                code="FNL-O301",
                                message=f"Missing required Trait field '{member.name}: {member.type_name}' from trait '{trait_name}' in entity '{entity.name}'",
                                span=entity.span,
                                remediation=f"Declare field '{member.name}: {member.type_name};' in entity '{entity.name}'.",
                            )
                        )
                    else:
                        expected_dim = DimensionParser.parse(member.type_name or "Scalar")
                        actual_dim = DimensionParser.parse(entity_fields[member.name])
                        if not actual_dim.is_compatible_with(expected_dim):
                            self.errors.append(
                                TraitConformanceError(
                                    code="FNL-O302",
                                    message=f"Dimensional unit mismatch for field '{member.name}' in entity '{entity.name}': expected {expected_dim}, got {actual_dim}",
                                    span=entity_field_spans.get(member.name, entity.span),
                                    remediation=f"Change field '{member.name}' type to {expected_dim} to conform with trait '{trait_name}'.",
                                )
                            )

                elif member.kind == "handler":
                    clean_handler = member.name.removeprefix("on_")
                    if clean_handler not in entity_handlers and member.name not in entity_handlers:
                        self.errors.append(
                            TraitConformanceError(
                                code="FNL-O301",
                                message=f"Missing required Trait lifecycle handler '{member.name}' from trait '{trait_name}' in entity '{entity.name}'",
                                span=entity.span,
                                remediation=f"Implement lifecycle handler '{member.name} -> {{ ... }}' in entity '{entity.name}'.",
                            )
                        )

    def _check_entity_postings(self, entity: EntityDefinition) -> None:
        for handler in entity.handlers:
            for action in handler.actions:
                if isinstance(action, PostStatementDefinition):
                    debit_sum = 0
                    credit_sum = 0
                    has_literal = False
                    symbolic_debits: list[str] = []
                    symbolic_credits: list[str] = []

                    for p in action.postings:
                        if isinstance(p.amount_expr, LiteralExpression) and isinstance(p.amount_expr.value, (int, float)):
                            has_literal = True
                            if p.operation == "debit":
                                debit_sum += p.amount_expr.value
                            else:
                                credit_sum += p.amount_expr.value
                        elif isinstance(p.amount_expr, ReferenceExpression):
                            if p.operation == "debit":
                                symbolic_debits.append(p.amount_expr.name)
                            else:
                                symbolic_credits.append(p.amount_expr.name)
                        elif isinstance(p.amount_expr, PayloadFieldExpression):
                            if p.operation == "debit":
                                symbolic_debits.append(f"payload.{p.amount_expr.name}")
                            else:
                                symbolic_credits.append(f"payload.{p.amount_expr.name}")

                    if len(action.postings) < 2:
                        self.errors.append(
                            TraitConformanceError(
                                code="FNL-O303",
                                message=f"Unbalanced double-entry posting in handler '{handler.event}' of entity '{entity.name}': double-entry requires at least one debit and one credit",
                                span=action.span or handler.span,
                                remediation="Provide balanced debit(...) and credit(...) legs in the post statement.",
                            )
                        )
                        continue

                    if has_literal and debit_sum != credit_sum and not symbolic_debits and not symbolic_credits:
                        self.errors.append(
                            TraitConformanceError(
                                code="FNL-O303",
                                message=f"Unbalanced double-entry posting in handler '{handler.event}' of entity '{entity.name}': total debits ({debit_sum}) != total credits ({credit_sum})",
                                span=action.span or handler.span,
                                remediation=f"Ensure sum(debits) == sum(credits) in post statement (imbalance: {abs(debit_sum - credit_sum)}).",
                            )
                        )
                    elif (
                        symbolic_debits
                        and symbolic_credits
                        and sorted(symbolic_debits) != sorted(symbolic_credits)
                        and has_literal
                        and debit_sum != credit_sum
                    ):
                        self.errors.append(
                                TraitConformanceError(
                                    code="FNL-O303",
                                    message=f"Unbalanced double-entry posting in handler '{handler.event}' of entity '{entity.name}': asymmetric debit/credit legs",
                                    span=action.span or handler.span,
                                    remediation="Ensure every debit leg has an equal and opposite credit leg.",
                                )
                            )

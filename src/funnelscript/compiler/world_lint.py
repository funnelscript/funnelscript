"""Advisory static control-flow and payload-use analysis for typed Worlds.

Only facts proved from closed, immutable declarations are flagged as unreachable.
Events can arrive externally, so absence of a source emitter is never reported.
This analyzer never modifies the source AST or substitutes for type checking.
"""

from __future__ import annotations

import linecache
import operator
from dataclasses import dataclass
from typing import ClassVar

from funnelscript.compiler.world_ast import (
    BinaryExpression,
    EntityDefinition,
    EventRuleDefinition,
    PayloadFieldExpression,
    SampleExpression,
    StateExpression,
    WorldAST,
    WorldTypeChecker,
)
from funnelscript.tokens import SourceSpan, diagnostic_excerpt


@dataclass(frozen=True, slots=True)
class WorldLintFinding:
    """A stable, non-fatal diagnostic with its originating source location."""

    code: str
    message: str
    subject: str
    hint: str
    span: SourceSpan | None
    severity: str = "warning"

    def render(self) -> str:
        if self.span is None:
            return f"{self.code} {self.subject}: {self.message}\nHint: {self.hint}"
        span = self.span
        location = (
            f"{span.file}: line {span.start_line}, column {span.start_col}"
        )
        line = linecache.getline(span.file, span.start_line).rstrip("\r\n")
        width = span.end_col - span.start_col if span.start_line == span.end_line else 1
        excerpt = diagnostic_excerpt(line, span.start_col, width) if line else ""
        return (
            f"{self.code} {location}\n{excerpt}\n"
            f"{self.subject}: {self.message}\nHint: {self.hint}"
        )


def _payload_refs(expression: StateExpression) -> set[str]:
    """Find payload reads, including nested arithmetic and sample arguments."""
    if isinstance(expression, PayloadFieldExpression):
        return {expression.name}
    if isinstance(expression, BinaryExpression):
        return _payload_refs(expression.left) | _payload_refs(expression.right)
    if isinstance(expression, SampleExpression):
        referenced: set[str] = set()
        for argument in expression.arguments:
            referenced.update(_payload_refs(argument))
        return referenced
    return set()


def _fields_read(rule: EventRuleDefinition) -> set[str]:
    names: set[str] = set()
    for transition in rule.transitions:
        names.update(_payload_refs(transition.expr))
    for emission in rule.emissions:
        for expression in emission.arguments.values():
            names.update(_payload_refs(expression))
    return names


class WorldLinter:
    """Produce stable warnings about provably dead declarations and reads."""

    COMPARISONS: ClassVar[dict[str, object]] = {
        "==": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
    }

    def __init__(self, ast: WorldAST) -> None:
        if not isinstance(ast, WorldAST):
            raise TypeError("WorldLinter requires a WorldAST")
        self.ast = ast

    def lint(self) -> tuple[WorldLintFinding, ...]:
        WorldTypeChecker.check(self.ast)
        findings: list[WorldLintFinding] = []
        findings.extend(self._unhandled_events())
        findings.extend(self._unused_payload_fields())
        findings.extend(self._unreachable_guards())
        findings.extend(self._noop_handlers())
        return tuple(findings)

    def _unhandled_events(self) -> list[WorldLintFinding]:
        result: list[WorldLintFinding] = []
        for decl in self.ast.declarations:
            handled = {rule.event for rule in decl.rules}
            for event in decl.events:
                if event.name in handled:
                    continue
                result.append(WorldLintFinding(
                    code="FNL-W301",
                    subject=f"{decl.name}.{event.name}",
                    message=f"Declared event '{event.name}' is never handled in this World.",
                    hint="Add a rule on this event or remove its unused declaration.",
                    span=event.span,
                ))
        return result

    def _unused_payload_fields(self) -> list[WorldLintFinding]:
        result: list[WorldLintFinding] = []
        for decl in self.ast.declarations:
            rules = {rule.event: rule for rule in decl.rules}
            for event in decl.events:
                rule = rules.get(event.name)
                if rule is None:
                    continue
                reads = _fields_read(rule)
                for field in event.fields:
                    if field.name in reads:
                        continue
                    result.append(WorldLintFinding(
                        code="FNL-W302",
                        subject=f"{decl.name}.{event.name}.{field.name}",
                        message=(
                            f"Payload field '{field.name}' is not read by its event handler."
                        ),
                        hint="Read the field with payload.<name> or remove the field.",
                        span=field.span,
                    ))
        return result

    def _unreachable_guards(self) -> list[WorldLintFinding]:
        result: list[WorldLintFinding] = []
        for decl in self.ast.declarations:
            result.extend(self._unreachable_in_declaration(decl))
        return result

    def _unreachable_in_declaration(
        self, decl: EntityDefinition,
    ) -> list[WorldLintFinding]:
        state = {item.name: item.value for item in decl.states}
        writable = {
            transition.target
            for rule in decl.rules
            for transition in rule.transitions
        }
        findings: list[WorldLintFinding] = []
        for rule in decl.rules:
            guard = rule.guard
            if guard is None or guard.field in writable:
                continue
            compares = self.COMPARISONS[guard.operator]
            if compares(state[guard.field], guard.value):
                continue
            findings.append(WorldLintFinding(
                code="FNL-W303",
                subject=f"{decl.name}.{rule.name}",
                message=(
                    f"Rule cannot run: guard state '{guard.field}' never changes "
                    "and its initial value contradicts the guard."
                ),
                hint="Make the guard satisfiable or declare an explicit state transition.",
                span=rule.span,
            ))
        return findings

    def _noop_handlers(self) -> list[WorldLintFinding]:
        findings: list[WorldLintFinding] = []
        for decl in self.ast.declarations:
            for rule in decl.rules:
                if rule.transitions or rule.emissions:
                    continue
                findings.append(WorldLintFinding(
                    code="FNL-W304",
                    subject=f"{decl.name}.{rule.name}",
                    message=(
                        "This event handler neither changes state nor emits events."
                    ),
                    hint="Add a transition or emission, or remove the inert handler.",
                    span=rule.span,
                ))
        return findings

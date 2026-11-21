"""Typed, domain-neutral World declaration AST and primitive state checker.

Research: funnelscript-research/spec/world-declarations-v0.md (H-W1 to H-W4).
"""

from __future__ import annotations

import linecache
import math
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field

from funnelscript.tokens import SourceSpan, diagnostic_excerpt


class LocatedNode(BaseModel):
    span: SourceSpan | None = Field(default=None, exclude=True, repr=False)


class StateDefinition(LocatedNode):
    name: str
    type_name: str
    value: object


class PayloadFieldExpression(LocatedNode):
    kind: Literal["payload_field"] = "payload_field"
    name: str


class LiteralExpression(LocatedNode):
    kind: Literal["literal"] = "literal"
    value: object


class ReferenceExpression(LocatedNode):
    kind: Literal["reference"] = "reference"
    name: str


class BinaryExpression(LocatedNode):
    kind: Literal["binary"] = "binary"
    operator: Literal["+", "-", "*", "/"]
    left: StateExpression
    right: StateExpression


class SampleExpression(LocatedNode):
    kind: Literal["sample"] = "sample"
    distribution: Literal["bernoulli", "uniform"]
    arguments: list[LiteralExpression | ReferenceExpression | PayloadFieldExpression]


StateExpression = Annotated[
    LiteralExpression | ReferenceExpression | PayloadFieldExpression | BinaryExpression
    | SampleExpression,
    Field(discriminator="kind"),
]


class StateTransitionDefinition(LocatedNode):
    target: str
    expr: StateExpression


class EventFieldDefinition(LocatedNode):
    name: str
    type_name: str


class EventDefinition(LocatedNode):
    name: str
    fields: list[EventFieldDefinition] = Field(default_factory=list)


class EventEmissionDefinition(LocatedNode):
    event: str
    delay: object
    arguments: dict[str, StateExpression] = Field(default_factory=dict)


class GuardDefinition(LocatedNode):
    field: str
    operator: Literal["==", "!=", "<", "<=", ">", ">="]
    value: object


class EventRuleDefinition(LocatedNode):
    name: str
    event: str
    guard: GuardDefinition | None = None
    transitions: list[StateTransitionDefinition] = Field(default_factory=list)
    emissions: list[EventEmissionDefinition] = Field(default_factory=list)


class EntityDefinition(LocatedNode):
    kind: Literal["entity"] = "entity"
    name: str
    states: list[StateDefinition] = Field(default_factory=list)
    events: list[EventDefinition] = Field(default_factory=list)
    rules: list[EventRuleDefinition] = Field(default_factory=list)


class AgentDefinition(EntityDefinition):
    kind: Literal["agent"] = "agent"


WorldDeclaration = Annotated[
    EntityDefinition | AgentDefinition, Field(discriminator="kind")
]


class WorldAST(LocatedNode):
    kind: Literal["world"] = "world"
    name: str
    declarations: list[WorldDeclaration] = Field(default_factory=list)


class WorldTypeError(ValueError):
    """A source declaration violates the primitive typing contract."""

    def __init__(self, message: str, *, span: SourceSpan | None = None) -> None:
        super().__init__(message)
        self.span = span

    def __str__(self) -> str:
        message = super().__str__()
        if self.span is None:
            return message
        span = self.span
        line = linecache.getline(span.file, span.start_line).rstrip("\r\n")
        width = span.end_col - span.start_col if span.start_line == span.end_line else 1
        excerpt = diagnostic_excerpt(line, span.start_col, width) if line else ""
        return (
            f"FNL-T201 {span.file}: line {span.start_line}, column {span.start_col}\n"
            f"{excerpt}\nWorldTypeError: {message}\n"
            "Hint: Verify declaration names, field references, and primitive types."
        )


@contextmanager
def _located(node: LocatedNode) -> Iterator[None]:
    """Preserve the nearest originating AST span on semantic failure."""
    try:
        yield
    except WorldTypeError as error:
        if error.span is None:
            error.span = node.span
        raise


class WorldTypeChecker:
    """Checks declaration uniqueness and exact primitive literal types."""

    PRIMITIVES: ClassVar[dict[str, type]] = {"int": int, "float": float, "bool": bool, "string": str}

    @classmethod
    def check(cls, world: WorldAST) -> None:
        names: set[str] = set()
        for declaration in world.declarations:
            with _located(declaration):
                if declaration.name in names:
                    raise WorldTypeError(f"Duplicate declaration '{declaration.name}'")
                names.add(declaration.name)
                cls._check_states(declaration)
                cls._check_rules(declaration)

    @classmethod
    def _check_states(cls, declaration: EntityDefinition) -> None:
        fields: set[str] = set()
        for state in declaration.states:
            with _located(state):
                if state.name in fields:
                    raise WorldTypeError(
                        f"Duplicate state '{state.name}' in '{declaration.name}'"
                    )
                fields.add(state.name)
                expected = cls.PRIMITIVES.get(state.type_name)
                if expected is None:
                    raise WorldTypeError(
                        f"Unknown state type '{state.type_name}' for '{state.name}'"
                    )
                if type(state.value) is not expected:
                    raise WorldTypeError(
                        f"Type mismatch for '{declaration.name}.{state.name}': "
                        f"expected {state.type_name}, got {type(state.value).__name__}"
                    )

    @classmethod
    def _event_types(cls, declaration: EntityDefinition) -> dict[str, dict[str, str]]:
        schemas: dict[str, dict[str, str]] = {}
        for event in declaration.events:
            with _located(event):
                if event.name in schemas:
                    raise WorldTypeError(f"Duplicate event declaration '{event.name}'")
                schemas[event.name] = cls._event_fields(event)
        return schemas

    @classmethod
    def _event_fields(cls, event: EventDefinition) -> dict[str, str]:
        fields: dict[str, str] = {}
        for field in event.fields:
            with _located(field):
                if field.name in fields:
                    raise WorldTypeError(f"Duplicate event field '{field.name}'")
                if field.type_name not in cls.PRIMITIVES:
                    raise WorldTypeError(f"Unknown event field type '{field.type_name}'")
                fields[field.name] = field.type_name
        return fields

    @classmethod
    def _check_rules(cls, declaration: EntityDefinition) -> None:
        types = {state.name: state.type_name for state in declaration.states}
        event_types = cls._event_types(declaration)
        names: set[str] = set()
        events: set[str] = set()
        declared_events = {rule.event for rule in declaration.rules}
        for rule in declaration.rules:
            with _located(rule):
                if rule.name in names:
                    raise WorldTypeError(f"Duplicate rule '{rule.name}'")
                if rule.event in events:
                    raise WorldTypeError(f"Duplicate event handler '{rule.event}'")
                names.add(rule.name)
                events.add(rule.event)
                if rule.guard is not None:
                    with _located(rule.guard):
                        cls._check_guard(rule.guard, types)
                cls._check_transitions(rule, types, event_types)
                cls._check_emissions(rule, declared_events, types, event_types)

    @classmethod
    def _check_transitions(
        cls, rule: EventRuleDefinition, types: dict[str, str],
        event_types: dict[str, dict[str, str]],
    ) -> None:
        targets: set[str] = set()
        for transition in rule.transitions:
            with _located(transition):
                target = transition.target
                if target in targets:
                    raise WorldTypeError(f"Duplicate transition target '{target}'")
                if target not in types:
                    raise WorldTypeError(f"Unknown transition target '{target}'")
                targets.add(target)
                actual_type = cls._expression_type(
                    transition.expr, types, event_types.get(rule.event, {})
                )
                if actual_type != types[target]:
                    raise WorldTypeError(
                        f"Type mismatch assigning '{target}': "
                        f"expected {types[target]}, got {actual_type}"
                    )

    @classmethod
    def _check_emissions(
        cls, rule: EventRuleDefinition, declared_events: set[str],
        types: dict[str, str], event_types: dict[str, dict[str, str]],
    ) -> None:
        for emission in rule.emissions:
            with _located(emission):
                if emission.event not in declared_events:
                    raise WorldTypeError(f"Unknown emitted event '{emission.event}'")
                cls._check_payload_arguments(
                    emission.arguments,
                    event_types.get(emission.event, {}),
                    types,
                    event_types.get(rule.event, {}),
                )
                delay = emission.delay
                if type(delay) not in (int, float):
                    raise WorldTypeError("Event emission delay must be numeric")
                try:
                    finite = math.isfinite(float(delay))
                except OverflowError:
                    finite = False
                if not finite or delay < 0:
                    raise WorldTypeError("Event emission delay must be finite and non-negative")

    @classmethod
    def _check_payload_arguments(
        cls,
        arguments: dict[str, StateExpression],
        schema: dict[str, str],
        state_types: dict[str, str],
        current_payload: dict[str, str],
    ) -> None:
        missing = schema.keys() - arguments.keys()
        extra = arguments.keys() - schema.keys()
        if extra:
            raise WorldTypeError(f"Unexpected event arguments: {sorted(extra)}")
        if missing:
            raise WorldTypeError(f"Missing event arguments: {sorted(missing)}")
        for name, expr in arguments.items():
            if isinstance(expr, SampleExpression):
                raise WorldTypeError("Sampling is only permitted in transitions")
            actual = cls._expression_type(expr, state_types, current_payload)
            if actual != schema[name]:
                raise WorldTypeError(
                    f"Type mismatch in emitted argument '{name}': "
                    f"expected {schema[name]}, got {actual}"
                )

    @classmethod
    def _check_guard(cls, guard: GuardDefinition, types: dict[str, str]) -> None:
        type_name = types.get(guard.field)
        if type_name is None:
            raise WorldTypeError(f"Unknown guard field '{guard.field}'")
        expected = cls.PRIMITIVES[type_name]
        if type(guard.value) is not expected:
            raise WorldTypeError(
                f"Type mismatch in guard '{guard.field}': expected {type_name}"
            )
        if guard.operator in ("<", "<=", ">", ">=") and type_name not in ("int", "float"):
            raise WorldTypeError("Ordered guard comparisons require numeric types")

    @classmethod
    def _expression_type(
        cls, expr: StateExpression, types: dict[str, str],
        payload_types: dict[str, str] | None = None,
    ) -> str:
        if isinstance(expr, LiteralExpression):
            if type(expr.value) is float and not math.isfinite(expr.value):
                raise WorldTypeError("Non-finite float literal")
            for name, value_type in cls.PRIMITIVES.items():
                if type(expr.value) is value_type:
                    return name
            raise WorldTypeError("Unknown literal value type")
        if isinstance(expr, ReferenceExpression):
            if expr.name not in types:
                raise WorldTypeError(f"Unknown state reference '{expr.name}'")
            return types[expr.name]
        if isinstance(expr, PayloadFieldExpression):
            if expr.name not in (payload_types or {}):
                raise WorldTypeError(f"Unknown payload field '{expr.name}'")
            return payload_types[expr.name]
        if isinstance(expr, SampleExpression):
            return cls._sample_type(expr, types, payload_types or {})
        if isinstance(expr, BinaryExpression):
            if cls._expression_depth(expr) > 24:
                raise WorldTypeError("Arithmetic expression depth limit exceeded")
            left_type = cls._expression_type(expr.left, types, payload_types)
            right_type = cls._expression_type(expr.right, types, payload_types)
            if left_type not in ("int", "float") or right_type not in ("int", "float"):
                raise WorldTypeError("Binary arithmetic requires numeric operands")
            if left_type != right_type:
                raise WorldTypeError(
                    f"Type mismatch in arithmetic: {left_type} versus {right_type}"
                )
            if expr.operator == "/":
                if isinstance(expr.right, LiteralExpression) and expr.right.value == 0:
                    raise WorldTypeError("Division by literal zero")
                return "float"
            return left_type
        raise WorldTypeError("Unknown state expression")

    @staticmethod
    def _expression_depth(expr: StateExpression) -> int:
        if not isinstance(expr, BinaryExpression):
            return 1
        return 1 + max(WorldTypeChecker._expression_depth(expr.left),
                       WorldTypeChecker._expression_depth(expr.right))

    @classmethod
    def _sample_type(
        cls, expr: SampleExpression, types: dict[str, str], payload_types: dict[str, str]
    ) -> str:
        expected_count = 1 if expr.distribution == "bernoulli" else 2
        if len(expr.arguments) != expected_count:
            raise WorldTypeError(
                f"Invalid {expr.distribution} argument count: expected {expected_count}"
            )
        for argument in expr.arguments:
            if cls._expression_type(argument, types, payload_types) != "float":
                raise WorldTypeError("Distribution arguments must have exact float type")
            if isinstance(argument, LiteralExpression) and not math.isfinite(argument.value):
                raise WorldTypeError("Distribution arguments must be finite")
        literals = [
            argument.value if isinstance(argument, LiteralExpression) else None
            for argument in expr.arguments
        ]
        if expr.distribution == "bernoulli":
            if literals[0] is not None and not 0.0 <= literals[0] <= 1.0:
                raise WorldTypeError("Bernoulli probability must be in [0, 1]")
            return "bool"
        lower, upper = literals
        if lower is not None and upper is not None:
            if lower > upper:
                raise WorldTypeError("Uniform bounds must satisfy low <= high")
            if not math.isfinite(upper - lower):
                raise WorldTypeError("Uniform span must be finite")
        return "float"

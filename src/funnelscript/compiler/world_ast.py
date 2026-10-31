"""Typed, domain-neutral World declaration AST and primitive state checker.

Research: funnelscript-research/spec/world-declarations-v0.md (H-W1 to H-W4).
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class StateDefinition(BaseModel):
    name: str
    type_name: str
    value: object


class PayloadFieldExpression(BaseModel):
    kind: Literal["payload_field"] = "payload_field"
    name: str


class LiteralExpression(BaseModel):
    kind: Literal["literal"] = "literal"
    value: object


class ReferenceExpression(BaseModel):
    kind: Literal["reference"] = "reference"
    name: str


class BinaryExpression(BaseModel):
    kind: Literal["binary"] = "binary"
    operator: Literal["+", "-"]
    left: ReferenceExpression
    right: LiteralExpression | PayloadFieldExpression


StateExpression = Annotated[
    LiteralExpression | ReferenceExpression | PayloadFieldExpression | BinaryExpression,
    Field(discriminator="kind"),
]


class StateTransitionDefinition(BaseModel):
    target: str
    expr: StateExpression


class EventFieldDefinition(BaseModel):
    name: str
    type_name: str


class EventDefinition(BaseModel):
    name: str
    fields: list[EventFieldDefinition] = Field(default_factory=list)


class EventEmissionDefinition(BaseModel):
    event: str
    delay: object
    arguments: dict[str, StateExpression] = Field(default_factory=dict)


class GuardDefinition(BaseModel):
    field: str
    operator: Literal["==", "!=", "<", "<=", ">", ">="]
    value: object


class EventRuleDefinition(BaseModel):
    name: str
    event: str
    guard: GuardDefinition | None = None
    transitions: list[StateTransitionDefinition] = Field(default_factory=list)
    emissions: list[EventEmissionDefinition] = Field(default_factory=list)


class EntityDefinition(BaseModel):
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


class WorldAST(BaseModel):
    kind: Literal["world"] = "world"
    name: str
    declarations: list[WorldDeclaration] = Field(default_factory=list)


class WorldTypeError(ValueError):
    """A source declaration violates the primitive typing contract."""


class WorldTypeChecker:
    """Checks declaration uniqueness and exact primitive literal types."""

    PRIMITIVES = {"int": int, "float": float, "bool": bool, "string": str}

    @classmethod
    def check(cls, world: WorldAST) -> None:
        names: set[str] = set()
        for declaration in world.declarations:
            if declaration.name in names:
                raise WorldTypeError(f"Duplicate declaration '{declaration.name}'")
            names.add(declaration.name)

            fields: set[str] = set()
            for state in declaration.states:
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
            cls._check_rules(declaration)


    @classmethod
    def _event_types(cls, declaration: EntityDefinition) -> dict[str, dict[str, str]]:
        schemas: dict[str, dict[str, str]] = {}
        for event in declaration.events:
            if event.name in schemas:
                raise WorldTypeError(f"Duplicate event declaration '{event.name}'")
            fields: dict[str, str] = {}
            for field in event.fields:
                if field.name in fields:
                    raise WorldTypeError(f"Duplicate event field '{field.name}'")
                if field.type_name not in cls.PRIMITIVES:
                    raise WorldTypeError(f"Unknown event field type '{field.type_name}'")
                fields[field.name] = field.type_name
            schemas[event.name] = fields
        return schemas

    @classmethod
    def _check_rules(cls, declaration: EntityDefinition) -> None:
        types = {state.name: state.type_name for state in declaration.states}
        event_types = cls._event_types(declaration)
        names: set[str] = set()
        events: set[str] = set()
        declared_events = {rule.event for rule in declaration.rules}
        for rule in declaration.rules:
            if rule.name in names:
                raise WorldTypeError(f"Duplicate rule '{rule.name}'")
            if rule.event in events:
                raise WorldTypeError(f"Duplicate event handler '{rule.event}'")
            names.add(rule.name)
            events.add(rule.event)
            if rule.guard is not None:
                cls._check_guard(rule.guard, types)

            targets: set[str] = set()
            for transition in rule.transitions:
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

            for emission in rule.emissions:
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
        if isinstance(expr, BinaryExpression):
            left_type = cls._expression_type(expr.left, types, payload_types)
            right_type = cls._expression_type(expr.right, types, payload_types)
            if left_type not in ("int", "float") or right_type not in ("int", "float"):
                raise WorldTypeError("Binary arithmetic requires numeric operands")
            if left_type != right_type:
                raise WorldTypeError(
                    f"Type mismatch in arithmetic: {left_type} versus {right_type}"
                )
            return left_type
        raise WorldTypeError("Unknown state expression")

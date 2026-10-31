"""Typed, domain-neutral World declaration AST and primitive state checker.

Research: funnelscript-research/spec/world-declarations-v0.md (H-W1 to H-W4).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class StateDefinition(BaseModel):
    name: str
    type_name: str
    value: object


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
    right: LiteralExpression


StateExpression = Annotated[
    LiteralExpression | ReferenceExpression | BinaryExpression,
    Field(discriminator="kind"),
]


class StateTransitionDefinition(BaseModel):
    target: str
    expr: StateExpression


class EventRuleDefinition(BaseModel):
    name: str
    event: str
    transitions: list[StateTransitionDefinition] = Field(default_factory=list)


class EntityDefinition(BaseModel):
    kind: Literal["entity"] = "entity"
    name: str
    states: list[StateDefinition] = Field(default_factory=list)
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
    def _check_rules(cls, declaration: EntityDefinition) -> None:
        types = {state.name: state.type_name for state in declaration.states}
        names: set[str] = set()
        events: set[str] = set()
        for rule in declaration.rules:
            if rule.name in names:
                raise WorldTypeError(f"Duplicate rule '{rule.name}'")
            if rule.event in events:
                raise WorldTypeError(f"Duplicate event handler '{rule.event}'")
            names.add(rule.name)
            events.add(rule.event)

            targets: set[str] = set()
            for transition in rule.transitions:
                target = transition.target
                if target in targets:
                    raise WorldTypeError(f"Duplicate transition target '{target}'")
                if target not in types:
                    raise WorldTypeError(f"Unknown transition target '{target}'")
                targets.add(target)
                actual_type = cls._expression_type(transition.expr, types)
                if actual_type != types[target]:
                    raise WorldTypeError(
                        f"Type mismatch assigning '{target}': "
                        f"expected {types[target]}, got {actual_type}"
                    )

    @classmethod
    def _expression_type(cls, expr: StateExpression, types: dict[str, str]) -> str:
        if isinstance(expr, LiteralExpression):
            for name, value_type in cls.PRIMITIVES.items():
                if type(expr.value) is value_type:
                    return name
            raise WorldTypeError("Unknown literal value type")
        if isinstance(expr, ReferenceExpression):
            if expr.name not in types:
                raise WorldTypeError(f"Unknown state reference '{expr.name}'")
            return types[expr.name]
        if isinstance(expr, BinaryExpression):
            left_type = cls._expression_type(expr.left, types)
            right_type = cls._expression_type(expr.right, types)
            if left_type not in ("int", "float") or right_type not in ("int", "float"):
                raise WorldTypeError("Binary arithmetic requires numeric operands")
            if left_type != right_type:
                raise WorldTypeError(
                    f"Type mismatch in arithmetic: {left_type} versus {right_type}"
                )
            return left_type
        raise WorldTypeError("Unknown state expression")

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


class EntityDefinition(BaseModel):
    kind: Literal["entity"] = "entity"
    name: str
    states: list[StateDefinition] = Field(default_factory=list)


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

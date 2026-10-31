"""Interpret type-checked World rules via the existing discrete-event machine.

Research: funnelscript-research/spec/rule-transitions-v0.md (H-R1 to H-R4).
"""

from __future__ import annotations

from collections.abc import Iterable

from funnelscript.compiler.world_ast import (
    BinaryExpression,
    EventRuleDefinition,
    LiteralExpression,
    ReferenceExpression,
    StateExpression,
    GuardDefinition,
    WorldAST,
    WorldTypeChecker,
)
from funnelscript.core.event_machine import Event, EventMachine, RunResult, Transition

WorldState = dict[str, dict[str, object]]


class WorldExecutionError(ValueError):
    """A supplied event cannot be dispatched to a declared World rule."""


class WorldExecutor:
    """Execute a domain-neutral World without external effects or model templates."""

    def __init__(self, world: WorldAST) -> None:
        WorldTypeChecker.check(world)
        # Retain a private snapshot of checked definitions: callers may mutate ASTs.
        self.world = world.model_copy(deep=True)
        self.handlers: dict[str, tuple[str, EventRuleDefinition]] = {}
        for declaration in self.world.declarations:
            for rule in declaration.rules:
                key = f"{declaration.name}.{rule.event}"
                self.handlers[key] = (declaration.name, rule)

    def initial_state(self) -> WorldState:
        return {
            decl.name: {field.name: field.value for field in decl.states}
            for decl in self.world.declarations
        }

    @staticmethod
    def _evaluate(expr: StateExpression, snapshot: dict[str, object]) -> object:
        if isinstance(expr, LiteralExpression):
            return expr.value
        if isinstance(expr, ReferenceExpression):
            return snapshot[expr.name]
        if isinstance(expr, BinaryExpression):
            left = snapshot[expr.left.name]
            right = expr.right.value
            return left + right if expr.operator == "+" else left - right
        raise WorldExecutionError("Unknown expression type")

    @staticmethod
    def _guard_matches(guard: GuardDefinition | None, snapshot: dict[str, object]) -> bool:
        if guard is None:
            return True
        left, right = snapshot[guard.field], guard.value
        if guard.operator == "==":
            return left == right
        if guard.operator == "!=":
            return left != right
        if guard.operator == "<":
            return left < right
        if guard.operator == "<=":
            return left <= right
        if guard.operator == ">":
            return left > right
        return left >= right

    def _updated_state(
        self, state: WorldState, owner: str, rule: EventRuleDefinition
    ) -> WorldState:
        snapshot = state[owner]
        updates = {
            item.target: self._evaluate(item.expr, snapshot)
            for item in rule.transitions
        }
        return {**state, owner: {**snapshot, **updates}}

    def advance(self, state: WorldState, event: Event) -> WorldState:
        """Apply a rule only when its guard matches the pre-event state."""
        handler = self.handlers.get(event.name)
        if handler is None:
            raise WorldExecutionError(f"Unknown event '{event.name}'")
        owner, rule = handler
        if not self._guard_matches(rule.guard, state[owner]):
            return state
        return self._updated_state(state, owner, rule)

    def _step(self, state: WorldState, event: Event) -> Transition[WorldState]:
        handler = self.handlers.get(event.name)
        if handler is None:
            raise WorldExecutionError(f"Unknown event '{event.name}'")
        owner, rule = handler
        if not self._guard_matches(rule.guard, state[owner]):
            return Transition(state=state)
        updated = self._updated_state(state, owner, rule)
        scheduled = tuple(
            Event(
                time=event.time + emission.delay,
                name=f"{owner}.{emission.event}",
                priority=event.priority,
            )
            for emission in rule.emissions
        )
        return Transition(state=updated, events=scheduled)

    def run(
        self,
        events: Iterable[Event],
        *,
        seed: int = 0,
        until: float | None = None,
        max_events: int = 100_000,
    ) -> RunResult[WorldState]:
        """Lower source rules to a pure reducer using the existing event calendar."""
        machine = EventMachine(lambda state, event, rng: self._step(state, event))
        return machine.run(
            self.initial_state(), events, seed=seed, until=until, max_events=max_events
        )

"""Interpret type-checked World rules via the existing discrete-event machine.

Research: funnelscript-research/spec/rule-transitions-v0.md (H-R1 to H-R4).
"""

from __future__ import annotations

from collections.abc import Iterable
import math
import random

from funnelscript.compiler.world_ast import (
    BinaryExpression,
    EventEmissionDefinition,
    EventRuleDefinition,
    LiteralExpression,
    PayloadFieldExpression,
    ReferenceExpression,
    SampleExpression,
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
        self.event_schemas: dict[str, dict[str, type]] = {}
        for declaration in self.world.declarations:
            for schema in declaration.events:
                self.event_schemas[f"{declaration.name}.{schema.name}"] = {
                    field.name: WorldTypeChecker.PRIMITIVES[field.type_name]
                    for field in schema.fields
                }
            for rule in declaration.rules:
                key = f"{declaration.name}.{rule.event}"
                self.handlers[key] = (declaration.name, rule)

    def initial_state(self) -> WorldState:
        return {
            decl.name: {field.name: field.value for field in decl.states}
            for decl in self.world.declarations
        }

    @staticmethod
    def _evaluate(
        expr: StateExpression, snapshot: dict[str, object],
        payload: dict[str, object] | None = None,
        rng: random.Random | None = None,
    ) -> object:
        if isinstance(expr, SampleExpression):
            return WorldExecutor._sample(expr, snapshot, payload, rng)
        if isinstance(expr, LiteralExpression):
            return expr.value
        if isinstance(expr, ReferenceExpression):
            return snapshot[expr.name]
        if isinstance(expr, PayloadFieldExpression):
            return (payload or {})[expr.name]
        if isinstance(expr, BinaryExpression):
            left = snapshot[expr.left.name]
            right = WorldExecutor._evaluate(expr.right, snapshot, payload, rng)
            return left + right if expr.operator == "+" else left - right
        raise WorldExecutionError("Unknown expression type")

    @staticmethod
    def _sample(
        expr: SampleExpression, snapshot: dict[str, object],
        payload: dict[str, object] | None, rng: random.Random | None,
    ) -> bool | float:
        if rng is None:
            raise WorldExecutionError("Sampled transitions require an explicit RNG")
        values = [
            WorldExecutor._evaluate(item, snapshot, payload) for item in expr.arguments
        ]
        if any(type(value) is not float or not math.isfinite(value) for value in values):
            raise WorldExecutionError("Distribution arguments must be finite floats")
        if expr.distribution == "bernoulli":
            probability = values[0]
            if not 0.0 <= probability <= 1.0:
                raise WorldExecutionError("Bernoulli probability must be in [0, 1]")
            return rng.random() < probability
        low, high = values
        if low > high:
            raise WorldExecutionError("Uniform bounds must satisfy low <= high")
        span = high - low
        if not math.isfinite(span):
            raise WorldExecutionError("Uniform span must be finite")
        return low + span * rng.random()

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
        self, state: WorldState, owner: str, rule: EventRuleDefinition,
        payload: dict[str, object] | None = None,
        rng: random.Random | None = None,
    ) -> WorldState:
        snapshot = state[owner]
        updates = {
            item.target: self._evaluate(item.expr, snapshot, payload, rng)
            for item in rule.transitions
        }
        return {**state, owner: {**snapshot, **updates}}

    def _validated_payload(self, event: Event) -> dict[str, object]:
        schema = self.event_schemas.get(event.name, {})
        if event.payload is None:
            payload: dict[str, object] = {}
        elif type(event.payload) is dict:
            payload = event.payload
        else:
            raise WorldExecutionError("Event payload must be a plain mapping")
        if any(type(key) is not str for key in payload):
            raise WorldExecutionError("Unexpected non-string event payload field")
        extra = payload.keys() - schema.keys()
        missing = schema.keys() - payload.keys()
        if extra:
            raise WorldExecutionError(f"Unexpected event payload fields: {sorted(extra)}")
        if missing:
            raise WorldExecutionError(f"Missing event payload fields: {sorted(missing)}")
        for name, value in payload.items():
            if type(value) is not schema[name]:
                raise WorldExecutionError(f"Type mismatch in event payload field '{name}'")
            if type(value) is float and not math.isfinite(value):
                raise WorldExecutionError(f"Event payload field '{name}' must be finite")
        return payload

    def advance(
        self, state: WorldState, event: Event, *, rng: random.Random | None = None
    ) -> WorldState:
        """Apply a rule only when its guard matches the pre-event state."""
        handler = self.handlers.get(event.name)
        if handler is None:
            raise WorldExecutionError(f"Unknown event '{event.name}'")
        owner, rule = handler
        payload = self._validated_payload(event)
        if not self._guard_matches(rule.guard, state[owner]):
            return state
        return self._updated_state(state, owner, rule, payload, rng)

    def _emitted_event(
        self, owner: str, parent: Event, emission: EventEmissionDefinition,
        snapshot: dict[str, object], payload: dict[str, object],
    ) -> Event:
        record = (
            {name: self._evaluate(expr, snapshot, payload)
             for name, expr in emission.arguments.items()}
            if emission.arguments else None
        )
        emitted = Event(
            time=parent.time + emission.delay,
            name=f"{owner}.{emission.event}",
            payload=record,
            priority=parent.priority,
        )
        self._validated_payload(emitted)
        return emitted

    def _step(
        self, state: WorldState, event: Event, rng: random.Random
    ) -> Transition[WorldState]:
        handler = self.handlers.get(event.name)
        if handler is None:
            raise WorldExecutionError(f"Unknown event '{event.name}'")
        owner, rule = handler
        payload = self._validated_payload(event)
        if not self._guard_matches(rule.guard, state[owner]):
            return Transition(state=state)
        snapshot = state[owner]
        updated = self._updated_state(state, owner, rule, payload, rng)
        scheduled = tuple(
            self._emitted_event(owner, event, emission, snapshot, payload)
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
        machine = EventMachine(self._step)
        return machine.run(
            self.initial_state(), events, seed=seed, until=until, max_events=max_events
        )

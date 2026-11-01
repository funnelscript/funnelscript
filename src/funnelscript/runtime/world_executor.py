"""Interpret type-checked World rules via the existing discrete-event machine.

Research: funnelscript-research/spec/rule-transitions-v0.md (H-R1 to H-R4).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import random
import re

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
            if type(left) is not type(right) or type(left) not in (int, float):
                raise WorldExecutionError("Arithmetic operands must have matching numeric types")
            if type(left) is float and (not math.isfinite(left) or not math.isfinite(right)):
                raise WorldExecutionError("Non-finite arithmetic operand")
            if expr.operator == "/" and right == 0:
                raise WorldExecutionError("Division by zero")
            try:
                if expr.operator == "+":
                    result = left + right
                elif expr.operator == "-":
                    result = left - right
                elif expr.operator == "*":
                    result = left * right
                else:
                    result = left / right
            except OverflowError as exc:
                raise WorldExecutionError("Non-finite arithmetic result") from exc
            if type(result) is float and not math.isfinite(result):
                raise WorldExecutionError("Non-finite arithmetic result")
            return result
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


RNG_DERIVATION_VERSION = "population-rng-v1/sha256-mt19937"
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*", re.ASCII)


def _valid_identity(value: object, name: str) -> str:
    if type(value) is not str or _ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a nonempty canonical ASCII identity")
    return value


@dataclass(frozen=True)
class PopulationAgent:
    """One explicitly enrolled instance of a source-defined World agent template."""

    agent_id: str
    cohort_id: str
    segment_id: str

    def __post_init__(self) -> None:
        for field in ("agent_id", "cohort_id", "segment_id"):
            _valid_identity(getattr(self, field), field)


@dataclass(frozen=True)
class PopulationResult:
    """Complete identity-indexed, terminal-inclusive snapshot for one trial."""

    trial_id: str
    stream_role: str
    rng_version: str
    results: dict[str, RunResult[WorldState]]
    partitions: dict[str, frozenset[str]]
    segments: dict[str, frozenset[str]]
    cohorts: dict[str, frozenset[str]]


class PopulationExecutor:
    """Opt-in isolated World runs with stable enrolled identity, not a scheduler."""

    def __init__(
        self, world: WorldExecutor, agents: Sequence[PopulationAgent], *,
        seed: int, trial_id: str, state_field: str, states: Sequence[str],
    ) -> None:
        if not isinstance(world, WorldExecutor):
            raise TypeError("world must be a WorldExecutor")
        if len(world.world.declarations) != 1 or world.world.declarations[0].kind != "agent":
            raise ValueError("Population execution requires one World agent template")
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        self.trial_id = _valid_identity(trial_id, "trial_id")
        self.seed = seed
        self.owner = world.world.declarations[0].name
        self.world = world
        if not isinstance(agents, Sequence) or not agents:
            raise ValueError("population must be a nonempty finite sequence")
        self.agents = tuple(agents)
        if any(not isinstance(item, PopulationAgent) for item in self.agents):
            raise TypeError("population entries must be PopulationAgent")
        self.ids = frozenset(item.agent_id for item in self.agents)
        if len(self.ids) != len(self.agents):
            raise ValueError("duplicate agent_id")
        self.state_field = _valid_identity(state_field, "state_field")
        self.states = tuple(_valid_identity(value, "state") for value in states)
        if not self.states or len(set(self.states)) != len(self.states):
            raise ValueError("states must be nonempty and unique")
        field = next(
            (item for item in world.world.declarations[0].states
             if item.name == state_field), None
        )
        if field is None or field.type_name != "string" or field.value not in self.states:
            raise ValueError("state_field must have a declared, valid initial string state")

    def stream_seed(self, agent_id: str, *, stream_role: str = "world-transitions") -> int:
        """Return the fully specified, versioned identity-derived MT seed."""
        _valid_identity(agent_id, "agent_id")
        _valid_identity(stream_role, "stream_role")
        if agent_id not in self.ids:
            raise ValueError("unknown agent_id")
        identity = ["population-rng-v1", self.seed, self.trial_id, agent_id, stream_role]
        encoded = json.dumps(identity, ensure_ascii=True, separators=(",", ":")).encode()
        return int.from_bytes(hashlib.sha256(encoded).digest(), "big")

    def run(
        self, events_by_agent: Mapping[str, Iterable[Event]], *,
        stream_role: str = "world-transitions",
        until: float | None = None, max_events: int = 100_000,
    ) -> PopulationResult:
        """Replay each agent-local event calendar; no cross-agent causal interactions."""
        _valid_identity(stream_role, "stream_role")
        if not isinstance(events_by_agent, Mapping):
            raise TypeError("events_by_agent must map agent IDs to ordered events")
        if set(events_by_agent) - self.ids:
            raise ValueError("unknown event owner")
        if any(not isinstance(events, Sequence) for events in events_by_agent.values()):
            raise TypeError("agent events must be ordered, replayable sequences")
        seeds = {aid: self.stream_seed(aid, stream_role=stream_role) for aid in self.ids}
        if len(set(seeds.values())) != len(seeds):
            raise ValueError("keyed stream seed collision")
        results: dict[str, RunResult[WorldState]] = {}
        partitions: dict[str, set[str]] = {state: set() for state in self.states}
        segments: dict[str, set[str]] = {}
        cohorts: dict[str, set[str]] = {}
        for agent in self.agents:
            aid = agent.agent_id
            output = self.world.run(
                events_by_agent.get(aid, ()), seed=seeds[aid],
                until=until, max_events=max_events,
            )
            state = output.state[self.owner][self.state_field]
            if state not in partitions:
                raise ValueError(f"agent {aid} has an invalid checkpoint state")
            partitions[state].add(aid)
            segments.setdefault(agent.segment_id, set()).add(aid)
            cohorts.setdefault(agent.cohort_id, set()).add(aid)
            results[aid] = output
        if set(results) != self.ids or set().union(*partitions.values()) != self.ids:
            raise RuntimeError("population identity partition violation")
        return PopulationResult(
            trial_id=self.trial_id, stream_role=stream_role,
            rng_version=RNG_DERIVATION_VERSION, results=results,
            partitions={k: frozenset(v) for k, v in partitions.items()},
            segments={k: frozenset(v) for k, v in segments.items()},
            cohorts={k: frozenset(v) for k, v in cohorts.items()},
        )

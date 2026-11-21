"""Interpret type-checked World rules via the existing discrete-event machine.

Research: funnelscript-research/spec/rule-transitions-v0.md (H-R1 to H-R4).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field

from funnelscript.compiler.world_ast import (
    BinaryExpression,
    EventEmissionDefinition,
    EventRuleDefinition,
    GuardDefinition,
    LiteralExpression,
    PayloadFieldExpression,
    ReferenceExpression,
    SampleExpression,
    StateExpression,
    WorldAST,
    WorldTypeChecker,
)
from funnelscript.core.event_machine import (
    Event,
    EventMachine,
    EventSession,
    EventSnapshot,
    FunnelRuntimeLimitError,
    RunResult,
    Transition,
)

WorldState = dict[str, dict[str, object]]


class WorldExecutionError(ValueError):
    """A supplied event cannot be dispatched to a declared World rule."""


@dataclass(frozen=True)
class WorldEventStep:
    """Observed World transition; index is processed order, not heap ordinal."""

    occurrence_index: int
    event: Event
    owner: str
    guard_matched: bool
    before: dict[str, object]
    after: dict[str, object]


class WorldExecutor:
    """Execute a domain-neutral World without external effects or model templates."""

    def __init__(self, world: WorldAST) -> None:
        WorldTypeChecker.check(world)
        # Retain a private snapshot of checked definitions: callers may mutate ASTs.
        self.world = world.model_copy(deep=True)
        self._model_identity = hashlib.sha256(
            self.world.model_dump_json().encode("utf-8")
        ).hexdigest()
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
            left = WorldExecutor._evaluate(expr.left, snapshot, payload, rng)
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

    def start(
        self,
        events: Iterable[Event],
        *,
        seed: int = 0,
        max_events: int = 100_000,
        max_queue_size: int | None = None,
        max_events_per_tick: int | None = None,
        max_zero_delay_depth: int | None = None,
    ) -> EventSession[WorldState]:
        """Create a resumable World calendar with the checked rule reducer."""
        return EventMachine(self._step).start(
            self.initial_state(), events, seed=seed, max_events=max_events,
            max_queue_size=max_queue_size, max_events_per_tick=max_events_per_tick,
            max_zero_delay_depth=max_zero_delay_depth,
            model_identity=self._model_identity,
        )

    def restore(self, snapshot: EventSnapshot[WorldState]) -> EventSession[WorldState]:
        """Resume only checkpoints from a definition with identical semantics."""
        if not isinstance(snapshot, EventSnapshot):
            raise TypeError("World restore requires an EventSnapshot")
        if snapshot.model_identity != self._model_identity:
            raise ValueError("World checkpoint does not match the current World definition")
        return EventMachine(self._step).restore(snapshot)

    def run(
        self,
        events: Iterable[Event],
        *,
        seed: int = 0,
        until: float | None = None,
        max_events: int = 100_000,
        max_queue_size: int | None = None,
        max_events_per_tick: int | None = None,
        max_zero_delay_depth: int | None = None,
        trace: list[WorldEventStep] | None = None,
    ) -> RunResult[WorldState]:
        """Lower source rules without changing the default event calendar."""
        if trace is not None and (type(trace) is not list or trace):
            raise ValueError("trace sink must be a fresh empty list")

        def observed_step(state: WorldState, event: Event, rng: random.Random) -> Transition[WorldState]:
            handler = self.handlers.get(event.name)
            transition = self._step(state, event, rng)
            if trace is not None and handler is not None:
                owner, rule = handler
                trace.append(WorldEventStep(
                    len(trace), deepcopy(event), owner,
                    self._guard_matches(rule.guard, state[owner]),
                    deepcopy(state[owner]), deepcopy(transition.state[owner]),
                ))
            return transition

        machine = EventMachine(observed_step if trace is not None else self._step)
        return machine.run(
            self.initial_state(), events, seed=seed, until=until, max_events=max_events,
            max_queue_size=max_queue_size, max_events_per_tick=max_events_per_tick,
            max_zero_delay_depth=max_zero_delay_depth,
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
        for identity_field in ("agent_id", "cohort_id", "segment_id"):
            _valid_identity(getattr(self, identity_field), identity_field)


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
    steps: dict[str, tuple[WorldEventStep, ...]] = field(default_factory=dict)


POPULATION_CHECKPOINT_SCHEMA = "population-checkpoint-v1"


@dataclass(frozen=True, slots=True)
class PopulationSnapshot:
    """Trusted, versioned checkpoint for all enrolled World event calendars.

    A snapshot contains no credentials or authenticated ledger transaction buffers.
    It must never be deserialized from an untrusted source with pickle.
    """

    schema_version: str
    rng_version: str
    world_identity: str
    trial_id: str
    seed: int
    state_field: str
    states: tuple[str, ...]
    enrollment: tuple[PopulationAgent, ...]
    stream_role: str
    stream_seeds: tuple[tuple[str, int], ...]
    sessions: tuple[tuple[str, EventSnapshot[WorldState]], ...]


def _build_population_result(
    executor: PopulationExecutor,
    output: dict[str, RunResult[WorldState]],
    stream_role: str,
    steps: dict[str, tuple[WorldEventStep, ...]] | None = None,
) -> PopulationResult:
    """Share one exhaustive identity partition check with uninterrupted runs."""
    partitions: dict[str, set[str]] = {name: set() for name in executor.states}
    segments: dict[str, set[str]] = {}
    cohorts: dict[str, set[str]] = {}
    for agent in executor.agents:
        aid = agent.agent_id
        phase = output[aid].state[executor.owner][executor.state_field]
        if phase not in partitions:
            raise ValueError(f"agent {aid} has an invalid checkpoint state")
        partitions[phase].add(aid)
        segments.setdefault(agent.segment_id, set()).add(aid)
        cohorts.setdefault(agent.cohort_id, set()).add(aid)
    if set(output) != executor.ids or set().union(*partitions.values()) != executor.ids:
        raise RuntimeError("population identity partition violation")
    return PopulationResult(
        trial_id=executor.trial_id,
        stream_role=stream_role,
        rng_version=RNG_DERIVATION_VERSION,
        results=output,
        partitions={key: frozenset(group) for key, group in partitions.items()},
        segments={key: frozenset(group) for key, group in segments.items()},
        cohorts={key: frozenset(group) for key, group in cohorts.items()},
        steps=steps or {},
    )


class PopulationSession:
    """Pause and resume independently scheduled agents as a single population."""

    def __init__(
        self,
        executor: PopulationExecutor,
        stream_role: str,
        sessions: dict[str, EventSession[WorldState]],
    ) -> None:
        self.executor = executor
        self.stream_role = stream_role
        self._sessions = sessions
        self._failed = False

    def advance(
        self, *, until: float | None = None, max_steps: int | None = None,
    ) -> PopulationResult:
        """Advance each agent at most max_steps events through inclusive until."""
        if self._failed:
            raise RuntimeError("Cannot advance a failed population session")
        if until is not None and (
            isinstance(until, bool)
            or not isinstance(until, (int, float))
            or not math.isfinite(until)
            or until < 0
        ):
            raise ValueError("until must be finite and non-negative")
        if max_steps is not None and (type(max_steps) is not int or max_steps < 1):
            raise ValueError("max_steps must be a positive integer or None")
        results: dict[str, RunResult[WorldState]] = {}
        try:
            for agent in self.executor.agents:
                aid = agent.agent_id
                try:
                    results[aid] = self._sessions[aid].advance(
                        until=until, max_steps=max_steps,
                    )
                except Exception as error:
                    error.add_note(f"population agent_id={aid}")
                    raise
            return _build_population_result(self.executor, results, self.stream_role)
        except Exception:
            # An agent may have mutated state before failure. Reject later checkpoints.
            self._failed = True
            raise

    def snapshot(self) -> PopulationSnapshot:
        """Deep-copy all calendars and metadata into one replayable checkpoint."""
        if self._failed:
            raise RuntimeError("Cannot snapshot a failed population session")
        return PopulationSnapshot(
            schema_version=POPULATION_CHECKPOINT_SCHEMA,
            rng_version=RNG_DERIVATION_VERSION,
            world_identity=self.executor.world._model_identity,
            trial_id=self.executor.trial_id,
            seed=self.executor.seed,
            state_field=self.executor.state_field,
            states=self.executor.states,
            enrollment=self.executor.agents,
            stream_role=self.stream_role,
            stream_seeds=tuple(
                (agent.agent_id, self.executor.stream_seed(
                    agent.agent_id, stream_role=self.stream_role,
                ))
                for agent in self.executor.agents
            ),
            sessions=tuple(
                (agent.agent_id, self._sessions[agent.agent_id].snapshot())
                for agent in self.executor.agents
            ),
        )


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

    def _checked_seeds(self, stream_role: str) -> dict[str, int]:
        _valid_identity(stream_role, "stream_role")
        seeds = {
            agent.agent_id: self.stream_seed(agent.agent_id, stream_role=stream_role)
            for agent in self.agents
        }
        if len(set(seeds.values())) != len(seeds):
            raise ValueError("keyed stream seed collision")
        return seeds

    def _checked_events(
        self, events_by_agent: Mapping[str, Iterable[Event]],
    ) -> None:
        if not isinstance(events_by_agent, Mapping):
            raise TypeError("events_by_agent must map agent IDs to ordered events")
        if set(events_by_agent) - self.ids:
            raise ValueError("unknown event owner")
        if any(not isinstance(events, Sequence) for events in events_by_agent.values()):
            raise TypeError("agent events must be ordered, replayable sequences")

    def start(
        self, events_by_agent: Mapping[str, Iterable[Event]], *,
        stream_role: str = "world-transitions",
        max_events: int = 100_000,
        max_queue_size: int | None = None,
        max_events_per_tick: int | None = None,
        max_zero_delay_depth: int | None = None,
    ) -> PopulationSession:
        """Create all identity-derived World calendars without dispatching events."""
        self._checked_events(events_by_agent)
        seeds = self._checked_seeds(stream_role)
        sessions: dict[str, EventSession[WorldState]] = {}
        for agent in self.agents:
            aid = agent.agent_id
            try:
                sessions[aid] = self.world.start(
                    events_by_agent.get(aid, ()),
                    seed=seeds[aid], max_events=max_events,
                    max_queue_size=max_queue_size,
                    max_events_per_tick=max_events_per_tick,
                    max_zero_delay_depth=max_zero_delay_depth,
                )
            except FunnelRuntimeLimitError as error:
                error.add_note(f"population agent_id={aid}")
                raise
        return PopulationSession(self, stream_role, sessions)

    def restore(self, checkpoint: PopulationSnapshot) -> PopulationSession:
        """Restore a complete trusted population checkpoint after identity checks."""
        if not isinstance(checkpoint, PopulationSnapshot):
            raise TypeError("restore requires a PopulationSnapshot")
        if checkpoint.schema_version != POPULATION_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported population checkpoint schema_version")
        if checkpoint.rng_version != RNG_DERIVATION_VERSION:
            raise ValueError("population checkpoint rng_version mismatch")
        if checkpoint.world_identity != self.world._model_identity:
            raise ValueError("population checkpoint World definition mismatch")
        if checkpoint.trial_id != self.trial_id:
            raise ValueError("population checkpoint trial mismatch")
        if checkpoint.seed != self.seed:
            raise ValueError("population checkpoint seed mismatch")
        if checkpoint.state_field != self.state_field:
            raise ValueError("population checkpoint state_field mismatch")
        if checkpoint.states != self.states:
            raise ValueError("population checkpoint states mismatch")
        expected = {agent.agent_id: agent for agent in self.agents}
        actual = {agent.agent_id: agent for agent in checkpoint.enrollment}
        if actual != expected or len(checkpoint.enrollment) != len(self.agents):
            raise ValueError("population checkpoint enrollment mismatch")
        expected_seeds = self._checked_seeds(checkpoint.stream_role)
        provided_seeds = dict(checkpoint.stream_seeds)
        if (
            len(checkpoint.stream_seeds) != len(self.agents)
            or provided_seeds != expected_seeds
        ):
            raise ValueError("population checkpoint stream seed manifest mismatch")
        ids = [item[0] for item in checkpoint.sessions]
        if len(ids) != len(self.agents) or set(ids) != self.ids:
            raise ValueError("population checkpoint session enrollment mismatch")
        sessions = {
            aid: self.world.restore(world_snapshot)
            for aid, world_snapshot in checkpoint.sessions
        }
        return PopulationSession(self, checkpoint.stream_role, sessions)

    def run(
        self, events_by_agent: Mapping[str, Iterable[Event]], *,
        stream_role: str = "world-transitions",
        until: float | None = None, max_events: int = 100_000,
        trace: bool = False,
        max_queue_size: int | None = None,
        max_events_per_tick: int | None = None,
        max_zero_delay_depth: int | None = None,
    ) -> PopulationResult:
        """Replay each agent-local event calendar; no cross-agent causal interactions."""
        self._checked_events(events_by_agent)
        seeds = self._checked_seeds(stream_role)
        results: dict[str, RunResult[WorldState]] = {}
        steps: dict[str, tuple[WorldEventStep, ...]] = {}
        for agent in self.agents:
            aid = agent.agent_id
            observed: list[WorldEventStep] = []
            try:
                output = self.world.run(
                    events_by_agent.get(aid, ()), seed=seeds[aid],
                    until=until, max_events=max_events,
                    max_queue_size=max_queue_size, max_events_per_tick=max_events_per_tick,
                    max_zero_delay_depth=max_zero_delay_depth,
                    trace=observed if trace else None,
                )
            except FunnelRuntimeLimitError as exc:
                exc.add_note(f"population agent_id={aid}")
                raise
            if trace:
                steps[aid] = tuple(observed)
            results[aid] = output
        return _build_population_result(self, results, stream_role, steps)

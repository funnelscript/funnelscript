"""Domain-neutral discrete-event state-machine kernel.

Research: funnelscript-research/spec/event-kernel-v0.md (H-K1 through H-K4).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count


@dataclass(frozen=True)
class Event:
    """A timed event; the payload is owned by the user-defined model."""

    time: float
    name: str
    payload: object = None
    priority: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.time, bool)
            or not isinstance(self.time, (int, float))
            or not math.isfinite(self.time)
            or self.time < 0
        ):
            raise ValueError("Event time must be finite and non-negative")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("Event priority must be an integer")


@dataclass(frozen=True)
class EffectIntent:
    """Inert description of an intended effect; no handler is invoked."""

    kind: str
    payload: object = None


@dataclass(frozen=True)
class Transition[S]:
    """Next state and events/effects proposed by a model-owned reducer."""

    state: S
    events: tuple[Event, ...] = ()
    effects: tuple[EffectIntent, ...] = ()


@dataclass(frozen=True)
class RunResult[S]:
    state: S
    processed: tuple[Event, ...]
    intents: tuple[EffectIntent, ...]
    pending: tuple[Event, ...]


class FunnelRuntimeLimitError(RuntimeError):
    """An explicit event resource budget was exceeded; no result was returned."""

    def __init__(
        self, limit_kind: str, configured_cap: int, attempted_count: int,
        timestamp: float, causal_chain: tuple[str, ...],
        trace_complete: bool = True,
    ) -> None:
        self.limit_kind = limit_kind
        self.configured_cap = configured_cap
        self.attempted_count = attempted_count
        self.timestamp = timestamp
        self.causal_chain = causal_chain
        self.trace_complete = trace_complete
        prefix = "max_events reached" if limit_kind == "max_events" else f"{limit_kind} reached"
        super().__init__(
            f"{prefix}: cap={configured_cap}, attempted={attempted_count}, "
            f"t={timestamp}; causal chain: " + " -> ".join(causal_chain)
            + ("" if trace_complete else " (full ancestry unavailable without an explicit guard)")
        )


@dataclass(frozen=True, slots=True)
class _CausalLink:
    name: str
    parent: _CausalLink | None
    zero_delay_depth: int


type _QueueEntry = (
    tuple[float, int, int, int, Event]
    | tuple[float, int, int, int, Event, _CausalLink]
)


def _chain(event: Event, link: _CausalLink | None) -> tuple[str, ...]:
    if link is None:
        return (event.name,)
    names = []
    while link is not None:
        names.append(link.name)
        link = link.parent
    return tuple(reversed(names))


def _validate_budget(value: int | None, name: str, minimum: int) -> None:
    if value is not None and (type(value) is not int or value < minimum):
        raise ValueError(f"{name} must be an integer >= {minimum} or None")


def _admit(
    queue: list[_QueueEntry], entry: _QueueEntry, max_queue_size: int | None,
) -> None:
    if max_queue_size is not None and len(queue) >= max_queue_size:
        raise FunnelRuntimeLimitError(
            "max_queue_size", max_queue_size, len(queue) + 1,
            entry[0], _chain(entry[4], entry[5] if len(entry) == 6 else None),
        )
    heappush(queue, entry)


def _schedule_emitted(
    queue: list[_QueueEntry], events: tuple[Event, ...],
    active: Event, causal_depth: int, zero_delay_depth: int,
    ancestor: _CausalLink | None, ordinal: Iterator[int],
    max_queue_size: int | None, max_zero_delay_depth: int | None,
    trace_enabled: bool,
) -> None:
    parent = (
        ancestor if ancestor is not None else _CausalLink(active.name, None, 0)
    ) if trace_enabled else None
    for future in events:
        if not isinstance(future, Event):
            raise TypeError("Scheduled entries must be Event instances")
        if future.time < active.time:
            raise ValueError("Cannot schedule an event in the past")
        if future.time == active.time and future.priority < active.priority:
            raise ValueError("Cannot schedule retrograde priority at the current time")
        if trace_enabled:
            next_zero_depth = zero_delay_depth + 1 if future.time == active.time else 0
            child = _CausalLink(future.name, parent, next_zero_depth)
            if max_zero_delay_depth is not None and next_zero_depth > max_zero_delay_depth:
                raise FunnelRuntimeLimitError(
                    "max_zero_delay_depth", max_zero_delay_depth, next_zero_depth,
                    future.time, _chain(future, child),
                )
            entry = (future.time, future.priority, causal_depth + 1, next(ordinal), future, child)
        else:
            entry = (future.time, future.priority, causal_depth + 1, next(ordinal), future)
        if max_queue_size is None:
            heappush(queue, entry)
        else:
            _admit(queue, entry, max_queue_size)


def _validate_run_arguments(
    until: float | None, max_events: int, max_queue_size: int | None,
    max_events_per_tick: int | None, max_zero_delay_depth: int | None,
) -> None:
    if until is not None and (
        isinstance(until, bool)
        or not isinstance(until, (int, float))
        or not math.isfinite(until)
        or until < 0
    ):
        raise ValueError("until must be finite and non-negative")
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("max_events must be a positive integer")
    _validate_budget(max_queue_size, "max_queue_size", 1)
    _validate_budget(max_events_per_tick, "max_events_per_tick", 1)
    _validate_budget(max_zero_delay_depth, "max_zero_delay_depth", 0)


@dataclass(frozen=True, slots=True)
class EventSnapshot[S]:
    """Trusted checkpoint of the event calendar and its reducer-owned state.

    Snapshots can be pickled for trusted local storage; never unpickle untrusted
    external data. The reducer itself is deliberately supplied at restore time.
    """

    state: S
    queue: tuple[_QueueEntry, ...]
    rng_state: tuple[object, ...]
    next_ordinal: int
    processed: tuple[Event, ...]
    intents: tuple[EffectIntent, ...]
    tick_time: float | None
    tick_events: int
    max_events: int
    max_queue_size: int | None
    max_events_per_tick: int | None
    max_zero_delay_depth: int | None
    model_identity: str | None


class EventSession[S]:
    """Resumable single-reducer calendar with a deterministic total order."""

    def __init__(
        self,
        reducer: Callable[[S, Event, random.Random], Transition[S]],
        initial_state: S,
        events: Iterable[Event],
        *,
        seed: int,
        max_events: int,
        max_queue_size: int | None,
        max_events_per_tick: int | None,
        max_zero_delay_depth: int | None,
        model_identity: str | None = None,
    ) -> None:
        _validate_run_arguments(
            None, max_events, max_queue_size, max_events_per_tick, max_zero_delay_depth,
        )
        self.reducer = reducer
        self.model_identity = model_identity
        self._failed = False
        self.max_events = max_events
        self.max_queue_size = max_queue_size
        self.max_events_per_tick = max_events_per_tick
        self.max_zero_delay_depth = max_zero_delay_depth
        self.trace_enabled = any(
            item is not None for item in
            (max_queue_size, max_events_per_tick, max_zero_delay_depth)
        )
        self.ordinal = count()
        self.queue: list[_QueueEntry] = []
        for event in events:
            if not isinstance(event, Event):
                raise TypeError("Calendar entries must be Event instances")
            entry = (event.time, event.priority, 0, next(self.ordinal), event)
            if max_queue_size is None:
                heappush(self.queue, entry)
            else:
                _admit(self.queue, entry, max_queue_size)
        self.rng = random.Random(seed)
        self.state = initial_state
        self.processed: list[Event] = []
        self.intents: list[EffectIntent] = []
        self.tick_time: float | None = None
        self.tick_events = 0

    @classmethod
    def from_snapshot(
        cls,
        reducer: Callable[[S, Event, random.Random], Transition[S]],
        snapshot: EventSnapshot[S],
    ) -> EventSession[S]:
        if not isinstance(snapshot, EventSnapshot):
            raise TypeError("restore requires an EventSnapshot")
        _validate_run_arguments(
            None, snapshot.max_events, snapshot.max_queue_size,
            snapshot.max_events_per_tick, snapshot.max_zero_delay_depth,
        )
        # A fresh session's initialization cannot observe a mutated checkpoint.
        result = cls(
            reducer, deepcopy(snapshot.state), (), seed=0,
            max_events=snapshot.max_events,
            max_queue_size=snapshot.max_queue_size,
            max_events_per_tick=snapshot.max_events_per_tick,
            max_zero_delay_depth=snapshot.max_zero_delay_depth,
            model_identity=snapshot.model_identity,
        )
        result.queue = list(deepcopy(snapshot.queue))
        result.ordinal = count(snapshot.next_ordinal)
        result.rng.setstate(snapshot.rng_state)
        result.processed = list(deepcopy(snapshot.processed))
        result.intents = list(deepcopy(snapshot.intents))
        result.tick_time = snapshot.tick_time
        result.tick_events = snapshot.tick_events
        return result

    def snapshot(self) -> EventSnapshot[S]:
        """Capture an independent copy, including the full PRNG Gaussian cache."""
        if self._failed:
            raise RuntimeError("Cannot snapshot a failed session")
        return EventSnapshot(
            state=deepcopy(self.state),
            queue=tuple(deepcopy(self.queue)),
            rng_state=self.rng.getstate(),
            next_ordinal=len(self.processed) + len(self.queue),
            processed=tuple(deepcopy(self.processed)),
            intents=tuple(deepcopy(self.intents)),
            tick_time=self.tick_time,
            tick_events=self.tick_events,
            max_events=self.max_events,
            max_queue_size=self.max_queue_size,
            max_events_per_tick=self.max_events_per_tick,
            max_zero_delay_depth=self.max_zero_delay_depth,
            model_identity=self.model_identity,
        )

    def advance(
        self, *, until: float | None = None, max_steps: int | None = None,
    ) -> RunResult[S]:
        """Process through an inclusive time horizon or an exact event budget."""
        if self._failed:
            raise RuntimeError("Cannot advance a failed session")
        _validate_run_arguments(
            until, self.max_events, self.max_queue_size,
            self.max_events_per_tick, self.max_zero_delay_depth,
        )
        if max_steps is not None and (type(max_steps) is not int or max_steps < 1):
            raise ValueError("max_steps must be a positive integer or None")
        dispatched = 0
        while (
            self.queue
            and (until is None or self.queue[0][0] <= until)
            and (max_steps is None or dispatched < max_steps)
        ):
            try:
                self._dispatch_one()
            except Exception:
                # The reducer may have mutated state or consumed random draws.
                # Never expose an invalid checkpoint or silently retry this event.
                self._failed = True
                raise
            dispatched += 1
        pending = tuple(item[4] for item in sorted(self.queue))
        return RunResult(
            self.state, tuple(self.processed), tuple(self.intents), pending,
        )

    def _check_next_budget(self, head: _QueueEntry) -> None:
        timestamp, event = head[0], head[4]
        ancestor = head[5] if len(head) == 6 else None
        if len(self.processed) >= self.max_events:
            raise FunnelRuntimeLimitError(
                "max_events", self.max_events, len(self.processed) + 1,
                timestamp, _chain(event, ancestor),
                trace_complete=self.trace_enabled,
            )
        if self.max_events_per_tick is None:
            return
        if timestamp != self.tick_time:
            self.tick_time = timestamp
            self.tick_events = 0
        if self.tick_events >= self.max_events_per_tick:
            raise FunnelRuntimeLimitError(
                "max_events_per_tick", self.max_events_per_tick,
                self.tick_events + 1, timestamp, _chain(event, ancestor),
            )

    def _dispatch_one(self) -> None:
        self._check_next_budget(self.queue[0])
        current = heappop(self.queue)
        event = current[4]
        ancestor = current[5] if len(current) == 6 else None
        depth = ancestor.zero_delay_depth if ancestor is not None else 0
        transition = self.reducer(self.state, event, self.rng)
        if not isinstance(transition, Transition):
            raise TypeError("Model reducer must return a Transition")
        if transition.events:
            _schedule_emitted(
                self.queue, transition.events, event, current[2], depth,
                ancestor, self.ordinal, self.max_queue_size,
                self.max_zero_delay_depth, self.trace_enabled,
            )
        for intent in transition.effects:
            if not isinstance(intent, EffectIntent):
                raise TypeError("Model effects must be EffectIntent instances")
            self.intents.append(intent)
        self.state = transition.state
        self.processed.append(event)
        if self.max_events_per_tick is not None:
            self.tick_events += 1


class EventMachine[S]:
    """Run or resume a model-owned reducer over an ordered event calendar."""

    def __init__(
        self, reducer: Callable[[S, Event, random.Random], Transition[S]],
    ) -> None:
        self.reducer = reducer

    def start(
        self,
        initial_state: S,
        events: Iterable[Event],
        *,
        seed: int,
        max_events: int = 100_000,
        max_queue_size: int | None = None,
        max_events_per_tick: int | None = None,
        max_zero_delay_depth: int | None = None,
        model_identity: str | None = None,
    ) -> EventSession[S]:
        return EventSession(
            self.reducer, initial_state, events, seed=seed,
            max_events=max_events, max_queue_size=max_queue_size,
            max_events_per_tick=max_events_per_tick,
            max_zero_delay_depth=max_zero_delay_depth,
            model_identity=model_identity,
        )

    def restore(self, snapshot: EventSnapshot[S]) -> EventSession[S]:
        return EventSession.from_snapshot(self.reducer, snapshot)

    def run(
        self,
        initial_state: S,
        events: Iterable[Event],
        *,
        seed: int,
        until: float | None = None,
        max_events: int = 100_000,
        max_queue_size: int | None = None,
        max_events_per_tick: int | None = None,
        max_zero_delay_depth: int | None = None,
    ) -> RunResult[S]:
        _validate_run_arguments(
            until, max_events, max_queue_size, max_events_per_tick, max_zero_delay_depth,
        )
        return self.start(
            initial_state, events, seed=seed, max_events=max_events,
            max_queue_size=max_queue_size, max_events_per_tick=max_events_per_tick,
            max_zero_delay_depth=max_zero_delay_depth,
        ).advance(until=until)

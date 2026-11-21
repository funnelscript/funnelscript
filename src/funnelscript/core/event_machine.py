"""Domain-neutral discrete-event state-machine kernel.

Research: funnelscript-research/spec/event-kernel-v0.md (H-K1 through H-K4).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterable, Iterator
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


class EventMachine[S]:
    """Run a model reducer over an ordered event calendar and seeded PRNG."""

    def __init__(
        self, reducer: Callable[[S, Event, random.Random], Transition[S]]
    ) -> None:
        self.reducer = reducer

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
        trace_enabled = any(
            bound is not None
            for bound in (max_queue_size, max_events_per_tick, max_zero_delay_depth)
        )
        ordinal = count()
        queue: list[_QueueEntry] = []
        for event in events:
            if not isinstance(event, Event):
                raise TypeError("Calendar entries must be Event instances")
            entry = (event.time, event.priority, 0, next(ordinal), event)
            if max_queue_size is None:
                heappush(queue, entry)
            else:
                _admit(queue, entry, max_queue_size)

        rng = random.Random(seed)
        state = initial_state
        processed: list[Event] = []
        intents: list[EffectIntent] = []
        tick_time: float | None = None
        tick_events = 0

        while queue and (until is None or queue[0][0] <= until):
            head = queue[0]
            timestamp, next_event = head[0], head[4]
            next_link = head[5] if len(head) == 6 else None
            if len(processed) >= max_events:
                raise FunnelRuntimeLimitError(
                    "max_events", max_events, len(processed) + 1,
                    timestamp, _chain(next_event, next_link),
                    trace_complete=trace_enabled,
                )
            if max_events_per_tick is not None:
                if timestamp != tick_time:
                    tick_time = timestamp
                    tick_events = 0
                if tick_events >= max_events_per_tick:
                    raise FunnelRuntimeLimitError(
                        "max_events_per_tick", max_events_per_tick, tick_events + 1,
                        timestamp, _chain(next_event, next_link),
                    )
            current = heappop(queue)
            causal_depth, event = current[2], current[4]
            ancestor = current[5] if len(current) == 6 else None
            zero_delay_depth = ancestor.zero_delay_depth if ancestor is not None else 0
            transition = self.reducer(state, event, rng)
            if not isinstance(transition, Transition):
                raise TypeError("Model reducer must return a Transition")
            if transition.events:
                _schedule_emitted(
                    queue, transition.events, event, causal_depth, zero_delay_depth,
                    ancestor, ordinal, max_queue_size, max_zero_delay_depth,
                    trace_enabled,
                )
            for intent in transition.effects:
                if not isinstance(intent, EffectIntent):
                    raise TypeError("Model effects must be EffectIntent instances")
                intents.append(intent)
            state = transition.state
            processed.append(event)
            if max_events_per_tick is not None:
                tick_events += 1

        pending = tuple(item[4] for item in sorted(queue))
        return RunResult(state, tuple(processed), tuple(intents), pending)

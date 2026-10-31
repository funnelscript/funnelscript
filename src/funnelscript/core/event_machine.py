"""Domain-neutral discrete-event state-machine kernel.

Research: funnelscript-research/spec/event-kernel-v0.md (H-K1 through H-K4).
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from typing import Callable, Generic, Iterable, TypeVar
import math
import random

S = TypeVar("S")


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
class Transition(Generic[S]):
    """Next state and events/effects proposed by a model-owned reducer."""

    state: S
    events: tuple[Event, ...] = ()
    effects: tuple[EffectIntent, ...] = ()


@dataclass(frozen=True)
class RunResult(Generic[S]):
    state: S
    processed: tuple[Event, ...]
    intents: tuple[EffectIntent, ...]
    pending: tuple[Event, ...]


class EventMachine(Generic[S]):
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
    ) -> RunResult[S]:
        if until is not None and (
            isinstance(until, bool)
            or not isinstance(until, (int, float))
            or not math.isfinite(until)
            or until < 0
        ):
            raise ValueError("until must be finite and non-negative")
        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
            raise ValueError("max_events must be a positive integer")

        ordinal = count()
        queue: list[tuple[float, int, int, Event]] = []
        for event in events:
            if not isinstance(event, Event):
                raise TypeError("Calendar entries must be Event instances")
            heappush(queue, (event.time, event.priority, next(ordinal), event))

        rng = random.Random(seed)
        state = initial_state
        processed: list[Event] = []
        intents: list[EffectIntent] = []

        while queue and (until is None or queue[0][0] <= until):
            if len(processed) >= max_events:
                raise RuntimeError("max_events reached before the calendar was exhausted")
            _, _, _, event = heappop(queue)
            transition = self.reducer(state, event, rng)
            if not isinstance(transition, Transition):
                raise TypeError("Model reducer must return a Transition")
            for future in transition.events:
                if not isinstance(future, Event):
                    raise TypeError("Scheduled entries must be Event instances")
                if future.time < event.time:
                    raise ValueError("Cannot schedule an event in the past")
                if future.time == event.time and future.priority < event.priority:
                    raise ValueError("Cannot schedule retrograde priority at the current time")
                heappush(queue, (future.time, future.priority, next(ordinal), future))
            for intent in transition.effects:
                if not isinstance(intent, EffectIntent):
                    raise TypeError("Model effects must be EffectIntent instances")
                intents.append(intent)
            state = transition.state
            processed.append(event)

        pending = tuple(item[3] for item in sorted(queue))
        return RunResult(state, tuple(processed), tuple(intents), pending)

"""Property-based falsification tests for the domain-neutral event kernel.

Contract: funnelscript-research/spec/event-kernel-v0.md (H-K1 to H-K3).
"""

import random

import pytest
from hypothesis import given, settings, strategies as st

from funnelscript.core.event_machine import Event, EventMachine, Transition


@settings(max_examples=150, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 200), st.integers(-8, 8)),
        max_size=60,
    ),
    st.integers(),
)
def test_calendar_orders_by_time_priority_and_insertion(pairs, seed):
    events = tuple(
        Event(when, f"event_{index}", priority=priority)
        for index, (when, priority) in enumerate(pairs)
    )
    machine = EventMachine(
        lambda state, event, rng: Transition(state=state + (event.name,))
    )
    result = machine.run((), events, seed=seed)
    expected = tuple(
        events[index]
        for index in sorted(
            range(len(events)),
            key=lambda index: (events[index].time, events[index].priority, index),
        )
    )
    assert result.processed == expected
    assert result.state == tuple(event.name for event in expected)


@settings(max_examples=100, deadline=None)
@given(
    st.integers(0, 150),
    st.integers(0, 60),
    st.integers(-8, 8),
    st.integers(),
)
def test_emitted_events_never_violate_calendar_order(start, delay, priority, seed):
    def reducer(state, event, rng):
        generated = (
            (Event(start + delay, "generated", priority=priority),)
            if event.name == "start"
            else ()
        )
        return Transition(state=state + (event.name,), events=generated)

    scheduled = (Event(start, "start", priority=priority),
                 Event(start, "already_queued", priority=priority))
    result = EventMachine(reducer).run((), scheduled, seed=seed)
    assert tuple(e.name for e in result.processed) == (
        ("start", "already_queued", "generated")
    )
    assert all(
        left.time <= right.time
        for left, right in zip(result.processed, result.processed[1:])
    )


@settings(max_examples=150, deadline=None)
@given(st.integers(), st.lists(st.integers(0, 25), max_size=45))
def test_seeded_replay_reproduces_complete_result(seed, delays):
    def reducer(state, event, rng: random.Random):
        roll = rng.random()
        scheduled = (
            (Event(event.time + 1, "followup", priority=event.priority),)
            if event.name == "initial" and roll < 0.5
            else ()
        )
        return Transition(state=state + ((event.name, roll),), events=scheduled)

    events = tuple(Event(delay, "initial") for delay in delays)
    machine = EventMachine(reducer)
    one = machine.run((), events, seed=seed)
    two = machine.run((), events, seed=seed)
    assert one == two
    assert len(one.processed) <= 2 * len(events)


@settings(max_examples=100, deadline=None)
@given(st.integers(0, 100), st.integers(0, 100), st.integers())
def test_horizon_keeps_future_events_pending(first, extra, seed):
    later = first + extra + 1
    events = (Event(first, "first"), Event(later, "later"))
    result = EventMachine(
        lambda state, event, rng: Transition(state=state + (event.name,))
    ).run((), events, seed=seed, until=first)
    assert tuple(e.name for e in result.processed) == ("first",)
    assert result.pending == (events[1],)


@settings(max_examples=75, deadline=None)
@given(st.integers(1, 200), st.integers(1, 10))
def test_retrograde_emission_is_rejected(now, shift):
    def reducer(state, event, rng):
        return Transition(state=state, events=(Event(now - min(now, shift), "backward"),))

    with pytest.raises(ValueError, match="past"):
        EventMachine(reducer).run(0, (Event(now, "start"),), seed=0)


@settings(max_examples=75, deadline=None)
@given(st.integers(0, 200), st.integers(-30, -1))
def test_equal_time_priority_regression_is_rejected(now, priority):
    def reducer(state, event, rng):
        return Transition(
            state=state,
            events=(Event(now, "illegal", priority=priority - 1),),
        )

    with pytest.raises(ValueError, match="priority"):
        EventMachine(reducer).run(
            0, (Event(now, "start", priority=priority),), seed=0
        )


@settings(max_examples=50, deadline=None)
@given(st.integers(1, 100))
def test_zero_delay_cycles_respect_processing_cap(limit):
    def reducer(state, event, rng):
        return Transition(state=state + 1, events=(Event(event.time, event.name),))

    with pytest.raises(RuntimeError, match="max_events"):
        EventMachine(reducer).run(
            0, (Event(0, "recursive"),), seed=0, max_events=limit
        )

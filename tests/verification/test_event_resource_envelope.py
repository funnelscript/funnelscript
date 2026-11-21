"""Opt-in event resource bounds derived from DEVS and H-RQ1/H-RQ2/H-RT1.

Hypothesis: finite explicit budgets reject at the event admission/dispatch
boundary without changing unbounded-v0 results, event order, or RNG draws.
Invariants: |Q| <= Lq; count(t) <= Lt; zero_delay_depth <= Lz;
every failure identifies the attempted count and exact causal ancestry.
"""

import itertools
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core import (
    Event,
    EventMachine,
    FunnelRuntimeLimitError,
    Transition,
)


def test_zero_delay_cycle_reports_exact_alternating_causal_chain():
    def repeat(state, event, rng):
        next_name = "B" if event.name == "A" else "A"
        return Transition(state=state + (event.name,), events=(Event(event.time, next_name),))

    with pytest.raises(FunnelRuntimeLimitError) as caught:
        EventMachine(repeat).run(
            (), [Event(4, "A")], seed=0, max_zero_delay_depth=2
        )

    error = caught.value
    assert error.limit_kind == "max_zero_delay_depth"
    assert error.configured_cap == 2
    assert error.attempted_count == 3
    assert error.timestamp == 4
    assert error.causal_chain == ("A", "B", "A", "B")
    assert "A -> B -> A -> B" in str(error)


def test_zero_delay_depth_resets_for_positive_time_advances():
    def progress(state, event, rng):
        if event.time == 5:
            return Transition(state=state + 1)
        return Transition(state=state + 1, events=(Event(event.time + 1, "tick"),))

    result = EventMachine(progress).run(
        0, [Event(0, "tick")], seed=0,
        max_zero_delay_depth=0, max_events_per_tick=1, max_queue_size=1,
    )
    assert result.state == 6
    assert len(result.processed) == 6


def test_queue_limit_rejects_streaming_initial_events_without_exhausting_generator():
    seen = []

    def forever():
        for index in itertools.count():
            seen.append(index)
            yield Event(100, f"future-{index}")

    with pytest.raises(FunnelRuntimeLimitError) as caught:
        EventMachine(lambda state, event, rng: Transition(state)).run(
            0, forever(), seed=0, until=0, max_queue_size=2
        )

    error = caught.value
    assert seen == [0, 1, 2]
    assert error.limit_kind == "max_queue_size"
    assert error.configured_cap == 2
    assert error.attempted_count == 3
    assert error.timestamp == 100
    assert error.causal_chain == ("future-2",)


def test_queue_limit_rejects_fanout_with_source_chain_and_no_partial_result():
    def fanout(state, event, rng):
        return Transition(
            state=state + 1,
            events=tuple(Event(5, f"child-{i}") for i in range(4)),
        )

    with pytest.raises(FunnelRuntimeLimitError) as caught:
        EventMachine(fanout).run(0, [Event(0, "root")], seed=0, max_queue_size=2)

    error = caught.value
    assert error.limit_kind == "max_queue_size"
    assert error.attempted_count == 3
    assert error.timestamp == 5
    assert error.causal_chain == ("root", "child-2")


def test_per_tick_limit_counts_independent_roots_but_resets_at_next_timestamp():
    events = (Event(0, "a"), Event(0, "b"), Event(1, "c"), Event(1, "d"))
    machine = EventMachine(lambda state, event, rng: Transition(state + (event.name,)))
    result = machine.run((), events, seed=0, max_events_per_tick=2)
    assert result.state == ("a", "b", "c", "d")

    with pytest.raises(FunnelRuntimeLimitError) as caught:
        machine.run((), events, seed=0, max_events_per_tick=1)

    error = caught.value
    assert error.limit_kind == "max_events_per_tick"
    assert error.configured_cap == 1
    assert error.attempted_count == 2
    assert error.timestamp == 0
    assert error.causal_chain == ("b",)


def test_total_events_cap_preserves_existing_runtime_error_contract_with_metadata():
    events = (Event(0, "first"), Event(1, "second"))
    machine = EventMachine(lambda state, event, rng: Transition(state + 1))

    with pytest.raises(RuntimeError, match="max_events") as caught:
        machine.run(0, events, seed=0, max_events=1)
    assert isinstance(caught.value, FunnelRuntimeLimitError)
    assert caught.value.limit_kind == "max_events"
    assert caught.value.configured_cap == 1
    assert caught.value.attempted_count == 2
    assert caught.value.causal_chain == ("second",)


@pytest.mark.parametrize(
    ("kwargs", "term"),
    [
        ({"max_queue_size": 0}, "max_queue_size"),
        ({"max_queue_size": True}, "max_queue_size"),
        ({"max_events_per_tick": 0}, "max_events_per_tick"),
        ({"max_events_per_tick": -1}, "max_events_per_tick"),
        ({"max_zero_delay_depth": -1}, "max_zero_delay_depth"),
        ({"max_zero_delay_depth": 1.5}, "max_zero_delay_depth"),
        ({"max_zero_delay_depth": True}, "max_zero_delay_depth"),
    ],
)
def test_rejects_invalid_resource_limit_configuration(kwargs, term):
    machine = EventMachine(lambda state, event, rng: Transition(state))
    with pytest.raises(ValueError, match=term):
        machine.run(0, (), seed=0, **kwargs)


@settings(max_examples=80, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=25), max_size=25),
    st.integers(),
)
def test_nonbinding_limits_leave_random_draws_and_complete_result_identical(times, seed):
    def reducer(state, event, rng: random.Random):
        return Transition(state + ((event.name, rng.random()),))

    events = tuple(Event(t, f"id-{i}") for i, t in enumerate(times))
    machine = EventMachine(reducer)
    baseline = machine.run((), events, seed=seed)
    bounded = machine.run(
        (), events, seed=seed,
        max_queue_size=max(1, len(events)),
        max_events_per_tick=max(1, len(events)),
        max_zero_delay_depth=0,
    )
    assert bounded == baseline


def test_queue_limit_accepts_exact_boundary_and_all_horizon_pending_events():
    events = tuple(Event(7, f"future-{i}") for i in range(3))
    result = EventMachine(lambda state, event, rng: Transition(state)).run(
        0, events, seed=0, until=0, max_queue_size=3,
    )
    assert result.processed == ()
    assert result.pending == events


def test_zero_delay_budget_counts_only_ancestor_chain_not_siblings():
    def siblings(state, event, rng):
        if event.name == "root":
            return Transition(state + 1, events=(Event(0, "a"), Event(0, "b")))
        return Transition(state + 1)

    result = EventMachine(siblings).run(
        0, (Event(0, "root"),), seed=0,
        max_zero_delay_depth=1, max_events_per_tick=3,
    )
    assert result.state == 3
    assert tuple(e.name for e in result.processed) == ("root", "a", "b")


def test_public_exception_is_exported_from_core():
    from funnelscript import core

    assert core.FunnelRuntimeLimitError is FunnelRuntimeLimitError


def test_default_total_budget_labels_incomplete_ancestry_of_emitted_event():
    def repeat(state, event, rng):
        return Transition(state + 1, events=(Event(event.time, "next"),))

    with pytest.raises(FunnelRuntimeLimitError, match="max_events reached") as caught:
        EventMachine(repeat).run(0, (Event(0, "origin"),), seed=0, max_events=2)
    assert caught.value.causal_chain == ("next",)
    assert caught.value.trace_complete is False
    assert "full ancestry unavailable" in str(caught.value)


def test_explicit_guard_keeps_complete_ancestry_for_total_event_limit():
    def repeat(state, event, rng):
        return Transition(state + 1, events=(Event(event.time, "next"),))

    with pytest.raises(FunnelRuntimeLimitError, match="max_events reached") as caught:
        EventMachine(repeat).run(
            0, (Event(0, "origin"),), seed=0,
            max_events=2, max_zero_delay_depth=10,
        )
    assert caught.value.causal_chain == ("origin", "next", "next")
    assert caught.value.trace_complete is True

"""Falsification suite for checkpointed discrete-event replay.

Research: DEVS event calendars, MT19937 state capture, and event sourcing.
H: Every split of a pure reducer produces the same complete trace as one run.
Invariant: run(Q,S,R) == restore(snapshot(run_prefix(Q,S,R))).run_suffix,
including emitted priority ties, future intents and exact random draws.
"""

from __future__ import annotations

import math
import pickle
import random
from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core import (
    EffectIntent,
    Event,
    EventMachine,
    FunnelRuntimeLimitError,
    Transition,
)


def _stochastic_reducer(state: tuple, event: Event, rng: random.Random) -> Transition:
    draw = rng.getrandbits(63)
    emitted = (
        (Event(event.time + 1, "follow", payload={"origin": event.name}),)
        if event.name.startswith("root") and draw % 3 == 0
        else ()
    )
    effects = (
        EffectIntent("ledger.observe", {"event": event.name, "draw": draw}),
    )
    return Transition(
        state=state + ((event.name, event.time, draw),),
        events=emitted,
        effects=effects,
    )


@settings(max_examples=95, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=25),
            st.integers(min_value=-2, max_value=4),
        ),
        max_size=35,
    ),
    st.integers(),
    st.integers(min_value=0, max_value=25),
)
def test_every_time_split_matches_reference_kernel(pairs, seed, split):
    events = tuple(
        Event(t, f"root-{index}", priority=priority)
        for index, (t, priority) in enumerate(pairs)
    )
    engine = EventMachine(_stochastic_reducer)
    expected = engine.run((), events, seed=seed)
    session = engine.start((), events, seed=seed)
    prefix = session.advance(until=split)
    assert all(item.time <= split for item in prefix.processed)
    assert all(item.time > split for item in prefix.pending)
    snapshot = session.snapshot()
    restored = engine.restore(snapshot)
    actual = restored.advance()
    assert actual == expected
    assert actual.processed[: len(prefix.processed)] == prefix.processed
    assert actual.intents[: len(prefix.intents)] == prefix.intents


@settings(max_examples=75, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=30),
    st.integers(),
    st.integers(min_value=1, max_value=35),
)
def test_every_event_count_split_matches_reference_kernel(times, seed, budget):
    events = tuple(Event(t, f"root-{i}") for i, t in enumerate(times))
    engine = EventMachine(_stochastic_reducer)
    expected = engine.run((), events, seed=seed)
    session = engine.start((), events, seed=seed)
    prefix = session.advance(max_steps=budget)
    snapshot = session.snapshot()
    resumed = engine.restore(snapshot).advance()
    assert prefix.processed == resumed.processed[: len(prefix.processed)]
    assert prefix.intents == resumed.intents[: len(prefix.intents)]
    assert resumed == expected


def test_emitted_event_retains_causal_depth_and_ingress_sequence():
    def reducer(state, event, rng):
        children = (
            (Event(1, "emitted-priority-0"), Event(2, "emitted-future"))
            if event.name == "root"
            else ()
        )
        return Transition(state + (event.name,), events=children)

    events = (
        Event(1, "root"),
        Event(1, "already-queued"),
        Event(2, "already-future"),
    )
    machine = EventMachine(reducer)
    control = machine.run((), events, seed=17)
    session = machine.start((), events, seed=17)
    session.advance(max_steps=1)
    checkpoint = session.snapshot()
    actual = machine.restore(checkpoint).advance()
    assert actual == control
    assert actual.state == (
        "root", "already-queued", "emitted-priority-0",
        "already-future", "emitted-future",
    )


def test_split_inside_a_single_tick_preserves_tick_quota():
    reducer = lambda state, event, rng: Transition(state + (event.name,))
    engine = EventMachine(reducer)
    source = (Event(5, "one"), Event(5, "two"), Event(5, "three"))
    first = engine.start((), source, seed=0, max_events_per_tick=2)
    first.advance(max_steps=2)
    resumed = engine.restore(first.snapshot())
    with pytest.raises(FunnelRuntimeLimitError) as caught:
        resumed.advance()
    error = caught.value
    assert error.limit_kind == "max_events_per_tick"
    assert error.configured_cap == 2
    assert error.attempted_count == 3
    assert error.timestamp == 5
    assert error.causal_chain == ("three",)


def test_cumulative_event_cap_is_not_reset_after_resume():
    machine = EventMachine(lambda s, event, rng: Transition(s + (event.name,)))
    source = tuple(Event(i, f"event-{i}") for i in range(4))
    running = machine.start((), source, seed=0, max_events=3)
    running.advance(max_steps=2)
    resumed = machine.restore(running.snapshot())
    with pytest.raises(FunnelRuntimeLimitError) as caught:
        resumed.advance()
    assert caught.value.attempted_count == 4
    assert caught.value.causal_chain == ("event-3",)


def test_zero_delay_chain_survives_snapshot_restore():
    def reducer(state, event, rng):
        name = "A" if event.name == "B" else "B"
        return Transition(state + (event.name,), events=(Event(0, name),))

    machine = EventMachine(reducer)
    running = machine.start((), (Event(0, "A"),), seed=0, max_zero_delay_depth=3)
    running.advance(max_steps=2)
    resumed = machine.restore(running.snapshot())
    with pytest.raises(FunnelRuntimeLimitError) as caught:
        resumed.advance()
    assert caught.value.limit_kind == "max_zero_delay_depth"
    assert caught.value.attempted_count == 4
    assert caught.value.causal_chain == ("A", "B", "A", "B", "A")


def test_snapshot_restores_full_random_stream_not_seed_only():
    def reducer(state, event, rng):
        return Transition(state + ((event.name, rng.gauss(0, 1)),))

    machine = EventMachine(reducer)
    source = tuple(Event(i, f"draw-{i}") for i in range(9))
    expected = machine.run((), source, seed=314159)
    running = machine.start((), source, seed=314159)
    running.advance(max_steps=3)
    restored = machine.restore(running.snapshot())
    assert restored.advance() == expected
    assert len({repr(item[1]) for item in expected.state}) == 9


def test_snapshot_isolation_covers_mutable_state_payloads_and_intents():
    def reducer(state, event, rng):
        state["entries"].append(event.payload["amount"])
        return Transition(
            state,
            effects=(EffectIntent("audit", {"amount": event.payload["amount"]}),),
        )

    original = {"entries": []}
    e1 = Event(0, "payment", {"amount": 9})
    e2 = Event(1, "payment", {"amount": 4})
    engine = EventMachine(reducer)
    session = engine.start(original, (e1, e2), seed=1)
    session.advance(max_steps=1)
    snapshot = session.snapshot()
    first = engine.restore(snapshot).advance()
    second = engine.restore(snapshot).advance()
    assert first == second
    assert first.state["entries"] == [9, 4]
    assert first.intents == (
        EffectIntent("audit", {"amount": 9}),
        EffectIntent("audit", {"amount": 4}),
    )
    assert snapshot.state["entries"] == [9]
    assert snapshot.queue[0][4].payload == {"amount": 4}
    assert original["entries"] == [9]
    first.state["entries"].append(100)
    first.intents[1].payload["amount"] = 0
    assert engine.restore(snapshot).advance() == second


def test_checkpoint_binary_roundtrip_for_trusted_local_artifact():
    engine = EventMachine(_stochastic_reducer)
    events = (Event(0, "root-0"), Event(2, "root-1"))
    running = engine.start((), events, seed=15)
    running.advance(max_steps=1)
    wire = pickle.dumps(running.snapshot())
    loaded = pickle.loads(wire)
    assert engine.restore(loaded).advance() == engine.run((), events, seed=15)


def test_checkpoint_retains_decimal_balances_without_float_conversion():
    def reducer(state, event, rng):
        new = deepcopy(state)
        new["ledger"]["posted"].append(
            {"id": event.name, "amount": Decimal(str(event.payload))}
        )
        new["ledger"]["cash"] += Decimal(str(event.payload))
        return Transition(new)

    machine = EventMachine(reducer)
    state = {"ledger": {"cash": Decimal("0.00"), "posted": []}}
    events = (
        Event(0, "p1", "0.01"),
        Event(0, "p2", "0.02"),
        Event(1, "p3", "-0.01"),
    )
    running = machine.start(state, events, seed=0)
    running.advance(max_steps=2)
    checkpoint = running.snapshot()
    result = machine.restore(checkpoint).advance()
    assert result == machine.run(deepcopy(state), events, seed=0)
    assert result.state["ledger"]["cash"] == Decimal("0.02")
    assert all(
        type(entry["amount"]) is Decimal
        for entry in result.state["ledger"]["posted"]
    )


@pytest.mark.parametrize("max_steps", (0, -1, 1.0, True, False, math.inf))
def test_advance_rejects_invalid_event_count_budget(max_steps):
    session = EventMachine(_stochastic_reducer).start((), (), seed=0)
    with pytest.raises(ValueError, match="max_steps"):
        session.advance(max_steps=max_steps)


@pytest.mark.parametrize("until", (-1, float("nan"), float("inf"), True))
def test_advance_rejects_invalid_horizon_without_consuming(until):
    machine = EventMachine(_stochastic_reducer)
    session = machine.start((), (Event(1, "root"),), seed=5)
    with pytest.raises(ValueError, match="until"):
        session.advance(until=until)
    assert session.advance() == machine.run((), (Event(1, "root"),), seed=5)


def test_restore_rejects_non_snapshot_objects():
    machine = EventMachine(_stochastic_reducer)
    with pytest.raises(TypeError, match="EventSnapshot"):
        machine.restore({"state": None})
    with pytest.raises(TypeError, match="EventSnapshot"):
        machine.restore(None)


def test_snapshot_is_frozen_and_does_not_advance_event_cursor():
    engine = EventMachine(_stochastic_reducer)
    events = (Event(0, "root-0"), Event(0, "root-1"))
    session = engine.start((), events, seed=21)
    session.advance(max_steps=1)
    a, b = session.snapshot(), session.snapshot()
    assert a == b
    with pytest.raises((AttributeError, FrozenInstanceError)):
        a.next_ordinal = 991
    assert engine.restore(a).advance() == session.advance()


def test_advance_is_idempotent_after_calendar_drains():
    engine = EventMachine(lambda s, e, rng: Transition(s + 1))
    session = engine.start(0, (Event(0, "one"),), seed=0)
    first = session.advance()
    assert first.state == 1
    assert first.pending == ()
    assert session.advance() == first
    assert engine.restore(session.snapshot()).advance() == first


def test_checkpoint_retains_original_queue_limit_contract_on_fanout():
    def reducer(state, event, rng):
        emitted = (
            tuple(Event(3, f"child-{i}") for i in range(3))
            if event.name == "root"
            else ()
        )
        return Transition(state + 1, events=emitted)

    engine = EventMachine(reducer)
    state = engine.start(0, [Event(0, "root")], seed=0, max_queue_size=2)
    checkpoint = state.snapshot()
    with pytest.raises(FunnelRuntimeLimitError) as initial:
        state.advance()
    with pytest.raises(FunnelRuntimeLimitError) as restored:
        engine.restore(checkpoint).advance()
    assert restored.value.limit_kind == initial.value.limit_kind
    assert restored.value.attempted_count == initial.value.attempted_count
    assert restored.value.causal_chain == initial.value.causal_chain


@settings(max_examples=65, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 10), st.integers(0, 2)),
        max_size=30,
    ),
    st.integers(),
    st.integers(min_value=1, max_value=35),
)
def test_snapshot_restore_with_nonbinding_guards_matches_full_kernel(
    pairs, seed, split,
):
    source = tuple(
        Event(time, f"root-{i}", priority=priority)
        for i, (time, priority) in enumerate(pairs)
    )
    engine = EventMachine(_stochastic_reducer)
    capacity = max(1, 2 * len(source))
    maximum = max(1, 2 * len(source) + 1)
    expected = engine.run(
        (), source, seed=seed, max_queue_size=capacity,
        max_events_per_tick=maximum, max_zero_delay_depth=2,
    )
    running = engine.start(
        (), source, seed=seed, max_queue_size=capacity,
        max_events_per_tick=maximum, max_zero_delay_depth=2,
    )
    running.advance(max_steps=split)
    assert engine.restore(running.snapshot()).advance() == expected


def test_failed_dispatch_cannot_generate_a_misleading_checkpoint():
    def invalid_reducer(state, event, rng):
        state.append(event.name)
        raise ValueError("model rejected transition")

    machine = EventMachine(invalid_reducer)
    session = machine.start([], (Event(0, "bad"),), seed=0)
    with pytest.raises(ValueError, match="model rejected"):
        session.advance()
    with pytest.raises(RuntimeError, match="failed session"):
        session.snapshot()
    with pytest.raises(RuntimeError, match="failed session"):
        session.advance()


def test_exceeded_resource_budget_poisoned_session_cannot_be_saved():
    machine = EventMachine(lambda s, e, rng: Transition(s + 1))
    session = machine.start(
        0, (Event(0, "first"), Event(1, "second")), seed=0,
        max_events=1,
    )
    session.advance(max_steps=1)
    with pytest.raises(FunnelRuntimeLimitError):
        session.advance()
    with pytest.raises(RuntimeError, match="failed session"):
        session.snapshot()


def test_validation_error_does_not_poison_the_session():
    machine = EventMachine(lambda s, e, rng: Transition(s + 1))
    session = machine.start(0, (Event(0, "good"),), seed=0)
    with pytest.raises(ValueError, match="max_steps"):
        session.advance(max_steps=0)
    assert session.snapshot().next_ordinal == 1
    assert session.advance().state == 1

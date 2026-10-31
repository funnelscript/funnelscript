"""Executable falsification checks for research spec/event-kernel-v0.md."""

import math
import pytest

from funnelscript.core.event_machine import Event, EventMachine, EffectIntent, Transition


def append_event(state: tuple[str, ...], event: Event, rng) -> Transition[tuple[str, ...]]:
    return Transition(state=state + (event.name,))


def test_orders_events_by_time_priority_and_stable_insertion():
    machine = EventMachine(append_event)
    events = (
        Event(3, "late"),
        Event(1, "same_first"),
        Event(1, "urgent", priority=-1),
        Event(1, "same_second"),
        Event(2, "middle"),
    )

    result = machine.run((), events, seed=7)

    assert result.state == ("urgent", "same_first", "same_second", "middle", "late")
    assert tuple(e.name for e in result.processed) == result.state


def test_new_same_time_event_respects_existing_queue_order():
    def reducer(state, event, rng):
        scheduled = (Event(1, "third"),) if event.name == "first" else ()
        return Transition(state=state + (event.name,), events=scheduled)

    result = EventMachine(reducer).run(
        (), (Event(1, "first"), Event(1, "second")), seed=3
    )
    assert result.state == ("first", "second", "third")


def test_seeded_replay_is_deterministic_for_pure_user_model():
    def random_walk(state, event, rng):
        return Transition(state=state + (rng.random(),))

    machine = EventMachine(random_walk)
    events = tuple(Event(float(i), "sample") for i in range(8))

    first = machine.run((), events, seed=100)
    replay = machine.run((), events, seed=100)
    alternate = machine.run((), events, seed=101)

    assert first == replay
    assert first.state != alternate.state
    assert all(0.0 <= draw < 1.0 for draw in first.state)


@pytest.mark.parametrize("when", [-1, math.inf, -math.inf, math.nan])
def test_rejects_invalid_event_timestamps(when):
    with pytest.raises(ValueError, match="finite and non-negative"):
        Event(when, "invalid")


def test_rejects_scheduling_into_the_past():
    def reducer(state, event, rng):
        return Transition(state=state, events=(Event(0.5, "retrograde"),))

    with pytest.raises(ValueError, match="past"):
        EventMachine(reducer).run(0, (Event(1.0, "now"),), seed=0)


def test_rejects_retrograde_priority_at_current_time():
    def reducer(state, event, rng):
        return Transition(state=state, events=(Event(1, "retrograde", priority=-1),))

    with pytest.raises(ValueError, match="priority"):
        EventMachine(reducer).run(0, (Event(1, "now"),), seed=0)


def test_event_limit_stops_unbounded_zero_delay_recursion():
    def repeat(state, event, rng):
        return Transition(state=state + 1, events=(Event(event.time, "repeat"),))

    with pytest.raises(RuntimeError, match="max_events"):
        EventMachine(repeat).run(0, (Event(0, "repeat"),), seed=0, max_events=3)


def test_run_until_horizon_preserves_pending_events():
    result = EventMachine(append_event).run(
        (), (Event(0, "now"), Event(10, "later")), seed=0, until=2.0
    )

    assert result.state == ("now",)
    assert [event.name for event in result.pending] == ["later"]


def test_non_marketing_state_and_inert_effect_intents():
    def increment(state: int, event: Event, rng):
        return Transition(
            state=state + int(event.payload),
            effects=(EffectIntent("audit.counter", {"value": event.payload}),),
        )

    result = EventMachine(increment).run(0, (Event(0, "increment", payload=5),), seed=11)

    assert result.state == 5
    assert result.intents == (EffectIntent("audit.counter", {"value": 5}),)


def test_rejects_invalid_horizon_and_event_cap():
    machine = EventMachine(append_event)

    with pytest.raises(ValueError, match="until"):
        machine.run((), (), seed=0, until=math.nan)
    with pytest.raises(ValueError, match="max_events"):
        machine.run((), (), seed=0, max_events=0)


def test_kernel_api_is_exported_from_core_package():
    import funnelscript.core as core

    assert getattr(core, "EventMachine", None) is EventMachine
    assert getattr(core, "Event", None) is Event
    assert getattr(core, "EffectIntent", None) is EffectIntent


def test_rejects_non_intent_effect_outputs():
    def invalid_effect(state, event, rng):
        return Transition(state=state, effects=("raw_dispatch",))

    with pytest.raises(TypeError, match="EffectIntent"):
        EventMachine(invalid_effect).run(0, (Event(0, "x"),), seed=0)


def test_model_must_return_transition():
    with pytest.raises(TypeError, match="Transition"):
        EventMachine(lambda state, event, rng: state).run(0, (Event(0, "x"),), seed=0)

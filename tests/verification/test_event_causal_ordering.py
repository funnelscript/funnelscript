"""Independent EventKey ordering regression tests for Core 99, B1.

Research: stable discrete-event causality and queue total ordering.
Hypothesis: lower causal depth wins at identical (time, priority), even when
its event is enqueued after an event at greater depth.
Invariant: (time, priority, causal_depth, monotonic_sequence) is lexicographic;
priority outranks depth, and sequence resolves exact ties.
"""

import json
import os
import subprocess
import sys

from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core.event_machine import Event, EventMachine, RunResult, Transition


def _branching_reducer(state, event, rng):
    scheduled = {
        "origin": (Event(1, "deeper_parent", priority=-2),),
        "deeper_parent": (Event(2, "deep", priority=0),),
        "shallow_parent": (Event(2, "shallow", priority=0),),
    }.get(event.name, ())
    return Transition(state=(*state, event.name), events=scheduled)


def test_causal_depth_precedes_insertion_sequence_for_equal_time_and_priority():
    initial = (Event(0, "origin"), Event(1, "shallow_parent", priority=1))
    result = EventMachine(_branching_reducer).run((), initial, seed=12)

    assert result.state == (
        "origin", "deeper_parent", "shallow_parent", "shallow", "deep"
    )
    assert tuple(event.name for event in result.processed) == result.state


def test_pending_calendar_retains_causal_depth_order_after_horizon():
    initial = (Event(0, "origin"), Event(1, "shallow_parent", priority=1))
    result = EventMachine(_branching_reducer).run(
        (), initial, seed=12, until=1
    )

    assert result.state == ("origin", "deeper_parent", "shallow_parent")
    assert tuple(event.name for event in result.pending) == ("shallow", "deep")


@settings(max_examples=60, deadline=None)
@given(
    start=st.integers(min_value=0, max_value=50),
    delay=st.integers(min_value=1, max_value=50),
    seed=st.integers(),
)
def test_causal_order_stable_under_time_translation_and_seed(start, delay, seed):
    def reducer(state, event, rng):
        if event.name == "origin":
            events = (Event(start + delay, "deeper_parent", priority=-2),)
        elif event.name == "deeper_parent":
            events = (Event(start + 2 * delay, "deep"),)
        elif event.name == "shallow_parent":
            events = (Event(start + 2 * delay, "shallow"),)
        else:
            events = ()
        return Transition(state=(*state, event.name), events=events)

    initial = (
        Event(start, "origin"),
        Event(start + delay, "shallow_parent", priority=1),
    )
    result = EventMachine(reducer).run((), initial, seed=seed)
    assert result.state == (
        "origin", "deeper_parent", "shallow_parent", "shallow", "deep"
    )


def test_event_priority_still_dominates_causal_depth():
    def reducer(state, event, rng):
        scheduled = {
            "origin": (Event(1, "deeper_parent", priority=-2),),
            "deeper_parent": (Event(2, "deep", priority=-1),),
            "shallow_parent": (Event(2, "shallow", priority=0),),
        }.get(event.name, ())
        return Transition(state=(*state, event.name), events=scheduled)

    result = EventMachine(reducer).run(
        (), (Event(0, "origin"), Event(1, "shallow_parent", priority=1)), seed=0
    )
    assert result.state == (
        "origin", "deeper_parent", "shallow_parent", "deep", "shallow"
    )


def test_causal_order_and_seeded_draws_are_hash_seed_independent():
    source = """
import json
from funnelscript.core.event_machine import Event, EventMachine, Transition

def reduce(state, event, rng):
    future = {
        "origin": (Event(1, "deeper_parent", priority=-2),),
        "deeper_parent": (Event(2, "deep"),),
        "shallow_parent": (Event(2, "shallow"),),
    }.get(event.name, ())
    return Transition((*state, (event.name, rng.random())), future)

result = EventMachine(reduce).run(
    (), (Event(0, "origin"), Event(1, "shallow_parent", priority=1)), seed=17
)
print(json.dumps({"state": result.state, "pending": len(result.pending)}))
"""
    outputs = []
    for value in (0, 1, 7, 79, 999):
        run = subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True, text=True, check=False,
            env={**os.environ, "PYTHONHASHSEED": str(value)},
        )
        assert run.returncode == 0, run.stderr
        outputs.append(json.loads(run.stdout))

    assert outputs == [outputs[0]] * 5
    assert [name for name, _ in outputs[0]["state"]] == [
        "origin", "deeper_parent", "shallow_parent", "shallow", "deep"
    ]


def test_event_api_generic_subscript_preserves_runtime_transition():
    machine = EventMachine[int](
        lambda state, event, rng: Transition[int](state=state + 1)
    )
    result = machine.run(0, (Event(0, "step"),), seed=0)
    assert isinstance(result, RunResult)
    assert result.state == 1
    assert result.processed == (Event(0, "step"),)

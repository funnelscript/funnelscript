"""DEVS bounds at World and identity-isolated population boundaries.

Research: event-kernel-v0 and runtime-resource-envelope-v0 H-RQ1/RQ2/RT1.
Hypothesis: opt-in caps reach the canonical EventMachine without reordering
events, changing keyed draws or coupling independent population queues.
Invariants: |Q_agent| <= Lq, count(agent,t) <= Lt, zero-delay depth <= Lz.
"""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core import Event, FunnelRuntimeLimitError
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent,
    PopulationExecutor,
    WorldExecutor,
)

SOURCE = """world ResourceDemo {
  agent Visitor {
    state phase: string = "new";
    state hits: int = 0;
    rule CountRule on event Tick { transition hits = hits + 1; }
    rule BeginRule on event Begin { emit Loop after 0; }
    rule LoopRule on event Loop { emit Loop after 0; }
    rule DelayRule on event Delay { emit Delay after 1; }
  }
}
"""

RNG_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/population-reference/identity-rng.fnl"
)


@pytest.fixture
def executor(tmp_path):
    path = tmp_path / "resource-demo.fnl"
    path.write_text(SOURCE, encoding="utf-8")
    return WorldExecutor(Parser.from_file(path))


def population(executor, agents=("a", "b")):
    identities = [PopulationAgent(a, "cohort", "segment") for a in agents]
    return PopulationExecutor(
        executor, identities, seed=17, trial_id="t1",
        state_field="phase", states=("new",),
    )


def test_world_queue_cap_rejects_initial_unbounded_iterable_at_exact_boundary(executor):
    consumed = []

    def future():
        for index in range(10):
            consumed.append(index)
            yield Event(10, "Visitor.Tick")

    with pytest.raises(FunnelRuntimeLimitError) as raised:
        executor.run(future(), until=0, max_queue_size=2)

    error = raised.value
    assert consumed == [0, 1, 2]
    assert error.limit_kind == "max_queue_size"
    assert error.configured_cap == 2
    assert error.attempted_count == 3
    assert error.timestamp == 10
    assert error.causal_chain == ("Visitor.Tick",)


def test_world_zero_delay_cycle_preserves_named_ancestry(executor):
    with pytest.raises(FunnelRuntimeLimitError) as raised:
        executor.run((Event(0, "Visitor.Begin"),), max_zero_delay_depth=2)
    error = raised.value
    assert error.limit_kind == "max_zero_delay_depth"
    assert error.configured_cap == 2
    assert error.attempted_count == 3
    assert error.causal_chain == (
        "Visitor.Begin", "Visitor.Loop", "Visitor.Loop", "Visitor.Loop"
    )
    assert error.trace_complete


def test_world_tick_budget_rejects_third_independent_same_time_root(executor):
    events = tuple(Event(2, "Visitor.Tick") for _ in range(3))
    with pytest.raises(FunnelRuntimeLimitError) as raised:
        executor.run(events, max_events_per_tick=2)
    assert raised.value.limit_kind == "max_events_per_tick"
    assert raised.value.configured_cap == 2
    assert raised.value.attempted_count == 3
    assert raised.value.timestamp == 2
    assert raised.value.causal_chain == ("Visitor.Tick",)


def test_world_advancing_delay_resets_zero_depth_and_per_tick_budget(executor):
    result = executor.run(
        (Event(0, "Visitor.Delay"),), until=3,
        max_queue_size=1, max_events_per_tick=1, max_zero_delay_depth=0,
    )
    assert [event.time for event in result.processed] == [0, 1, 2, 3]
    assert [(event.time, event.name) for event in result.pending] == [
        (4, "Visitor.Delay")
    ]


def test_world_nonbinding_guards_preserve_default_result_and_trace(executor):
    events = (Event(3, "Visitor.Tick"), Event(1, "Visitor.Tick"))
    raw_trace = []
    guarded_trace = []
    raw = executor.run(events, seed=23, trace=raw_trace)
    guarded = executor.run(
        events, seed=23, trace=guarded_trace,
        max_queue_size=2, max_events_per_tick=1, max_zero_delay_depth=0,
    )
    assert guarded == raw
    assert guarded_trace == raw_trace
    assert guarded.state["Visitor"]["hits"] == 2


def test_world_default_total_cap_is_backwards_compatible(executor):
    with pytest.raises(FunnelRuntimeLimitError, match="max_events reached") as raised:
        executor.run((Event(0, "Visitor.Begin"),), max_events=2)
    assert raised.value.limit_kind == "max_events"
    assert raised.value.attempted_count == 3
    assert not raised.value.trace_complete


def test_population_budgets_are_independent_per_agent_not_global(executor):
    people = population(executor, ("a", "b", "c"))
    events = {name: (Event(0, "Visitor.Tick"),) for name in ("a", "b", "c")}
    unbounded = people.run(events, trace=True)
    guarded = people.run(
        events, trace=True,
        max_queue_size=1, max_events_per_tick=1, max_zero_delay_depth=0,
    )
    assert guarded == unbounded
    assert all(len(result.processed) == 1 for result in guarded.results.values())
    assert guarded.partitions["new"] == frozenset(("a", "b", "c"))


def test_population_one_agent_queue_failure_is_not_silently_truncated(executor):
    people = population(executor)
    events = {
        "a": (Event(0, "Visitor.Tick"),),
        "b": (Event(0, "Visitor.Tick"), Event(1, "Visitor.Tick")),
    }
    with pytest.raises(FunnelRuntimeLimitError) as raised:
        people.run(events, max_queue_size=1)
    assert raised.value.limit_kind == "max_queue_size"
    assert raised.value.attempted_count == 2
    assert raised.value.causal_chain == ("Visitor.Tick",)
    assert raised.value.__notes__ == ["population agent_id=b"]


def test_population_zero_delay_loop_surfaces_exact_child_chain(executor):
    with pytest.raises(FunnelRuntimeLimitError) as raised:
        population(executor).run(
            {"a": (Event(0, "Visitor.Tick"),),
             "b": (Event(0, "Visitor.Begin"),)},
            max_zero_delay_depth=1,
        )
    assert raised.value.limit_kind == "max_zero_delay_depth"
    assert raised.value.causal_chain == (
        "Visitor.Begin", "Visitor.Loop", "Visitor.Loop"
    )
    assert raised.value.trace_complete
    assert raised.value.__notes__ == ["population agent_id=b"]


def test_population_tick_budget_applies_to_each_agent(executor):
    with pytest.raises(FunnelRuntimeLimitError) as raised:
        population(executor).run(
            {"a": (Event(0, "Visitor.Tick"), Event(0, "Visitor.Tick"))},
            max_events_per_tick=1,
        )
    assert raised.value.limit_kind == "max_events_per_tick"
    assert raised.value.configured_cap == 1
    assert raised.value.attempted_count == 2


@pytest.mark.parametrize(
    "bad_kwargs",
    [
        {"max_queue_size": 0},
        {"max_queue_size": True},
        {"max_events_per_tick": -1},
        {"max_events_per_tick": 1.5},
        {"max_zero_delay_depth": -1},
        {"max_zero_delay_depth": False},
    ],
)
def test_world_and_population_reject_malformed_resource_budgets(executor, bad_kwargs):
    for run in (
        lambda: executor.run((), **bad_kwargs),
        lambda: population(executor).run({}, **bad_kwargs),
    ):
        with pytest.raises(ValueError, match=next(iter(bad_kwargs))):
            run()


@settings(max_examples=80, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=20), max_size=16),
    st.integers(min_value=0, max_value=2**32 - 1),
)
def test_nonbinding_bounds_preserve_keyed_world_and_population_rng(times, seed):
    world = WorldExecutor(Parser.from_file(RNG_REFERENCE))
    events = tuple(Event(t, "Visitor.Tick") for t in times)
    limits = {
        "max_queue_size": max(1, len(events)),
        "max_events_per_tick": max(1, len(events)),
        "max_zero_delay_depth": 0,
    }
    assert world.run(events, seed=seed) == world.run(events, seed=seed, **limits)
    agents = (PopulationAgent("a", "c", "s"), PopulationAgent("b", "c", "s"))
    people = PopulationExecutor(
        world, agents, seed=seed, trial_id="trial",
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    calendar = {"a": events, "b": tuple(reversed(events))}
    assert people.run(calendar) == people.run(calendar, **limits)

def test_world_emitted_fanout_hits_queue_budget_at_second_child(tmp_path):
    source = SOURCE.replace(
        "rule BeginRule on event Begin { emit Loop after 0; }",
        "rule BeginRule on event Begin { emit Tick after 1; emit Tick after 1; }",
    )
    path = tmp_path / "fanout.fnl"
    path.write_text(source, encoding="utf-8")
    world = WorldExecutor(Parser.from_file(path))

    with pytest.raises(FunnelRuntimeLimitError) as raised:
        world.run((Event(0, "Visitor.Begin"),), max_queue_size=1)
    assert raised.value.limit_kind == "max_queue_size"
    assert raised.value.configured_cap == 1
    assert raised.value.attempted_count == 2
    assert raised.value.timestamp == 1
    assert raised.value.causal_chain == ("Visitor.Begin", "Visitor.Tick")
    assert raised.value.trace_complete

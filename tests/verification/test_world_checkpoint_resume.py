"""World-level checkpoint replay using real parsed .fnls and identity-derived RNG.

Anchor: DEVS replay equivalence and deterministic agent-local random streams.
H: world state, ordered events and stochastic draws survive checkpoint/restore.
Invariant: for each immutable agent identity i, world_run(seed_i) equals the
concatenation of world_start(seed_i).advance(split), restore().advance().
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent,
    PopulationExecutor,
    WorldExecutor,
)

ROOT = Path(__file__).resolve().parents[2]
STOCHASTIC = ROOT / "tests/fixtures/world-conformance/stochastic.fnls"
ORDERING = ROOT / "tests/fixtures/world-conformance/ordering.fnls"
POPULATION = ROOT / "tests/fixtures/population-reference/identity-rng.fnls"


def _world(path: Path) -> WorldExecutor:
    return WorldExecutor(Parser.from_file(path))


@settings(max_examples=75, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=20), max_size=35),
    st.integers(),
    st.integers(min_value=0, max_value=20),
)
def test_stochastic_world_checkpoint_matches_continuous_trace(times, seed, split):
    executor = _world(STOCHASTIC)
    events = tuple(Event(time, "A.Tick") for time in times)
    expected = executor.run(events, seed=seed)
    live = executor.start(events, seed=seed)
    live.advance(until=split)
    checkpoint = live.snapshot()
    resumed = executor.restore(checkpoint).advance()
    assert resumed == expected


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(min_value=0, max_value=12), st.integers(0, 5)),
        max_size=20,
    ),
    st.integers(),
    st.integers(min_value=1, max_value=25),
)
def test_world_emission_payload_and_priority_are_identical_after_resume(
    pairs, seed, split,
):
    executor = _world(ORDERING)
    source = tuple(
        Event(t, "Log.Mark", payload={"digit": d})
        for t, d in pairs
    ) + (Event(0, "Log.Trigger"),)
    expected = executor.run(source, seed=seed)
    live = executor.start(source, seed=seed)
    live.advance(max_steps=split)
    after = executor.restore(live.snapshot()).advance()
    assert after == expected
    assert after.state["Log"]["sum"] == 4 + sum(d for _, d in pairs)
    assert after.pending == ()


@pytest.mark.parametrize("split", [0, 1, 2, 3, 10])
def test_identity_derived_population_rng_survives_individual_world_checkpoints(
    split,
):
    world = _world(POPULATION)
    agents = (
        PopulationAgent("alice", "c1", "A"),
        PopulationAgent("bob", "c1", "B"),
        PopulationAgent("charlie", "c2", "A"),
    )
    population = PopulationExecutor(
        world, agents, seed=912, trial_id="checkpoint-trial",
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    inputs = {
        item.agent_id: (Event(0, "Visitor.Tick"), Event(2, "Visitor.Tick"))
        for item in agents
    }
    expected = population.run(inputs)
    recovered = {}
    for agent in agents:
        agent_id = agent.agent_id
        stream = population.stream_seed(agent_id)
        session = world.start(inputs[agent_id], seed=stream)
        if split:
            session.advance(max_steps=split)
        payload = pickle.dumps(session.snapshot())
        recovered[agent_id] = world.restore(pickle.loads(payload)).advance()
    assert recovered == expected.results
    assert all(
        actual.state["Visitor"]["phase"] == "terminal"
        for actual in recovered.values()
    )
    assert len({
        recovered[agent.agent_id].state["Visitor"]["draw"] for agent in agents
    }) == len(agents)


def test_world_checkpoint_original_ast_is_unmodified_and_state_is_independent():
    world = _world(ORDERING)
    before = world.world.model_dump_json()
    live = world.start((Event(0, "Log.Trigger"),), seed=33)
    live.advance(max_steps=1)
    checkpoint = live.snapshot()
    one = world.restore(checkpoint).advance()
    two = world.restore(checkpoint).advance()
    assert one == two
    assert one.state["Log"]["sum"] == 4
    assert world.world.model_dump_json() == before
    one.state["Log"]["sum"] = 4000
    assert world.restore(checkpoint).advance() == two


def test_unrecognized_world_events_preserve_typed_runtime_error_after_resume():
    from funnelscript.runtime.world_executor import WorldExecutionError

    world = _world(POPULATION)
    active = world.start((Event(0, "Visitor.Tick"), Event(1, "Missing.Event")), seed=0)
    active.advance(max_steps=1)
    checkpoint = active.snapshot()
    with pytest.raises(WorldExecutionError, match="Unknown event"):
        world.restore(checkpoint).advance()


def test_checkpoint_with_true_horizon_keeps_pending_world_events_unchanged():
    world = _world(ORDERING)
    events = (
        Event(0, "Log.Trigger"),
        Event(10, "Log.Mark", payload={"digit": 2}),
    )
    active = world.start(events, seed=0)
    until_zero = active.advance(until=0)
    assert tuple(e.time for e in until_zero.pending) == (10,)
    assert tuple(e.name for e in until_zero.processed) == ("Log.Trigger", "Log.Mark")
    resumed = world.restore(active.snapshot()).advance()
    assert resumed == world.run(events, seed=0)


@pytest.mark.parametrize("count", [100, 1_000])
def test_thousand_world_events_use_same_calendar_after_three_checkpoints(count):
    world = _world(POPULATION)
    events = tuple(Event(i // 3, "Visitor.Tick") for i in range(count))
    expected = world.run(events, seed=75)
    live = world.start(events, seed=75)
    live.advance(max_steps=10)
    live = world.restore(live.snapshot())
    live.advance(max_steps=70)
    live = world.restore(live.snapshot())
    live.advance(max_steps=350)
    actual = world.restore(live.snapshot()).advance()
    assert actual == expected
    assert len(actual.processed) == count


def test_checkpoint_from_another_world_is_rejected_before_execution(tmp_path):
    first = tmp_path / "first.fnls"
    other = tmp_path / "other.fnls"
    first.write_text(
        "world Same { entity E { state n: int = 0; "
        "rule R on event Tick { transition n = n + 1; } } }",
        encoding="utf-8",
    )
    other.write_text(
        "world Same { entity E { state n: int = 0; "
        "rule R on event Tick { transition n = n + 2; } } }",
        encoding="utf-8",
    )
    source = _world(first)
    target = _world(other)
    live = source.start((Event(0, "E.Tick"), Event(1, "E.Tick")), seed=1)
    live.advance(max_steps=1)
    with pytest.raises(ValueError, match="World checkpoint"):
        target.restore(live.snapshot())


def test_identical_world_content_at_different_source_path_can_resume(tmp_path):
    one = tmp_path / "one.fnls"
    two = tmp_path / "two.fnls"
    source = (
        "world W { entity E { state n: int = 0; "
        "rule R on event Tick { transition n = n + 1; } } }"
    )
    one.write_text(source, encoding="utf-8")
    two.write_text(source, encoding="utf-8")
    first = _world(one)
    other = _world(two)
    events = (Event(0, "E.Tick"), Event(1, "E.Tick"))
    live = first.start(events, seed=1)
    live.advance(max_steps=1)
    assert other.restore(live.snapshot()).advance() == first.run(events, seed=1)


def test_unbound_kernel_checkpoint_is_rejected_as_a_world_snapshot():
    from funnelscript.core import EventMachine, Transition

    kernel = EventMachine(lambda state, event, rng: Transition(state + 1))
    session = kernel.start(0, (Event(0, "Tick"),), seed=1)
    with pytest.raises(ValueError, match="World checkpoint"):
        _world(POPULATION).restore(session.snapshot())

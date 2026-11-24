"""Falsification suite for full-population DEVS checkpoints.

Research: agent-based simulation (ABM) state preservation, keyed RNG
streams, and deterministic independent discrete-event calendars.
H: Continuing each enrolled agent after a complete population snapshot
produces identical RunResult traces and partitions as uninterrupted runs.
Invariant: each agent identity is in exactly one partition, one cohort
and one segment, before and after any legal split/resume.
"""

from __future__ import annotations

import pickle
import random
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.core import Event, FunnelRuntimeLimitError
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent,
    PopulationExecutor,
    PopulationSnapshot,
    WorldExecutor,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/fixtures/population-reference/identity-rng.fnls"
STATES = ("new", "terminal", "inactive")


def agents(n: int = 8) -> tuple[PopulationAgent, ...]:
    return tuple(
        PopulationAgent(f"p-{i:04d}", f"cohort-{i % 3}", f"segment-{i % 2}")
        for i in range(n)
    )


def population(
    n: int = 8, *,
    enrollment: tuple[PopulationAgent, ...] | None = None,
    seed: int = 42,
    trial: str = "demo-trial",
    source: Path = SOURCE,
    states: tuple[str, ...] = STATES,
) -> PopulationExecutor:
    return PopulationExecutor(
        WorldExecutor(Parser.from_file(source)),
        enrollment if enrollment is not None else agents(n),
        seed=seed, trial_id=trial, state_field="phase", states=states,
    )


def source_events(
    enrolled: tuple[PopulationAgent, ...],
    *,
    count: int = 3,
) -> dict[str, tuple[Event, ...]]:
    return {
        agent.agent_id: tuple(Event(i, "Visitor.Tick") for i in range(count))
        for agent in enrolled
    }


def _partitions_are_total(result, enrolled) -> None:
    ids = {item.agent_id for item in enrolled}
    assert set(result.results) == ids
    assert set().union(*result.partitions.values()) == ids
    assert sum(len(partition) for partition in result.partitions.values()) == len(ids)
    assert set().union(*result.segments.values()) == ids
    assert set().union(*result.cohorts.values()) == ids
    assert all(
        sum(aid in group for group in result.segments.values()) == 1
        and sum(aid in group for group in result.cohorts.values()) == 1
        and sum(aid in group for group in result.partitions.values()) == 1
        for aid in ids
    )


@settings(max_examples=85, deadline=None)
@given(
    st.lists(st.lists(st.integers(min_value=0, max_value=9), max_size=7),
             min_size=1, max_size=9),
    st.integers(min_value=0, max_value=9),
    st.integers(min_value=0, max_value=2**64 - 1),
)
def test_arbitrary_agent_calendars_and_horizon_splits_match_reference(
    timings, cutoff, seed,
):
    enrolled = agents(len(timings))
    subject = population(enrollment=enrolled, seed=seed)
    inputs = {
        agent.agent_id: tuple(Event(time, "Visitor.Tick") for time in times)
        for agent, times in zip(enrolled, timings, strict=True)
    }
    expected = subject.run(inputs)
    session = subject.start(inputs)
    before = session.advance(until=cutoff)
    assert all(
        event.time <= cutoff
        for result in before.results.values() for event in result.processed
    )
    checkpoint = session.snapshot()
    assert isinstance(checkpoint, PopulationSnapshot)
    recovered = subject.restore(checkpoint).advance()
    assert recovered == expected
    _partitions_are_total(recovered, enrolled)


@settings(max_examples=80, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=15), min_size=1, max_size=12),
    st.integers(min_value=1, max_value=10),
    st.integers(min_value=0, max_value=2**32 - 1),
)
def test_arbitrary_per_agent_step_budgets_match_uninterrupted_runs(
    lengths, steps, seed,
):
    enrolled = agents(len(lengths))
    subject = population(enrollment=enrolled, seed=seed)
    inputs = {
        agent.agent_id: tuple(Event(i // 3, "Visitor.Tick") for i in range(length))
        for agent, length in zip(enrolled, lengths, strict=True)
    }
    expected = subject.run(inputs)
    session = subject.start(inputs)
    partial = session.advance(max_steps=steps)
    assert all(len(result.processed) <= steps for result in partial.results.values())
    restored = subject.restore(session.snapshot())
    actual = restored.advance()
    assert actual == expected
    _partitions_are_total(actual, enrolled)


@pytest.mark.parametrize("count", [1, 2, 10, 50])
def test_full_population_snapshot_pickle_roundtrip_matches_original(count):
    enrolled = agents(count)
    source = source_events(enrolled, count=4)
    subject = population(enrollment=enrolled)
    expected = subject.run(source)
    running = subject.start(source)
    running.advance(max_steps=2)
    wire = pickle.dumps(running.snapshot(), protocol=5)
    resumed = subject.restore(pickle.loads(wire))
    assert resumed.advance() == expected
    assert len(resumed.snapshot().sessions) == count


def test_snapshot_can_be_restored_repeatedly_without_aliasing():
    enrolled = agents(3)
    subject = population(enrollment=enrolled)
    running = subject.start(source_events(enrolled, count=5))
    running.advance(max_steps=1)
    saved = running.snapshot()
    first = subject.restore(saved).advance()
    second = subject.restore(saved).advance()
    assert first == second
    aid = enrolled[0].agent_id
    first.results[aid].state["Visitor"]["draw"] = -99
    assert subject.restore(saved).advance() == second
    assert running.snapshot() == saved


def test_partial_partition_is_exactly_recomputed_at_each_checkpoint():
    enrolled = agents(6)
    subject = population(enrollment=enrolled)
    src = {
        enrolled[0].agent_id: (Event(0, "Visitor.Tick"),),
        enrolled[1].agent_id: (Event(0, "Visitor.Deactivate"),),
        enrolled[2].agent_id: (Event(9, "Visitor.Tick"),),
        enrolled[3].agent_id: (Event(4, "Visitor.Deactivate"),),
    }
    running = subject.start(src)
    initial = running.advance(until=0)
    assert initial.partitions["terminal"] == frozenset({enrolled[0].agent_id})
    assert initial.partitions["inactive"] == frozenset({enrolled[1].agent_id})
    assert len(initial.partitions["new"]) == 4
    _partitions_are_total(initial, enrolled)
    resumed = subject.restore(running.snapshot())
    middle = resumed.advance(until=4)
    assert len(middle.partitions["inactive"]) == 2
    last = subject.restore(resumed.snapshot()).advance()
    assert last == subject.run(src)
    assert len(last.partitions["terminal"]) == 2
    _partitions_are_total(last, enrolled)


@pytest.mark.parametrize("role", ["world-transitions", "policy", "forecast-v2"])
def test_stream_namespace_is_bound_to_population_checkpoint(role):
    enrolled = agents(3)
    subject = population(enrollment=enrolled)
    inputs = source_events(enrolled, count=4)
    reference = subject.run(inputs, stream_role=role)
    session = subject.start(inputs, stream_role=role)
    session.advance(max_steps=2)
    snap = session.snapshot()
    assert snap.stream_role == role
    assert subject.restore(snap).advance() == reference
    if role != "world-transitions":
        assert reference.results != subject.run(inputs).results


@pytest.mark.parametrize(
    "kwargs,expected_error",
    [
        ({"seed": 43}, "seed"),
        ({"trial": "other-trial"}, "trial"),
        ({"states": ("new", "terminal")}, "states"),
    ],
)
def test_changed_population_context_rejects_checkpoint(kwargs, expected_error):
    enrolled = agents(4)
    snapshot = population(enrollment=enrolled).start({}).snapshot()
    changed = population(enrollment=enrolled, **kwargs)
    with pytest.raises(ValueError, match=expected_error):
        changed.restore(snapshot)


@pytest.mark.parametrize(
    "membership",
    [
        (PopulationAgent("p-0000", "other-cohort", "segment-0"),),
        (PopulationAgent("p-0000", "cohort-0", "other-segment"),),
        (PopulationAgent("added", "cohort-1", "segment-1"),),
    ],
)
def test_changed_agent_identity_or_membership_rejects_restore(membership):
    original = agents(4)
    checkpoint = population(enrollment=original).start({}).snapshot()
    alternate = membership + original[1:]
    subject = population(enrollment=alternate)
    with pytest.raises(ValueError, match="enrollment"):
        subject.restore(checkpoint)


def test_agent_enrollment_order_can_change_without_changing_identity_streams():
    original = agents(20)
    subject = population(enrollment=original)
    events = source_events(original, count=3)
    started = subject.start(events)
    started.advance(max_steps=1)
    checkpoint = started.snapshot()
    permuted = list(original)
    random.Random(76543).shuffle(permuted)
    other = population(enrollment=tuple(permuted))
    resumed = other.restore(checkpoint).advance()
    assert resumed.results == subject.run(events).results
    assert resumed.partitions == subject.run(events).partitions
    assert resumed.segments == subject.run(events).segments
    assert resumed.cohorts == subject.run(events).cohorts


def test_mismatch_world_ast_is_rejected_before_executing_any_agent(tmp_path):
    original = agents(3)
    checkpoint = population(enrollment=original).start({}).snapshot()
    source = tmp_path / "altered.fnls"
    source.write_text(
        SOURCE.read_text(encoding="utf-8").replace(
            'transition phase = "terminal";',
            'transition phase = "inactive";',
        ),
        encoding="utf-8",
    )
    altered = population(enrollment=original, source=source)
    with pytest.raises(ValueError, match="World"):
        altered.restore(checkpoint)


@pytest.mark.parametrize(
    "edit",
    [
        lambda snap: replace(snap, schema_version="population-v99"),
        lambda snap: replace(snap, rng_version="not-the-accepted-derivation"),
        lambda snap: replace(snap, stream_role="not-the-original-stream"),
        lambda snap: replace(snap, sessions=snap.sessions[:-1]),
        lambda snap: replace(snap, sessions=snap.sessions + (snap.sessions[0],)),
        lambda snap: replace(snap, sessions=(("unknown", snap.sessions[0][1]),) + snap.sessions[1:]),
    ],
)
def test_malformed_population_snapshot_envelope_is_rejected(edit):
    subject = population(n=3)
    original = subject.start({}).snapshot()
    with pytest.raises((TypeError, ValueError)):
        subject.restore(edit(original))


def test_missing_source_events_default_to_empty_calendar():
    enrolled = agents(5)
    subject = population(enrollment=enrolled)
    session = subject.start({enrolled[2].agent_id: (Event(2, "Visitor.Tick"),)})
    first = session.advance(until=0)
    assert first.partitions["new"] == frozenset(x.agent_id for x in enrolled)
    saved = session.snapshot()
    final = subject.restore(saved).advance()
    assert final.partitions["terminal"] == frozenset({enrolled[2].agent_id})
    assert len(final.partitions["new"]) == 4


def test_fatal_agent_error_identifies_actual_identity_and_rejects_resnapshot():
    enrolled = agents(3)
    subject = population(enrollment=enrolled)
    session = subject.start({
        enrolled[1].agent_id: (Event(0, "Unknown.Event"),),
    })
    with pytest.raises(ValueError, match="Unknown event") as caught:
        session.advance()
    assert any("p-0001" in message for message in caught.value.__notes__)
    with pytest.raises(RuntimeError, match="failed"):
        session.snapshot()


def test_existing_resource_quota_is_preserved_after_population_restore():
    enrolled = agents(2)
    subject = population(enrollment=enrolled)
    source = source_events(enrolled, count=3)
    session = subject.start(source, max_events=2)
    session.advance(max_steps=1)
    saved = session.snapshot()
    resumed = subject.restore(saved)
    with pytest.raises(FunnelRuntimeLimitError) as caught:
        resumed.advance()
    assert caught.value.limit_kind == "max_events"
    assert any("agent_id=" in message for message in caught.value.__notes__)


def test_restore_refuses_cross_type_or_missing_snapshot():
    subject = population(n=2)
    for bad in (None, {}, "invalid"):
        with pytest.raises(TypeError, match="PopulationSnapshot"):
            subject.restore(bad)


def test_population_snapshot_is_idempotent_after_all_calendars_finish():
    enrolled = agents(3)
    subject = population(enrollment=enrolled)
    session = subject.start(source_events(enrolled, count=2))
    final = session.advance()
    assert session.advance() == final
    restored = subject.restore(session.snapshot())
    assert restored.advance() == final


def test_population_snapshot_restores_guarded_zeno_limit():
    enrolled = agents(2)
    subject = population(enrollment=enrolled)
    session = subject.start(
        {
            agent.agent_id: (Event(0, "Visitor.Tick"), Event(0, "Visitor.Tick"))
            for agent in enrolled
        },
        max_events_per_tick=1,
    )
    session.advance(max_steps=1)
    checkpoint = session.snapshot()
    # Each time bucket is independent for the tick budget. Replacing 1 with 2
    # would hide an actual violation if a checkpoint forgot its current tick.
    resumed = subject.restore(checkpoint)
    with pytest.raises(FunnelRuntimeLimitError) as caught:
        resumed.advance()
    assert caught.value.limit_kind == "max_events_per_tick"

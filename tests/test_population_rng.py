"""Independent keyed stream and cohort perturbation contract, Phase 007A."""

from pathlib import Path
import json
import random

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent, PopulationExecutor, WorldExecutor, RNG_DERIVATION_VERSION,
)

ROOT = Path(__file__).parent / "fixtures/population-reference"
SOURCE = ROOT / "identity-rng.fnl"
GOLDEN = json.loads((ROOT / "keyed-rng-golden.json").read_text(encoding="utf-8"))
FIRST = {aid: item["draws"][0] for aid, item in GOLDEN["trial-1"].items()}
SECOND = {aid: item["draws"][1] for aid, item in GOLDEN["trial-1"].items()}
GOLDEN_SEED = int(GOLDEN["trial-1"]["agent-000"]["digest"], 16)


def members(n):
    return [
        PopulationAgent(f"agent-{i:03}", "batch-" + str(i % 3), "north" if i % 2 == 0 else "south")
        for i in range(n)
    ]


def runner(agents, trial="trial-1", seed=1):
    return PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)), agents,
        trial_id=trial, seed=seed, state_field="phase",
        states=("new", "terminal", "inactive"),
    )


def events(agents, count=1):
    return {a.agent_id: tuple(Event(i, "Visitor.Tick") for i in range(count)) for a in agents}


def draws(result):
    return {key: value.state["Visitor"]["draw"] for key, value in result.results.items()}


@pytest.mark.parametrize("n", [10, 100, 1000])
def test_initialized_partitions_segments_and_terminal_inclusion(n):
    agents = members(n)
    subject = runner(agents)
    initial = subject.run({})
    complete = subject.run(events(agents))
    ids = {agent.agent_id for agent in agents}
    assert initial.partitions["new"] == frozenset(ids)
    assert complete.partitions["terminal"] == frozenset(ids)
    assert sum(len(v) for v in complete.partitions.values()) == n
    assert set().union(*complete.partitions.values()) == ids
    assert set().union(*complete.segments.values()) == ids
    assert len(complete.segments["north"]) == (n + 1) // 2
    assert len(complete.segments["south"]) == n // 2
    assert set().union(*complete.cohorts.values()) == ids
    assert all(set(v) <= ids for v in complete.partitions.values())


def test_exact_fixed_golden_provenance_and_draw_sequence():
    agents = members(2)
    subject = runner(agents)
    assert RNG_DERIVATION_VERSION == "population-rng-v1/sha256-mt19937"
    assert subject.stream_seed("agent-000") == GOLDEN_SEED
    one = subject.run(events(agents))
    two = subject.run(events(agents))
    assert draws(one) == FIRST
    assert one == two
    double = subject.run(events(agents, count=2))
    assert draws(double) == SECOND
    assert len(double.results["agent-000"].processed) == 2


def test_order_reverse_and_fixed_pseudorandom_permutation():
    agents = members(100)
    baseline = runner(agents).run(events(agents))
    reversed_result = runner(list(reversed(agents))).run(events(agents))
    permuted = agents.copy()
    random.Random(4455).shuffle(permuted)
    shuffled = runner(permuted).run(events(agents))
    assert draws(baseline) == draws(reversed_result) == draws(shuffled)
    assert baseline.partitions == reversed_result.partitions == shuffled.partitions
    assert baseline.segments == shuffled.segments


def test_unrelated_insertion_removal_and_segment_reordering():
    agents = members(10)
    baseline = runner(agents).run(events(agents))
    inserted = agents[:4] + [PopulationAgent("extra", "batch-x", "south")] + agents[4:]
    addition = runner(inserted).run(events(inserted))
    removal = runner(agents[:-1]).run(events(agents[:-1]))
    assert all(draws(addition)[a.agent_id] == draws(baseline)[a.agent_id] for a in agents)
    assert all(draws(removal)[a.agent_id] == draws(baseline)[a.agent_id] for a in agents[:-1])
    reassigned = [
        PopulationAgent(a.agent_id, a.cohort_id, "south" if a.segment_id == "north" else "north")
        for a in reversed(agents)
    ]
    assert draws(runner(reassigned).run(events(reassigned))) == draws(baseline)


def test_trial_isolation_reorder_and_role_namespace():
    agents = members(2)
    first = runner(agents, "trial-1")
    second = runner(agents, "trial-2")
    x = first.run(events(agents))
    y = second.run(events(agents))
    z = first.run(events(agents))
    assert x == z
    assert draws(y) == {aid: item["first"] for aid, item in GOLDEN["trial-2"].items()}
    assert first.stream_seed("agent-000") != second.stream_seed("agent-000")
    assert first.stream_seed("agent-000", stream_role="policy") != first.stream_seed("agent-000")
    assert first.run(events(agents), stream_role="policy") == first.run(events(agents), stream_role="policy")


def test_paired_policy_comparison_preserves_unchanged_exogenous_identity():
    agents = members(10)
    baseline = runner(agents).run(events(agents))
    intervention_events = events(agents)
    intervention_events["agent-001"] = (Event(0, "Visitor.Tick"), Event(1, "Visitor.Tick"))
    intervention = runner(list(reversed(agents))).run(intervention_events)
    for agent in agents:
        if agent.agent_id != "agent-001":
            assert intervention.results[agent.agent_id] == baseline.results[agent.agent_id]
    assert intervention.results["agent-001"].state["Visitor"]["draw"] == SECOND["agent-001"]
    assert baseline.results["agent-001"].state["Visitor"]["draw"] == FIRST["agent-001"]


@pytest.mark.parametrize("bad", ["", " space", "x/y", "é", None, 1, "a\nb"])
def test_missing_or_noncanonical_agent_identity_rejected(bad):
    with pytest.raises(ValueError, match="agent_id"):
        PopulationAgent(bad, "batch", "north")


@pytest.mark.parametrize("field,bad", [("cohort_id", ""), ("segment_id", None)])
def test_missing_cohort_or_segment_rejected(field, bad):
    values = {"agent_id": "x", "cohort_id": "batch", "segment_id": "north"}
    values[field] = bad
    with pytest.raises(ValueError, match=field):
        PopulationAgent(**values)


def test_duplicate_identity_and_empty_population_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        runner([members(1)[0], members(1)[0]])
    with pytest.raises(ValueError, match="nonempty"):
        runner([])


@pytest.mark.parametrize("seed", [-1, 2**64, True, 1.0, "1"])
def test_invalid_world_seed_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        runner(members(2), seed=seed)


@pytest.mark.parametrize("trial", ["", "with space", None, 1])
def test_invalid_trial_rejected(trial):
    with pytest.raises(ValueError, match="trial_id"):
        runner(members(2), trial=trial)


def test_unknown_agent_and_stream_role_and_event_owner_rejected():
    subject = runner(members(2))
    with pytest.raises(ValueError, match="unknown agent_id"):
        subject.stream_seed("absent")
    with pytest.raises(ValueError, match="stream_role"):
        subject.stream_seed("agent-000", stream_role="")
    with pytest.raises(ValueError, match="unknown event owner"):
        subject.run({"absent": (Event(0, "Visitor.Tick"),)})


def test_invalid_state_partition_and_source_world_rejected():
    with pytest.raises(ValueError, match="initial"):
        PopulationExecutor(
            WorldExecutor(Parser.from_file(SOURCE)), members(2),
            seed=1, trial_id="trial-1", state_field="phase", states=("terminal",),
        )
    with pytest.raises(ValueError, match="state_field"):
        PopulationExecutor(
            WorldExecutor(Parser.from_file(SOURCE)), members(2),
            seed=1, trial_id="trial-1", state_field="draw", states=("new",),
        )


def test_rejects_non_replayable_generator_events():
    subject = runner(members(2))
    with pytest.raises(TypeError, match="ordered, replayable"):
        subject.run({"agent-000": (Event(0, "Visitor.Tick") for _ in range(1))})


def test_event_time_bound_replays_without_advance_or_rng_state_leak():
    agents = members(2)
    subject = runner(agents)
    source_events = {a.agent_id: (Event(0, "Visitor.Tick"), Event(2, "Visitor.Tick")) for a in agents}
    early = subject.run(source_events, until=0)
    full = subject.run(source_events, until=2)
    assert draws(early) == FIRST
    assert draws(full) == SECOND
    assert all(len(v.pending) == 1 for v in early.results.values())
    assert all(len(v.pending) == 0 for v in full.results.values())


def test_terminal_inactive_and_new_are_disjoint_and_exhaustive():
    agents = members(10)
    output = runner(agents).run({
        agents[0].agent_id: (Event(0, "Visitor.Tick"),),
        agents[1].agent_id: (Event(0, "Visitor.Deactivate"),),
    })
    assert output.partitions["terminal"] == frozenset({agents[0].agent_id})
    assert output.partitions["inactive"] == frozenset({agents[1].agent_id})
    assert output.partitions["new"] == frozenset(a.agent_id for a in agents[2:])
    assert set().union(*output.partitions.values()) == {a.agent_id for a in agents}
    assert all(
        not (set(left) & set(right))
        for i, left in enumerate(output.partitions.values())
        for right in list(output.partitions.values())[i + 1:]
    )


def test_invalid_runtime_partition_value_is_not_silently_counted(tmp_path):
    bad_source = tmp_path / "invalid-phase.fnl"
    bad_source.write_text(
        SOURCE.read_text(encoding="utf-8").replace(
            'transition phase = "terminal";', 'transition phase = "unregistered";'
        ),
        encoding="utf-8",
    )
    executor = PopulationExecutor(
        WorldExecutor(Parser.from_file(bad_source)), members(2),
        seed=1, trial_id="trial-1",
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    with pytest.raises(ValueError, match="invalid checkpoint state"):
        executor.run(events(members(2)))


def test_colliding_derived_seeds_rejected(monkeypatch):
    subject = runner(members(2))
    monkeypatch.setattr(subject, "stream_seed", lambda aid, *, stream_role: 123)
    with pytest.raises(ValueError, match="collision"):
        subject.run(events(members(2)))


def test_event_limit_is_enforced_by_existing_kernel():
    subject = runner(members(2))
    with pytest.raises(RuntimeError, match="max_events reached"):
        subject.run(events(members(2), count=2), max_events=1)

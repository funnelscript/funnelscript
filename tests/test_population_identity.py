"""Identity-preserving opt-in World population runner contract (H-ID1)."""

from pathlib import Path

from funnelscript.core import Event
from funnelscript.parser import Parser
import funnelscript.runtime.world_executor as world_runtime


SOURCE = Path(__file__).parent / "fixtures/population-reference/identity-rng.fnl"


def test_ten_instances_have_exhaustive_identity_partition():
    agent_type = getattr(world_runtime, "PopulationAgent", None)
    runner_type = getattr(world_runtime, "PopulationExecutor", None)
    assert agent_type is not None and runner_type is not None, "Missing opt-in population API"

    agents = [
        agent_type(f"agent-{n:03}", "batch-1", "north" if n % 2 == 0 else "south")
        for n in range(10)
    ]
    runner = runner_type(
        world_runtime.WorldExecutor(Parser.from_file(SOURCE)),
        agents, seed=1, trial_id="trial-1",
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    events = {agent.agent_id: (Event(0, "Visitor.Tick"),) for agent in agents}
    output = runner.run(events)
    expected_ids = {agent.agent_id for agent in agents}
    assert set(output.results) == expected_ids
    assert output.partitions["terminal"] == frozenset(expected_ids)
    assert output.partitions["new"] == frozenset()
    assert output.partitions["inactive"] == frozenset()
    assert sum(map(len, output.partitions.values())) == 10
    assert set().union(*output.partitions.values()) == expected_ids
    assert output.results["agent-000"].state["Visitor"]["draw"] == 0.15311003683137503
    assert output.results["agent-001"].state["Visitor"]["draw"] == 0.7905505363492208

"""Measure actual identity-keyed World Population checkpoint replay.

Runs one deterministic scenario per fresh process. Diagnostic measurements
are not release SLAs and no metric is used as a CI performance threshold.
Every reported digest includes the complete result trace, not just totals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import platform
import resource
import sys
import time
from dataclasses import asdict
from pathlib import Path

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent,
    PopulationExecutor,
    PopulationResult,
    WorldExecutor,
)

SOURCE = Path(__file__).resolve().parents[1] / (
    "tests/fixtures/population-reference/identity-rng.fnl"
)


def _inputs(
    agent_count: int, event_count: int,
) -> tuple[tuple[PopulationAgent, ...], dict[str, tuple[Event, ...]]]:
    """Allocate exactly event_count events over agent_count distinct IDs."""
    quotient, remainder = divmod(event_count, agent_count)
    agents = tuple(
        PopulationAgent(
            f"benchmark-{i:06d}",
            f"cohort-{i % 10}",
            f"segment-{i % 3}",
        )
        for i in range(agent_count)
    )
    events = {
        agent.agent_id: tuple(
            Event(tick, "Visitor.Tick")
            for tick in range(quotient + (i < remainder))
        )
        for i, agent in enumerate(agents)
    }
    return agents, events


def _result_sha256(result: PopulationResult) -> str:
    """Stable digest of full per-agent states, emitted events and partitions."""
    digest = hashlib.sha256()
    header = {
        "trial_id": result.trial_id,
        "stream_role": result.stream_role,
        "rng_version": result.rng_version,
        "partitions": {
            key: sorted(value)
            for key, value in result.partitions.items()
        },
        "segments": {
            key: sorted(value) for key, value in result.segments.items()
        },
        "cohorts": {
            key: sorted(value) for key, value in result.cohorts.items()
        },
    }
    digest.update(json.dumps(header, sort_keys=True).encode("ascii"))
    for aid in sorted(result.results):
        run = result.results[aid]
        digest.update(aid.encode("ascii"))
        payload = {
            "state": run.state,
            "processed": [asdict(event) for event in run.processed],
            "pending": [asdict(event) for event in run.pending],
            "intents": [asdict(effect) for effect in run.intents],
        }
        digest.update(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )
    return digest.hexdigest()


def run_scenario(events: int, agents: int, mode: str) -> dict[str, object]:
    """Run a real .fnl population trial with or without mid-run restoration."""
    enrolled, source_events = _inputs(agents, events)
    runner = PopulationExecutor(
        WorldExecutor(Parser.from_file(SOURCE)),
        enrolled, seed=731, trial_id="population-benchmark",
        state_field="phase", states=("new", "terminal", "inactive"),
    )
    checkpoint_bytes = 0
    started = time.perf_counter()
    if mode == "continuous":
        result = runner.run(source_events)
    elif mode == "checkpoint":
        session = runner.start(source_events)
        max_steps = max(1, events // agents // 3)
        session.advance(max_steps=max_steps)
        checkpoint_data = pickle.dumps(session.snapshot(), protocol=5)
        checkpoint_bytes = len(checkpoint_data)
        session = runner.restore(pickle.loads(checkpoint_data))
        result = session.advance()
    else:
        raise ValueError("unknown benchmark mode")
    elapsed = time.perf_counter() - started
    processed = sum(len(item.processed) for item in result.results.values())
    pending = sum(len(item.pending) for item in result.results.values())
    if processed != events or pending:
        raise AssertionError("incomplete population event calendar")
    if result.partitions["terminal"] != frozenset(
        agent.agent_id for agent in enrolled
    ):
        raise AssertionError("unexpected terminal population partition")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "mode": mode,
        "events": events,
        "agents": agents,
        "processed": processed,
        "pending": pending,
        "terminal": len(result.partitions["terminal"]),
        "checkpoint_bytes": checkpoint_bytes,
        "sha256": _result_sha256(result),
        "elapsed_seconds": elapsed,
        "process_peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=1_000)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--mode", choices=("continuous", "checkpoint"), required=True)
    args = parser.parse_args()
    if not 1 <= args.events <= 100_000:
        parser.error("--events must be between 1 and 100000")
    if not 1 <= args.agents <= min(args.events, 1_000):
        parser.error("--agents must be between 1 and min(events,1000)")
    print(json.dumps(run_scenario(args.events, args.agents, args.mode), sort_keys=True))


if __name__ == "__main__":
    main()

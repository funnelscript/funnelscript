"""Scale-probe contract for aggregate Population World calendars.

Research: ABM resource envelopes and measured end-to-end checkpoints.
Hypothesis: 1,000 to 100,000 agent events produce identical canonical
result digests in continuous versus snapshot/restore execution.
Invariant: sum(processed_i) == requested_event_count and no agent disappears
from its cohort, segment or terminal state after a full recovery.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/benchmark_population_checkpoint.py"
)


def _probe(
    count: int,
    population_size: int,
    mode: str,
) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--events", str(count),
            "--agents", str(population_size),
            "--mode", mode,
        ],
        capture_output=True, text=True, check=False, timeout=40,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("events", "population_size"),
    [
        (5, 1),
        (12, 3),
        (101, 7),
        (1_000, 30),
        (1_000, 1_000),
    ],
)
def test_independent_benchmark_modes_have_same_trace_digest(
    events, population_size,
):
    continuous = _probe(events, population_size, "continuous")
    resumed = _probe(events, population_size, "checkpoint")
    assert continuous["processed"] == resumed["processed"] == events
    assert continuous["agents"] == resumed["agents"] == population_size
    assert continuous["terminal"] == resumed["terminal"] == population_size
    assert continuous["pending"] == resumed["pending"] == 0
    assert continuous["sha256"] == resumed["sha256"]
    assert continuous["mode"] == "continuous"
    assert resumed["mode"] == "checkpoint"
    assert continuous["elapsed_seconds"] >= 0
    assert resumed["elapsed_seconds"] >= 0
    assert continuous["process_peak_rss_bytes"] > 0
    assert resumed["process_peak_rss_bytes"] > 0
    assert resumed["checkpoint_bytes"] > 0
    assert continuous["checkpoint_bytes"] == 0


@pytest.mark.parametrize(
    ("events", "agents"),
    [(0, 1), (-1, 1), (100001, 1), (1, 0), (1, -1), (3, 4)],
)
def test_scale_probe_rejects_invalid_limits(events, agents):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--events", str(events),
            "--agents", str(agents),
            "--mode", "continuous",
        ],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode != 0
    assert "must be between" in result.stderr


def test_scale_probe_rejects_invalid_mode():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--events", "100",
            "--agents", "10",
            "--mode", "unknown",
        ],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_scale_probe_output_is_machine_readable_and_excludes_raw_agent_state():
    output = _probe(17, 4, "checkpoint")
    assert set(output) >= {
        "mode", "events", "agents", "processed", "pending",
        "terminal", "sha256", "checkpoint_bytes", "elapsed_seconds",
        "process_peak_rss_bytes", "python", "platform",
    }
    assert output["events"] == 17
    assert output["processed"] == 17
    assert len(output["sha256"]) == 64
    assert "Visitor" not in output
    assert "results" not in output

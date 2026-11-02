"""Independent smoke checks for the non-contractual EventMachine resource probe."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_event_resources.py"


@pytest.mark.parametrize(
    ("scenario", "processed", "pending"),
    [("initial", 0, 3), ("fanout", 1, 3), ("due", 3, 0)],
)
def test_resource_probe_reports_complete_calendar(scenario, processed, pending):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--scenario", scenario, "--count", "3"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["scenario"] == scenario
    assert result["count"] == 3
    assert (result["processed"], result["pending"]) == (processed, pending)
    assert result["tracemalloc_peak_bytes"] > 0
    assert result["process_peak_rss_bytes"] > 0
    assert result["elapsed_seconds"] >= 0


def test_resource_probe_rejects_unbounded_requested_count():
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--scenario", "initial", "--count", "100001"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode != 0
    assert "--count must be between" in run.stderr

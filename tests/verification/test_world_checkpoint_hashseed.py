"""Independent-process portability of trusted World runtime checkpoints.

Anchor: content-addressed model identity and deterministic event sourcing.
H: restoring the same checkpoint under independently seeded Python hash maps
preserves every event, ordering decision, source state and pending calendar.
Invariant: sha256(canonical_run_result) is unchanged for equal .fnls model and
inputs across two OS processes; a changed World definition is rejected.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / (
    "tests/fixtures/world-conformance/ordering.fnls"
)
SCRIPT = """
import base64
import hashlib
import json
import os
import pickle
from dataclasses import asdict

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor

world = WorldExecutor(Parser.from_file(os.environ["FNL_SOURCE"]))
events = (
    Event(0, "Log.Trigger"),
    Event(0, "Log.Mark", {"digit": 2}),
    Event(1, "Log.Mark", {"digit": 3}),
    Event(1, "Log.Trigger"),
    Event(4, "Log.Mark", {"digit": 7}),
)
if os.environ["FNL_ACTION"] == "save":
    session = world.start(events, seed=78, max_zero_delay_depth=5)
    session.advance(max_steps=2)
    checkpoint = pickle.dumps(session.snapshot(), protocol=5)
    print(base64.b64encode(checkpoint).decode("ascii"))
else:
    if os.environ["FNL_ACTION"] == "resume":
        checkpoint = pickle.loads(base64.b64decode(os.environ["FNL_CHECKPOINT"]))
        result = world.restore(checkpoint).advance()
    else:
        result = world.run(events, seed=78, max_zero_delay_depth=5)
    payload = {
        "state": result.state,
        "processed": [asdict(event) for event in result.processed],
        "pending": [asdict(event) for event in result.pending],
        "intents": [asdict(effect) for effect in result.intents],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(json.dumps({
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "payload": payload,
    }, sort_keys=True))
"""


def _run(seed: int, action: str, checkpoint: str = "") -> str:
    env = {
        **os.environ,
        "PYTHONHASHSEED": str(seed),
        "FNL_SOURCE": str(SOURCE),
        "FNL_ACTION": action,
        "FNL_CHECKPOINT": checkpoint,
    }
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("initial_hashseed", [0, 1, 7])
def test_checkpoint_serialized_in_one_process_restores_in_other_hash_seeds(
    initial_hashseed,
):
    wire = _run(initial_hashseed, "save")
    assert len(base64.b64decode(wire)) > 100
    reference = json.loads(_run(initial_hashseed, "full"))
    actual = [json.loads(_run(seed, "resume", wire)) for seed in (0, 1, 7, 79, 999)]
    assert actual == [reference] * 5
    assert reference["payload"]["state"]["Log"] == {"sum": 20}
    assert [item["name"] for item in reference["payload"]["processed"]] == [
        "Log.Trigger", "Log.Mark", "Log.Mark", "Log.Mark",
        "Log.Trigger", "Log.Mark", "Log.Mark",
    ]
    assert reference["payload"]["pending"] == []


def test_split_world_checkpoint_is_identical_on_repeated_process_restore():
    wire = _run(3, "save")
    a = _run(31, "resume", wire)
    b = _run(31, "resume", wire)
    assert a == b
    assert json.loads(a)["sha256"] == json.loads(_run(3, "full"))["sha256"]

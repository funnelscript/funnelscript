"""Cross-process oracle for identity-keyed aggregate Population replay.

Research anchor: schedule-independent agent-based modeling and reproducible
random streams under Python's randomized hash seed.
H: any saved population checkpoint can resume in a fresh Python interpreter
independent of enrollment ordering, process hash seed and source path.
Invariant: canonical population SHA-256 and individual agent event traces
match a continuous run for all tested seeds, partitions and cohorts.
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
    "tests/fixtures/population-reference/identity-rng.fnl"
)


RUNNER = """
import base64
import hashlib
import json
import os
import pickle
from dataclasses import asdict

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent, PopulationExecutor, WorldExecutor,
)

ids = {f"participant-{idx:04}" for idx in range(24)}
enrolled = [
    PopulationAgent(
        aid,
        f"cohort-{int(aid[-2:]) % 3}",
        f"segment-{int(aid[-2:]) % 2}",
    )
    for aid in ids
]
runner = PopulationExecutor(
    WorldExecutor(Parser.from_file(os.environ["FNL_SOURCE"])),
    enrolled, seed=104, trial_id="replay-trial", state_field="phase",
    states=("new", "terminal", "inactive"),
)
inputs = {
    agent.agent_id: (
        Event(0, "Visitor.Tick"),
        Event(1, "Visitor.Deactivate") if int(agent.agent_id[-2:]) % 4 == 0
        else Event(1, "Visitor.Tick"),
        Event(7, "Visitor.Tick"),
        Event(10, "Visitor.Tick"),
    )
    for agent in enrolled
}

def encode_result(result):
    def calendar(run):
        return {
            "state": run.state,
            "processed": [asdict(event) for event in run.processed],
            "intents": [asdict(intent) for intent in run.intents],
            "pending": [asdict(event) for event in run.pending],
        }
    canonical = {
        "trial": result.trial_id,
        "role": result.stream_role,
        "rng_version": result.rng_version,
        "results": {aid: calendar(value) for aid, value in result.results.items()},
        "partitions": {
            name: sorted(ids) for name, ids in result.partitions.items()
        },
        "cohorts": {name: sorted(ids) for name, ids in result.cohorts.items()},
        "segments": {name: sorted(ids) for name, ids in result.segments.items()},
    }
    wire = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return json.dumps(
        {
            "sha256": hashlib.sha256(wire).hexdigest(),
            "payload": canonical,
        },
        sort_keys=True,
    )

action = os.environ["FNL_ACTION"]
if action == "save":
    active = runner.start(inputs, stream_role="policy", max_events_per_tick=6)
    active.advance(until=1)
    print(base64.b64encode(pickle.dumps(active.snapshot(), protocol=5)).decode())
elif action == "full":
    print(encode_result(runner.run(
        inputs, stream_role="policy", max_events_per_tick=6,
    )))
elif action == "resume":
    trusted_checkpoint = pickle.loads(
        base64.b64decode(os.environ["FNL_CHECKPOINT"])
    )
    result = runner.restore(trusted_checkpoint).advance()
    print(encode_result(result))
else:
    raise ValueError("unsupported action")
"""


def _run(
    hashseed: int,
    action: str,
    checkpoint: str = "",
    *,
    source: Path = SOURCE,
) -> str:
    env = {
        **os.environ,
        "PYTHONHASHSEED": str(hashseed),
        "FNL_SOURCE": str(source),
        "FNL_ACTION": action,
        "FNL_CHECKPOINT": checkpoint,
    }
    result = subprocess.run(
        [sys.executable, "-c", RUNNER],
        capture_output=True, text=True, env=env, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("snapshot_seed", (0, 7, 99))
def test_checkpoint_created_in_process_a_replays_in_five_other_processes(
    snapshot_seed,
):
    wire = _run(snapshot_seed, "save")
    assert len(base64.b64decode(wire)) > 500
    control = json.loads(_run(snapshot_seed, "full"))
    for restore_seed in (0, 1, 7, 99, 999):
        actual = json.loads(_run(restore_seed, "resume", wire))
        assert actual == control
        assert actual["sha256"] == control["sha256"]
        assert len(actual["payload"]["results"]) == 24
        assert len(actual["payload"]["partitions"]["terminal"]) == 24
        assert all(
            len(result["processed"]) == 4
            for result in actual["payload"]["results"].values()
        )


def test_identity_derived_replay_does_not_depend_on_manifest_entry_order():
    a = json.loads(_run(11, "full"))
    b = json.loads(_run(999, "full"))
    assert a == b
    checkpoint = _run(1, "save")
    assert json.loads(_run(3, "resume", checkpoint)) == b


def test_cross_process_restoration_is_idempotent_and_canonical():
    checkpoint = _run(9, "save")
    recovered_one = _run(88, "resume", checkpoint)
    recovered_two = _run(88, "resume", checkpoint)
    assert recovered_one == recovered_two
    sha = json.loads(recovered_one)["sha256"]
    assert len(sha) == 64
    assert sha == json.loads(_run(22, "full"))["sha256"]


def test_equivalent_source_moved_to_another_path_is_accepted(tmp_path):
    mirror = tmp_path / "equivalent.fnl"
    mirror.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    checkpoint = _run(0, "save")
    assert json.loads(_run(999, "resume", checkpoint, source=mirror)) == json.loads(
        _run(999, "full", source=mirror)
    )


def test_source_semantics_changed_between_processes_is_rejected(tmp_path):
    altered = tmp_path / "changed.fnl"
    source = SOURCE.read_text(encoding="utf-8")
    assert 'transition phase = "terminal";' in source
    altered.write_text(
        source.replace(
            'transition phase = "terminal";',
            'transition phase = "inactive";',
        ),
        encoding="utf-8",
    )
    checkpoint = _run(1, "save")
    with pytest.raises(AssertionError, match="World definition mismatch"):
        _run(2, "resume", checkpoint, source=altered)

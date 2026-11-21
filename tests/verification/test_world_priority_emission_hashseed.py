"""Independent cross-process .fnl World event-ordering regression.

Research anchor: stable discrete-event scheduling with the total order
(time, priority, causal depth, monotonic insertion sequence).
Hypothesis: given identical ingress order, PYTHONHASHSEED cannot change
a same-tick collision or the emitted child's processed position.
Invariant: canonical trace bytes equal the fixed C-ORDER conformance oracle;
permuting equal-priority ingress changes the trace, not the final sum.
"""

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path("tests/fixtures/world-conformance")
_SOURCE = """
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor

root = Path("tests/fixtures/world-conformance")
cases = json.loads((root / "cases.json").read_text())
case = next(item for item in cases["cases"] if item["id"] == "C-ORDER")
records = list(case["events"])
if os.environ["FNL_REORDER_EQUAL_PRIORITY"] == "1":
    records[1], records[3] = records[3], records[1]
events = tuple(Event(**record) for record in records)
result = WorldExecutor(Parser.from_file(root / case["source"])).run(
    events, seed=case["seed"],
)
record = {
    "state": result.state,
    "processed": [asdict(event) for event in result.processed],
    "pending": [asdict(event) for event in result.pending],
    "intents": [asdict(intent) for intent in result.intents],
}
canonical = json.dumps(
    record, sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode("utf-8")
print(json.dumps({
    "sha256": sha256(canonical).hexdigest(),
    "record": record,
}, sort_keys=True))
"""


def _replay(hash_seed: int, *, reorder_equal_priority: bool = False) -> dict:
    process = subprocess.run(
        [sys.executable, "-c", _SOURCE],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTHONHASHSEED": str(hash_seed),
            "FNL_REORDER_EQUAL_PRIORITY": "1" if reorder_equal_priority else "0",
            "PYTHONPATH": os.pathsep.join(sys.path),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def _case() -> dict:
    cases = json.loads((ROOT / FIXTURES / "cases.json").read_text())
    return next(item for item in cases["cases"] if item["id"] == "C-ORDER")


def test_emitted_collision_and_priority_trace_match_golden_across_hash_seeds():
    results = [_replay(seed) for seed in (0, 1, 7, 79, 999)]
    assert results == [results[0]] * len(results)
    actual = results[0]["record"]
    expected = _case()["expected"]
    assert actual == expected
    expected_digest = sha256(
        json.dumps(
            expected, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert results[0]["sha256"] == expected_digest
    assert [event["payload"] for event in actual["processed"]] == [
        {"digit": 2}, None, {"digit": 1}, {"digit": 3}, {"digit": 4},
    ]
    assert actual["state"]["Log"]["sum"] == 10


def test_equal_priority_ingress_permutation_is_detected_by_trace_digest():
    original = _replay(7)
    reordered = _replay(7, reorder_equal_priority=True)
    assert original["sha256"] != reordered["sha256"]
    assert original["record"]["processed"] != reordered["record"]["processed"]
    assert original["record"]["state"] == reordered["record"]["state"]
    assert [event["payload"] for event in reordered["record"]["processed"]] == [
        {"digit": 2}, None, {"digit": 3}, {"digit": 1}, {"digit": 4},
    ]

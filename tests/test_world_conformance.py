"""Phase 006: independent, fixed World semantic conformance cases.

The expected records live in cases.json; production internals never calculate
golden state, event order or sample values for these assertions.
"""

from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path
import random

import pytest

from funnelscript.compiler.world_ast import WorldTypeError
from funnelscript.core.event_machine import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.runtime.world_executor import WorldExecutor, WorldExecutionError
from funnelscript.tokens import Lexer

ROOT = Path(__file__).parent / "fixtures" / "world-conformance"
CORPUS = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
ERRORS = {
    "ParserError": ParserError,
    "WorldTypeError": WorldTypeError,
    "WorldExecutionError": WorldExecutionError,
    "RuntimeError": RuntimeError,
}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def _event(record: dict) -> Event:
    return Event(
        time=record["time"], name=record["name"],
        payload=record["payload"], priority=record["priority"],
    )


def _run(case: dict):
    source = ROOT / case["source"]
    assert source.resolve().is_relative_to(ROOT.resolve())
    executor = WorldExecutor(Parser.from_file(source))
    return executor.run(
        [_event(item) for item in case["events"]],
        seed=case["seed"],
        until=case.get("until"),
        max_events=case.get("max_events", 100),
    )


def _trace(case: dict, result) -> dict:
    return {
        "schema": CORPUS["schema"],
        "engine": {"package": "funnelscript", "version": version("funnelscript")},
        "seed": case["seed"],
        "configuration": {
            "until": case.get("until"), "max_events": case.get("max_events", 100),
        },
        "state": result.state,
        "processed": [asdict(event) for event in result.processed],
        "pending": [asdict(event) for event in result.pending],
        "intents": [asdict(intent) for intent in result.intents],
    }


def _expected_trace(case: dict) -> dict:
    return {
        "schema": CORPUS["schema"],
        "engine": {"package": "funnelscript", "version": version("funnelscript")},
        "seed": case["seed"],
        "configuration": {
            "until": case.get("until"), "max_events": case.get("max_events", 100),
        },
        **case["expected"],
    }


def _case(case_id: str) -> dict:
    return next(item for item in CORPUS["cases"] if item["id"] == case_id)


def test_corpus_schema_and_stable_ids():
    assert CORPUS["schema"] == "world-conformance/v0"
    ids = [item["id"] for item in CORPUS["cases"]]
    assert len(ids) == len(set(ids))
    assert all(item["source"].endswith(".fnl") for item in CORPUS["cases"])
    assert all(("expected" in item) != ("reject" in item) for item in CORPUS["cases"])


@pytest.mark.parametrize(
    "case", [c for c in CORPUS["cases"] if "expected" in c],
    ids=lambda case: case["id"],
)
def test_fixed_golden_traces_and_three_replays(case):
    expected_bytes = _canonical(_expected_trace(case))
    # Three fresh parsers, executors and calendars; not repeated serialization.
    for _ in range(3):
        result = _run(case)
        assert _canonical(_trace(case, result)) == expected_bytes, case["id"]
        assert len(result.processed) <= case.get("max_events", 100)
        for before, after in zip(result.processed, result.processed[1:]):
            assert (before.time, before.priority) <= (after.time, after.priority)


@pytest.mark.parametrize(
    "case", [c for c in CORPUS["cases"] if "reject" in c],
    ids=lambda case: case["id"],
)
def test_fixed_rejection_boundary(case):
    rejection = case["reject"]
    assert rejection["boundary"] in {
        "parse", "type", "import", "ingress", "runtime", "calendar"
    }
    with pytest.raises(ERRORS[rejection["exception"]], match=rejection["contains"]):
        _run(case)


def test_false_guard_preserves_rng_stream_and_does_not_schedule():
    guarded = _run(_case("C-RNG-SEED-1"))
    unguarded = _run(_case("C-RNG-NO-SKIP"))
    assert guarded.state == unguarded.state
    assert guarded.pending == unguarded.pending == ()
    assert [item.name for item in guarded.processed] == ["A.Skip", "A.Tick"]
    assert [item.name for item in unguarded.processed] == ["A.Tick"]


def test_equal_priority_insertion_perturbation_changes_ordered_trace():
    original = _case("C-ORDER")
    perturbed = dict(original)
    events = list(original["events"])
    events[1], events[3] = events[3], events[1]
    perturbed["events"] = events
    assert _canonical(_trace(original, _run(perturbed))) != _canonical(
        _expected_trace(original)
    )


def test_changed_seed_matches_independent_reference_outcomes():
    left = _case("C-RNG-SEED-1")["expected"]["state"]["A"]
    right = _case("C-RNG-SEED-2")["expected"]["state"]["A"]
    assert left["first"] == 0.13436424411240122
    assert right["first"] == 0.9560342718892494
    assert left["first"] != right["first"]
    assert _run(_case("C-RNG-SEED-1")).state["A"] == left
    assert _run(_case("C-RNG-SEED-2")).state["A"] == right


@pytest.mark.parametrize("id", [
    "R-DYNAMIC-ZERO", "R-PAYLOAD-MISSING", "R-PAYLOAD-BOOL",
    "R-PAYLOAD-EXTRA", "R-GUARDED-PAYLOAD", "R-UNKNOWN-EVENT",
])
def test_rejected_event_does_not_mutate_caller_owned_state(id):
    case = _case(id)
    executor = WorldExecutor(Parser.from_file(ROOT / case["source"]))
    before = executor.initial_state()
    baseline = _canonical(before)
    with pytest.raises(ERRORS[case["reject"]["exception"]]):
        executor.advance(before, _event(case["events"][0]), rng=random.Random(0))
    assert _canonical(before) == baseline


@pytest.mark.parametrize("time", [-1, float("nan"), float("inf"), -float("inf"), True, "0"])
def test_invalid_timestamp_rejected_on_event_construction(time):
    with pytest.raises(ValueError, match="finite and non-negative"):
        Event(time, "Pair.Go")


@pytest.mark.parametrize("configuration,fragment", [
    ({"until": float("nan")}, "until"),
    ({"until": -1}, "until"),
    ({"max_events": 0}, "max_events"),
    ({"max_events": True}, "max_events"),
])
def test_calendar_run_configuration_rejected_before_processing(configuration, fragment):
    subject = WorldExecutor(Parser.from_file(ROOT / "snapshot.fnl"))
    with pytest.raises(ValueError, match=fragment):
        subject.run([Event(0, "Pair.Go")], **configuration)


def test_parser_exhaustion_is_a_deliberate_diagnostic():
    with pytest.raises(ParserError, match="Unexpected end of token stream"):
        Parser([]).current()
    with pytest.raises(ParserError, match="Unclosed world declaration"):
        Parser(Lexer("world W {").tokenize()).parse_world()


def test_non_finite_arithmetic_rejects_before_caller_state_mutation():
    arithmetic = WorldExecutor(Parser.from_file(ROOT / "arithmetic.fnl"))
    state = arithmetic.initial_state()
    state["Values"]["fraction"] = float("nan")
    before = dict(state["Values"])
    with pytest.raises(WorldExecutionError, match="Non-finite arithmetic operand"):
        arithmetic.advance(state, Event(0, "Values.Calc"))
    assert state["Values"] == before

    overflow = WorldExecutor(Parser.from_file(ROOT / "overflow.fnl"))
    state = overflow.initial_state()
    state["A"]["left"] = 1e308
    state["A"]["right"] = 1e308
    before = dict(state["A"])
    with pytest.raises(WorldExecutionError, match="Non-finite arithmetic result"):
        overflow.advance(state, Event(0, "A.Go"))
    assert state["A"] == before


def test_canonical_serialization_is_sorted_and_rejects_non_finite_numbers():
    assert _canonical({"z": 1, "a": {"z": 2, "b": 3.0}}) == (
        b'{"a":{"b":3.0,"z":2},"z":1}'
    )
    for nonfinite in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="Out of range float"):
            _canonical({"nested": {"value": nonfinite}})


@pytest.mark.parametrize("example", [
    "counter_world.fnl", "guarded_world.fnl", "payload_world.fnl",
    "stochastic_world.fnl", "event_chain_world.fnl", "warehouse_world.fnl",
])
def test_existing_valid_world_example_still_compiles(example):
    example_path = ROOT.parents[2] / "examples" / example
    assert isinstance(WorldExecutor(Parser.from_file(example_path)).initial_state(), dict)

"""H-P1 through H-P4: source-typed event records and deterministic delivery."""

import json
import math
import subprocess
import sys

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.runtime.world_executor import WorldExecutor, WorldExecutionError


WORLD = """world Ledger {
  entity Wallet {
    state balance: int = 0;
    state quota: int = 10;
    event Credit(amount: int);

    rule Receive on event Credit {
      transition balance = balance + payload.amount;
    }
    rule Seed on event Start {
      emit Credit(amount = quota) after 2;
      transition quota = 0;
    }
  }
}
"""


def parse_world(tmp_path, source=WORLD):
    source_file = tmp_path / "payload.fnl"
    source_file.write_text(source, encoding="utf-8")
    return Parser.from_file(source_file)


def test_payload_source_has_typed_ast_nodes(tmp_path):
    wallet = parse_world(tmp_path).declarations[0]
    assert [(item.name, item.type_name) for item in wallet.events[0].fields] == [
        ("amount", "int")
    ]
    transition = wallet.rules[0].transitions[0]
    assert transition.expr.right.kind == "payload_field"
    assert transition.expr.right.name == "amount"
    emission = wallet.rules[1].emissions[0]
    assert emission.event == "Credit"
    assert emission.arguments["amount"].kind == "reference"


def test_input_payload_is_read_by_rule(tmp_path):
    result = WorldExecutor(parse_world(tmp_path)).run(
        [Event(0, "Wallet.Credit", payload={"amount": 7})]
    )
    assert result.state["Wallet"] == {"balance": 7, "quota": 10}
    assert len(result.processed) == 1
    assert result.intents == ()


def test_source_emission_payload_uses_pre_event_snapshot(tmp_path):
    result = WorldExecutor(parse_world(tmp_path)).run([Event(3, "Wallet.Start")])
    assert [(item.name, item.time) for item in result.processed] == [
        ("Wallet.Start", 3),
        ("Wallet.Credit", 5),
    ]
    assert result.processed[1].payload == {"amount": 10}
    assert result.state["Wallet"] == {"balance": 10, "quota": 0}
    assert result.pending == ()


def test_delayed_payload_is_visible_as_pending_event(tmp_path):
    result = WorldExecutor(parse_world(tmp_path)).run(
        [Event(3, "Wallet.Start")], until=4
    )
    assert result.state["Wallet"] == {"balance": 0, "quota": 0}
    assert [(e.time, e.payload) for e in result.pending] == [(5, {"amount": 10})]


def test_payload_can_assign_boolean_directly(tmp_path):
    source = """world W { agent A {
      state active: bool = false;
      event Set(active: bool);
      rule R on event Set { transition active = payload.active; }
    } }"""
    result = WorldExecutor(parse_world(tmp_path, source)).run(
        [Event(0, "A.Set", payload={"active": True})]
    )
    assert result.state["A"]["active"] is True


@pytest.mark.parametrize(
    ("record", "error"),
    [
        (None, "Missing"),
        ({}, "Missing"),
        ({"amount": 1, "extra": 2}, "Unexpected"),
        ({"amount": True}, "Type mismatch"),
        ({"amount": 1.0}, "Type mismatch"),
        ({"amount": "1"}, "Type mismatch"),
        ({"amount": 1}, None),
        (["amount", 1], "mapping"),
    ],
)
def test_inbound_payload_shape_and_types(tmp_path, record, error):
    runner = WorldExecutor(parse_world(tmp_path))
    event = Event(0, "Wallet.Credit", payload=record)
    if error is None:
        assert runner.run([event]).state["Wallet"]["balance"] == 1
    else:
        with pytest.raises(WorldExecutionError, match=error):
            runner.run([event])


def test_false_guard_does_not_bypass_payload_validation(tmp_path):
    source = """world W { entity E {
      state n: int = 0;
      event Tick(amount: int);
      rule R on event Tick when (n > 10) {
        transition n = payload.amount;
      }
    } }"""
    runner = WorldExecutor(parse_world(tmp_path, source))
    with pytest.raises(WorldExecutionError, match="Missing"):
        runner.run([Event(0, "E.Tick")])
    result = runner.run([Event(0, "E.Tick", payload={"amount": 7})])
    assert result.state["E"]["n"] == 0
    assert len(result.processed) == 1


@pytest.mark.parametrize(
    ("declaration", "error"),
    [
        ("event Credit(amount: int, amount: int);", "Duplicate event field"),
        ("event Credit(amount: unknown);", "Unknown event field type"),
        ("event Credit(amount: int); event Credit(value: int);", "Duplicate event"),
    ],
)
def test_event_declaration_errors(tmp_path, declaration, error):
    source = f"""world W {{ entity E {{ {declaration}
      rule R on event Credit {{}}
    }} }}"""
    with pytest.raises(ValueError, match=error):
        parse_world(tmp_path, source)


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("transition balance = payload.missing;", "Unknown payload field"),
        ("transition balance = payload.amount + 1;", "Expected"),
        ("transition balance = payload.amount;", None),
        ("emit Credit after 1;", "Missing"),
        ("emit Credit(amount = true) after 1;", "Type mismatch"),
        ("emit Credit(extra = 1) after 1;", "Unexpected"),
        ("emit Credit(amount = 1, amount = 2) after 1;", "Duplicate"),
        ("emit Credit(amount = payload.bad) after 1;", "Unknown payload field"),
    ],
)
def test_static_references_and_emission_arguments(tmp_path, body, error):
    source = f"""world W {{ entity E {{
      state balance: int = 0;
      event Credit(amount: int);
      rule A on event Credit {{ {body} }}
    }} }}"""
    if error is None:
        assert parse_world(tmp_path, source)
    else:
        with pytest.raises((ParserError, ValueError), match=error):
            parse_world(tmp_path, source)


def test_zero_field_and_legacy_events_stay_compatible(tmp_path):
    source = """world W { entity E {
      state n: int = 0;
      event Ping();
      rule A on event Start { emit Ping after 0; }
      rule B on event Ping { transition n = n + 1; }
    } }"""
    result = WorldExecutor(parse_world(tmp_path, source)).run([Event(0, "E.Start")])
    assert result.state["E"]["n"] == 1
    assert len(result.processed) == 2
    assert result.processed[1].payload is None


def test_undeclared_event_rejects_untyped_payload(tmp_path):
    source = """world W { entity E { rule R on event Start {} } }"""
    runner = WorldExecutor(parse_world(tmp_path, source))
    with pytest.raises(WorldExecutionError, match="Unexpected"):
        runner.run([Event(0, "E.Start", payload={"anything": "x"})])


def test_emission_order_and_payload_replay(tmp_path):
    source = """world W { entity E {
      state total: int = 0;
      event Step(value: int);
      rule A on event Begin {
        emit Step(value = 1) after 0;
        emit Step(value = 2) after 0;
      }
      rule B on event Step { transition total = total + payload.value; }
    } }"""
    runner = WorldExecutor(parse_world(tmp_path, source))
    first = runner.run([Event(1, "E.Begin")], seed=9)
    second = runner.run([Event(1, "E.Begin")], seed=9)
    assert first == second
    assert [e.payload for e in first.processed[1:]] == [
        {"value": 1}, {"value": 2}
    ]
    assert first.state["E"]["total"] == 3


def test_cli_reads_typed_event_json_without_executing_code(tmp_path):
    source_file = tmp_path / "payload.fnl"
    source_file.write_text(WORLD, encoding="utf-8")
    event = {"name": "Wallet.Credit", "time": 0, "payload": {"amount": 8}}
    command = [
        sys.executable, "-m", "funnelscript.cli", "run-world",
        str(source_file), "--event", json.dumps(event),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"]["Wallet"]["balance"] == 8

    invalid = {**event, "payload": {"amount": "8"}}
    command[-1] = json.dumps(invalid)
    failed = subprocess.run(command, capture_output=True, text=True)
    assert failed.returncode != 0
    assert "Type mismatch" in failed.stderr


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_float_event_payload_must_be_finite(tmp_path, value):
    source = """world W { entity E {
      state balance: float = 0.0;
      event Deposit(amount: float);
      rule R on event Deposit { transition balance = payload.amount; }
    } }"""
    runner = WorldExecutor(parse_world(tmp_path, source))
    with pytest.raises(WorldExecutionError, match="finite"):
        runner.run([Event(0, "E.Deposit", payload={"amount": value})])


def test_cli_rejects_nonfinite_json_payload(tmp_path):
    source = """world W { entity E {
      state balance: float = 0.0;
      event Deposit(amount: float);
      rule R on event Deposit { transition balance = payload.amount; }
    } }"""
    source_file = tmp_path / "float.fnl"
    source_file.write_text(source, encoding="utf-8")
    payload = json.dumps({
        "name": "E.Deposit", "time": 0, "payload": {"amount": math.nan}
    })
    result = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "run-world",
         str(source_file), "--event", payload],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "finite" in result.stderr


def test_invalid_python_payload_keys_fail_with_world_error(tmp_path):
    runner = WorldExecutor(parse_world(tmp_path))
    event = Event(0, "Wallet.Credit", payload={"amount": 1, 7: 2, "other": 3})
    with pytest.raises(WorldExecutionError, match="Unexpected"):
        runner.run([event])


def test_outbound_payload_is_checked_before_entering_pending_calendar(tmp_path):
    source = """world W { entity E {
      state amount: float = 0.0;
      event Report(value: float);
      rule A on event Begin { emit Report(value = amount) after 5; }
      rule B on event Report {}
    } }"""
    world = parse_world(tmp_path, source)
    world.declarations[0].states[0].value = math.inf
    runner = WorldExecutor(world)
    with pytest.raises(WorldExecutionError, match="finite"):
        runner.run([Event(0, "E.Begin")], until=0)


def test_cli_malformed_event_does_not_echo_input_contents(tmp_path):
    source_file = tmp_path / "payload.fnl"
    source_file.write_text(WORLD, encoding="utf-8")
    marker = "PRIVATE_EVENT_VALUE_DO_NOT_LOG"
    result = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "run-world",
         str(source_file), "--event", f"bad:{marker}"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Invalid event" in result.stderr
    assert marker not in result.stderr


def test_cli_rejects_duplicate_json_event_fields(tmp_path):
    source_file = tmp_path / "payload.fnl"
    source_file.write_text(WORLD, encoding="utf-8")
    raw = '{"name":"Wallet.Credit","time":0,"payload":{"amount":1,"amount":9}}'
    result = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "run-world",
         str(source_file), "--event", raw],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Duplicate JSON" in result.stderr

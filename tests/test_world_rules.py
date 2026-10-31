"""H-R1 through H-R4: source rules lowered to the existing event machine."""

import json
import subprocess
import sys

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import LexerError


WORLD = """world Interactions {
  entity Counter {
    state a: int = 1;
    state b: int = 2;

    rule Exchange on event Swap {
      transition a = b;
      transition b = a;
    }
    rule Increase on event Pulse {
      transition a = a + 1;
    }
    rule Decrease on event Drop {
      transition b = b - 1;
    }
    rule Reset on event Clear {
      transition a = 0;
    }
  }
  agent Sensor {
    state active: bool = true;
    rule Stop on event Halt {
      transition active = false;
    }
  }
}
"""


def parse_source(tmp_path, source=WORLD):
    path = tmp_path / "rules.fnl"
    path.write_text(source, encoding="utf-8")
    return Parser.from_file(path)


def test_rule_source_parses_to_typed_ast(tmp_path):
    world = parse_source(tmp_path)
    counter = world.declarations[0]
    assert [rule.name for rule in counter.rules] == [
        "Exchange", "Increase", "Decrease", "Reset"
    ]
    assert counter.rules[0].event == "Swap"
    assert [t.target for t in counter.rules[0].transitions] == ["a", "b"]
    assert counter.rules[1].transitions[0].expr.kind == "binary"


def test_simultaneous_transitions_use_before_event_state(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path))
    before = executor.initial_state()
    after = executor.advance(before, Event(0, "Counter.Swap"))

    assert before["Counter"] == {"a": 1, "b": 2}
    assert after["Counter"] == {"a": 2, "b": 1}
    assert before is not after
    assert before["Counter"] is not after["Counter"]


def test_existing_other_entity_state_is_not_mutated(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path))
    before = executor.initial_state()
    after = executor.advance(before, Event(0, "Counter.Pulse"))

    assert before["Counter"]["a"] == 1
    assert after["Counter"]["a"] == 2
    assert before["Sensor"] is after["Sensor"]
    assert after["Sensor"]["active"] is True


def test_event_calendar_order_and_seeded_replay(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path))
    incoming = (
        Event(10, "Counter.Swap"),
        Event(1, "Counter.Pulse"),
        Event(3, "Counter.Drop"),
    )
    first = executor.run(incoming, seed=31)
    replay = executor.run(incoming, seed=31)

    assert first == replay
    assert [event.name for event in first.processed] == [
        "Counter.Pulse", "Counter.Drop", "Counter.Swap"
    ]
    assert first.state["Counter"] == {"a": 1, "b": 2}
    assert first.intents == ()


def test_agent_can_react_to_event(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path))
    result = executor.run([Event(1, "Sensor.Halt")], seed=1)

    assert result.state["Sensor"]["active"] is False


@pytest.mark.parametrize(
    ("fragment", "error"),
    [
        ("transition missing = 1;", "Unknown transition target"),
        ("transition a = missing;", "Unknown state reference"),
        ("transition a = true;", "Type mismatch"),
        ("transition a = a + 1.0;", "Type mismatch"),
        ("transition a = a + true;", "numeric"),
        ("transition a = b + 1.0;", "Type mismatch"),
    ],
)
def test_typechecker_rejects_invalid_transition(tmp_path, fragment, error):
    src = f"world W {{ entity Box {{ state a: int = 1; state b: int = 2; rule R on event Go {{ {fragment} }} }} }}"
    with pytest.raises(ValueError, match=error):
        parse_source(tmp_path, src)


@pytest.mark.parametrize(
    ("fragment", "error"),
    [
        (
            "rule First on event Go { transition a = 1; } rule Second on event Go { transition a = 2; }",
            "Duplicate event handler",
        ),
        (
            "rule Same on event Go { transition a = 1; } rule Same on event Stop { transition a = 2; }",
            "Duplicate rule",
        ),
        (
            "rule First on event Go { transition a = 1; transition a = 2; }",
            "Duplicate transition target",
        ),
    ],
)
def test_checker_rejects_ambiguous_handlers(tmp_path, fragment, error):
    src = f"world W {{ entity Box {{ state a: int = 1; {fragment} }} }}"
    with pytest.raises(ValueError, match=error):
        parse_source(tmp_path, src)


@pytest.mark.parametrize(
    "source",
    [
        "world W { entity E { state n: int = 1; rule R event Go { transition n = 2; } } }",
        "world W { entity E { state n: int = 1; rule R on event Go { transition n = n * 2; } } }",
        "world W { entity E { state n: int = 1; rule R on event Go { transition n = 2 } } }",
    ],
)
def test_parser_rejects_invalid_rule_syntax(tmp_path, source):
    with pytest.raises((LexerError, ParserError)):
        parse_source(tmp_path, source)


def test_unknown_qualified_event_fails_explicitly(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor, WorldExecutionError

    executor = WorldExecutor(parse_source(tmp_path))
    with pytest.raises(WorldExecutionError, match="Unknown event"):
        executor.run([Event(0, "Counter.Unknown")], seed=0)
    with pytest.raises(WorldExecutionError, match="Unknown event"):
        executor.run([Event(0, "Pulse")], seed=0)


def test_world_runner_respects_event_processing_limit(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path))
    events = [Event(0, "Counter.Pulse"), Event(1, "Counter.Pulse")]
    with pytest.raises(RuntimeError, match="max_events"):
        executor.run(events, seed=0, max_events=1)


def test_cli_runs_rules_from_fnl_file(tmp_path):
    path = tmp_path / "counter.fnl"
    path.write_text(WORLD, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, "-m", "funnelscript.cli", "run-world", str(path),
            "--event", "Counter.Swap@0", "--event", "Counter.Pulse@1",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["state"]["Counter"] == {"a": 3, "b": 1}
    assert data["processed_events"] == 2


def test_legacy_strategy_remains_unsupported_for_world_runner():
    result = subprocess.run(
        [
            sys.executable, "-m", "funnelscript.cli", "run-world",
            "examples/black_friday_2026.fnl", "--event", "Counter.Pulse@0",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0

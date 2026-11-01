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


def test_executor_isolates_checked_world_from_caller_mutations(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    parsed_world = parse_source(tmp_path)
    executor = WorldExecutor(parsed_world)
    parsed_world.declarations[0].states[0].value = 99
    parsed_world.declarations[0].rules[1].transitions[0].expr.right.value = 900

    result = executor.run([Event(0, "Counter.Pulse")])
    assert result.state["Counter"]["a"] == 2


def arithmetic_world(expression, *, result_type="float", event_fields=""):
    return f"""world Arithmetic {{
      entity Math {{
        state n: int = 12;
        state d: int = 3;
        state x: float = 12.0;
        state y: float = 3.0;
        state result: {result_type} = {"0" if result_type == "int" else "0.0"};
        event Calculate({event_fields});
        rule Calculate on event Calculate {{ transition result = {expression}; }}
      }}
    }}"""


@pytest.mark.parametrize(
    ("expression", "result_type", "expected"),
    [
        ("n * d", "int", 36),
        ("n * -2", "int", -24),
        ("n * 0", "int", 0),
        ("n / d", "float", 4.0),
        ("n / -3", "float", -4.0),
        ("x * y", "float", 36.0),
        ("x / y", "float", 4.0),
        ("x / -3.0", "float", -4.0),
        ("x + y", "float", 15.0),
        ("x - y", "float", 9.0),
    ],
)
def test_narrow_arithmetic_result_matches_static_type(tmp_path, expression, result_type, expected):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world(expression, result_type=result_type)))
    initial = executor.initial_state()
    updated = executor.advance(initial, Event(0, "Math.Calculate"))
    assert updated["Math"]["result"] == expected
    assert type(updated["Math"]["result"]).__name__ == result_type


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("n * payload.factor", 36), ("n / payload.factor", 4.0),
     ("n + d", 15), ("n - d", 9)],
)
def test_arithmetic_accepts_typed_dynamic_right_operands(tmp_path, expression, expected):
    from funnelscript.runtime.world_executor import WorldExecutor

    result_type = "float" if "/" in expression else "int"
    schema = "factor: int" if "payload" in expression else ""
    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world(expression, result_type=result_type, event_fields=schema)))
    payload = {"factor": 3} if schema else None
    updated = executor.advance(executor.initial_state(), Event(0, "Math.Calculate", payload=payload))
    assert updated["Math"]["result"] == expected


@pytest.mark.parametrize(
    ("expression", "result_type", "message"),
    [
        ("n * 1.0", "int", "Type mismatch in arithmetic"),
        ("x / n", "float", "Type mismatch in arithmetic"),
        ("n / d", "int", "Type mismatch assigning"),
        ("n * true", "int", "numeric"),
        ("n * missing", "int", "Unknown state reference"),
        ("n / payload.missing", "float", "Unknown payload field"),
        ("n * \"bad\"", "int", "numeric"),
        ("n / 0", "float", "Division by literal zero"),
        ("x / -0.0", "float", "Division by literal zero"),
    ],
)
def test_arithmetic_rejects_invalid_types_references_and_static_zero(tmp_path, expression, result_type, message):
    with pytest.raises(ValueError, match=message):
        parse_source(tmp_path, arithmetic_world(expression, result_type=result_type))


@pytest.mark.parametrize("expression", ["n / d", "n / payload.factor", "x / y"])
def test_dynamic_division_by_zero_is_controlled_and_atomic(tmp_path, expression):
    from funnelscript.runtime.world_executor import WorldExecutionError, WorldExecutor

    schema = "factor: int" if "payload" in expression else ""
    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world(expression, event_fields=schema)))
    before = executor.initial_state()
    state = {**before, "Math": {**before["Math"]}}
    if expression == "n / d":
        state["Math"]["d"] = 0
    elif expression == "x / y":
        state["Math"]["y"] = 0.0
    payload = {"factor": 0} if schema else None
    with pytest.raises(WorldExecutionError, match="Division by zero"):
        executor.advance(state, Event(0, "Math.Calculate", payload=payload))
    assert state["Math"]["result"] == 0.0
    assert before["Math"]["d"] == 3


def test_division_by_negative_zero_from_payload_is_controlled(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutionError, WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world("x / payload.divisor", event_fields="divisor: float")))
    with pytest.raises(WorldExecutionError, match="Division by zero"):
        executor.advance(executor.initial_state(), Event(0, "Math.Calculate", payload={"divisor": -0.0}))


@pytest.mark.parametrize("expression", ["x * y", "x + y", "x / y"])
def test_arithmetic_rejects_runtime_nonfinite_result(tmp_path, expression):
    from funnelscript.runtime.world_executor import WorldExecutionError, WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world(expression)))
    before = executor.initial_state()
    state = {**before, "Math": {**before["Math"], "x": 1.7e308, "y": 2.0 if "*" in expression else 1.7e308 if "+" in expression else 1e-308}}
    with pytest.raises(WorldExecutionError, match="Non-finite arithmetic result"):
        executor.advance(state, Event(0, "Math.Calculate"))
    assert state["Math"]["result"] == 0.0


def test_integer_division_float_conversion_overflow_is_controlled(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutionError, WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world("n / d")))
    state = executor.initial_state()
    state["Math"]["n"] = 10 ** 400
    with pytest.raises(WorldExecutionError, match="Non-finite arithmetic result"):
        executor.advance(state, Event(0, "Math.Calculate"))


def test_rejects_nonfinite_float_literal_in_arithmetic(tmp_path):
    enormous = "9" * 400 + ".0"
    with pytest.raises(ValueError, match="Non-finite float literal"):
        parse_source(tmp_path, arithmetic_world(f"x * {enormous}"))


def test_slash_comment_precedence_and_binary_tokenization(tmp_path):
    from funnelscript.tokens import Lexer, TokenType
    from funnelscript.runtime.world_executor import WorldExecutor

    source = arithmetic_world("n / d")
    source = source.replace("state n: int = 12;", "state n: int = 12; // / * ignored\n")
    types = [token.type for token in Lexer(source).tokenize()]
    assert types.count(TokenType.SLASH) == 1
    assert TokenType.STAR not in types
    result = WorldExecutor(parse_source(tmp_path, source)).run([Event(0, "Math.Calculate")])
    assert result.state["Math"]["result"] == 4.0


@pytest.mark.parametrize("expression", ["n *", "n + (d", "n / )"])
def test_malformed_arithmetic_is_rejected(tmp_path, expression):
    with pytest.raises(ParserError):
        parse_source(tmp_path, arithmetic_world(expression))


@pytest.mark.parametrize(("expression", "result_type", "expected"), [
    ("n * d + 2", "int", 38), ("n + d * 2", "int", 18),
    ("n / (d)", "float", 4.0),
])
def test_newly_supported_arithmetic_is_semantically_checked(tmp_path, expression, result_type, expected):
    from funnelscript.runtime.world_executor import WorldExecutor
    model = WorldExecutor(parse_source(tmp_path, arithmetic_world(expression, result_type=result_type)))
    result = model.run([Event(0, "Math.Calculate")])
    assert result.state["Math"]["result"] == expected


@pytest.mark.parametrize("expression", ["n / d / 2", "n / sample uniform(1.0, 2.0)"])
def test_chained_arithmetic_does_not_silently_coerce_mixed_numeric_types(tmp_path, expression):
    from funnelscript.compiler.world_ast import WorldTypeError
    with pytest.raises(WorldTypeError, match="Type mismatch"):
        parse_source(tmp_path, arithmetic_world(expression))


def test_arithmetic_retains_pre_event_snapshot_and_seed_replay(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    source = """world W { entity E {
      state n: int = 2;
      state doubled: int = 0;
      state sampled: float = 0.0;
      rule R on event Go {
        transition n = n * 3;
        transition doubled = n * 2;
        transition sampled = sample uniform(0.0, 1.0);
      }
    } }"""
    executor = WorldExecutor(parse_source(tmp_path, source))
    first = executor.run([Event(0, "E.Go"), Event(1, "E.Go")], seed=81)
    second = executor.run([Event(0, "E.Go"), Event(1, "E.Go")], seed=81)
    assert first == second
    assert first.state["E"]["n"] == 18
    assert first.state["E"]["doubled"] == 12


def test_runtime_rejects_nonfinite_float_operand_before_arithmetic(tmp_path):
    import math
    from funnelscript.runtime.world_executor import WorldExecutionError, WorldExecutor

    executor = WorldExecutor(parse_source(tmp_path, arithmetic_world("x * y")))
    state = executor.initial_state()
    state["Math"]["x"] = math.inf
    with pytest.raises(WorldExecutionError, match="Non-finite arithmetic operand"):
        executor.advance(state, Event(0, "Math.Calculate"))


def test_arithmetic_expression_in_local_emitted_event_uses_pre_event_values(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    source = """world W { entity E {
      state n: int = 8;
      state divisor: int = 2;
      state result: float = 0.0;
      event Answer(value: float);
      rule Begin on event Start {
        transition n = n * 2;
        emit Answer(value = n / divisor) after 1;
      }
      rule Finish on event Answer { transition result = payload.value; }
    } }"""
    executor = WorldExecutor(parse_source(tmp_path, source))
    output = executor.run([Event(0, "E.Start")], seed=19)
    assert output.state["E"]["n"] == 16
    assert output.state["E"]["result"] == 4.0
    assert [event.name for event in output.processed] == ["E.Start", "E.Answer"]


def test_cli_reports_dynamic_division_by_zero_as_world_error(tmp_path):
    path = tmp_path / "arithmetic.fnl"
    path.write_text(arithmetic_world("n / d"), encoding="utf-8")
    path.write_text(arithmetic_world("n / d").replace("state d: int = 3;", "state d: int = 0;"), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "run-world", str(path),
         "--event", "Math.Calculate@0"], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Division by zero" in result.stderr
    assert "ZeroDivisionError" not in result.stderr

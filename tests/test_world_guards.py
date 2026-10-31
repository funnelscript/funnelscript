"""H-G1 through H-G4: typed guards control World transitions and emissions."""

import json
import subprocess
import sys

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import LexerError


GUARDED_WORLD = """world BoundedFlow {
  agent Counter {
    state value: int = 0;
    rule Advance on event Tick when (value < 3) {
      transition value = value + 1;
      emit Tick after 1;
    }
  }
}
"""


def parse_world(tmp_path, source=GUARDED_WORLD):
    path = tmp_path / "guarded.fnl"
    path.write_text(source, encoding="utf-8")
    return Parser.from_file(path)


def test_guard_is_typed_ast_node(tmp_path):
    guard = parse_world(tmp_path).declarations[0].rules[0].guard
    assert guard is not None
    assert guard.field == "value"
    assert guard.operator == "<"
    assert guard.value == 3


def test_guarded_reaction_chain_stops_without_exhausting_event_cap(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    executor = WorldExecutor(parse_world(tmp_path))
    result = executor.run([Event(0, "Counter.Tick")], max_events=5)
    assert [event.time for event in result.processed] == [0, 1, 2, 3]
    assert result.state["Counter"]["value"] == 3
    assert result.pending == ()
    assert result.intents == ()


def test_false_guard_skips_transition_and_emit(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    src = GUARDED_WORLD.replace("state value: int = 0;", "state value: int = 3;")
    result = WorldExecutor(parse_world(tmp_path, src)).run([Event(2, "Counter.Tick")])
    assert result.state["Counter"]["value"] == 3
    assert len(result.processed) == 1
    assert result.pending == ()
    assert result.intents == ()


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        ("==", "3", True),
        ("!=", "3", False),
        (">", "2", True),
        (">=", "3", True),
        ("<", "4", True),
        ("<=", "2", False),
    ],
)
def test_numeric_comparison_operators(tmp_path, operator, value, expected):
    from funnelscript.runtime.world_executor import WorldExecutor

    src = f"""world W {{ entity E {{
      state n: int = 3;
      state hit: bool = false;
      rule R on event Go when (n {operator} {value}) {{
        transition hit = true;
      }}
    }} }}"""
    result = WorldExecutor(parse_world(tmp_path, src)).run([Event(0, "E.Go")])
    assert result.state["E"]["hit"] is expected


def test_boolean_and_string_equality_guards(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    src = """world W { entity E {
      state ready: bool = true;
      state name: string = "active";
      state count: int = 0;
      rule A on event Start when (ready == true) { transition count = count + 1; }
      rule B on event Finish when (name != "done") { transition count = count + 1; }
    } }"""
    result = WorldExecutor(parse_world(tmp_path, src)).run(
        [Event(0, "E.Start"), Event(1, "E.Finish")]
    )
    assert result.state["E"]["count"] == 2


@pytest.mark.parametrize(
    ("guard", "message"),
    [
        ("missing == 3", "Unknown guard field"),
        ("n == 3.0", "Type mismatch"),
        ("n == true", "Type mismatch"),
        ("active < true", "numeric"),
        ('label > "a"', "numeric"),
    ],
)
def test_typechecker_rejects_invalid_guard(tmp_path, guard, message):
    src = f"""world W {{ entity E {{
      state n: int = 3;
      state active: bool = true;
      state label: string = "x";
      rule R on event Go when ({guard}) {{ transition n = 1; }}
    }} }}"""
    with pytest.raises(ValueError, match=message):
        parse_world(tmp_path, src)


@pytest.mark.parametrize(
    "guard",
    ["when n < 3", "when (n < )", "when (n <> 3)", "when (n < 3) when (n > 0)"],
)
def test_malformed_guards_are_rejected(tmp_path, guard):
    src = f"""world W {{ entity E {{
      state n: int = 3;
      rule R on event Go {guard} {{ transition n = 1; }}
    }} }}"""
    with pytest.raises((LexerError, ParserError, ValueError)):
        parse_world(tmp_path, src)


def test_cli_executes_guarded_world_from_source(tmp_path):
    path = tmp_path / "guarded.fnl"
    path.write_text(GUARDED_WORLD, encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable, "-m", "funnelscript.cli", "run-world", str(path),
            "--event", "Counter.Tick@0", "--max-events", "5",
        ],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    body = json.loads(completed.stdout)
    assert body["state"]["Counter"]["value"] == 3
    assert body["processed_events"] == 4

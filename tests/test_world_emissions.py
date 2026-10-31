"""H-E1 to H-E4: emitted World events use the existing ordered event calendar."""

import json
import subprocess
import sys

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError


WORLD = """world Cascade {
  entity Worker {
    state count: int = 0;
    state active: bool = false;

    rule Begin on event Start {
      emit Tick after 2;
      transition active = true;
    }
    rule Advance on event Tick {
      transition count = count + 1;
    }
  }
}
"""


def parse_world(tmp_path, source=WORLD):
    path = tmp_path / "cascade.fnl"
    path.write_text(source, encoding="utf-8")
    return Parser.from_file(path)


def test_emit_parses_with_forward_rule_reference(tmp_path):
    ast = parse_world(tmp_path)
    begin = ast.declarations[0].rules[0]
    assert begin.event == "Start"
    assert len(begin.emissions) == 1
    assert begin.emissions[0].event == "Tick"
    assert begin.emissions[0].delay == 2


def test_emitted_event_runs_at_relative_time_on_same_calendar(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    result = WorldExecutor(parse_world(tmp_path)).run([Event(3, "Worker.Start")])
    assert [(event.time, event.name) for event in result.processed] == [
        (3, "Worker.Start"),
        (5, "Worker.Tick"),
    ]
    assert result.state["Worker"] == {"count": 1, "active": True}
    assert result.intents == ()


def test_emissions_preserve_source_order_for_same_time(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    source = """world W { entity E {
      state x: int = 0;
      rule Begin on event Start {
        emit First after 0;
        transition x = 0;
        emit Second after 0;
      }
      rule A on event First { transition x = x + 1; }
      rule B on event Second { transition x = x + 10; }
    } }"""
    executor = WorldExecutor(parse_world(tmp_path, source))
    first = executor.run([Event(0, "E.Start")], seed=17)
    replay = executor.run([Event(0, "E.Start")], seed=17)
    assert first == replay
    assert [event.name for event in first.processed] == [
        "E.Start", "E.First", "E.Second"
    ]
    assert first.state["E"]["x"] == 11


def test_horizon_leaves_emitted_events_pending(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    result = WorldExecutor(parse_world(tmp_path)).run(
        [Event(3, "Worker.Start")], until=4
    )
    assert [event.name for event in result.processed] == ["Worker.Start"]
    assert [(e.time, e.name) for e in result.pending] == [(5, "Worker.Tick")]
    assert result.state["Worker"] == {"count": 0, "active": True}


def test_zero_delay_recursive_emission_is_bounded(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    source = """world W { agent A {
      state count: int = 0;
      rule Repeat on event Loop {
        transition count = count + 1;
        emit Loop after 0;
      }
    } }"""
    executor = WorldExecutor(parse_world(tmp_path, source))
    with pytest.raises(RuntimeError, match="max_events"):
        executor.run([Event(0, "A.Loop")], max_events=3)


@pytest.mark.parametrize(
    ("bad_body", "message"),
    [
        ("emit Missing after 1;", "Unknown emitted event"),
        ("emit Tick after -1;", "non-negative"),
        ('emit Tick after "2";', "numeric"),
        ("emit Tick after true;", "numeric"),
    ],
)
def test_invalid_emissions_fail_at_typecheck(tmp_path, bad_body, message):
    source = f"""world W {{ entity E {{
      state n: int = 0;
      rule StartRule on event Start {{ {bad_body} }}
      rule TickRule on event Tick {{ transition n = 1; }}
    }} }}"""
    with pytest.raises(ValueError, match=message):
        parse_world(tmp_path, source)


@pytest.mark.parametrize(
    "bad_emit",
    ["emit Tick 2;", "emit Tick after 2", "emit after 2;"],
)
def test_invalid_emit_syntax_is_rejected(tmp_path, bad_emit):
    source = f"""world W {{ entity E {{
      rule A on event Start {{ {bad_emit} }}
      rule B on event Tick {{}}
    }} }}"""
    with pytest.raises((ParserError, ValueError)):
        parse_world(tmp_path, source)


def test_cli_processes_emitted_events_from_real_file(tmp_path):
    path = tmp_path / "cascade.fnl"
    path.write_text(WORLD, encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "funnelscript.cli",
            "run-world",
            str(path),
            "--event",
            "Worker.Start@3",
            "--seed",
            "11",
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    body = json.loads(completed.stdout)
    assert body["processed_events"] == 2
    assert body["state"]["Worker"] == {"count": 1, "active": True}


def test_zero_delay_emit_inherits_nonzero_event_priority(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    source = """world W { entity E {
      state n: int = 0;
      rule Begin on event Start { emit Next after 0; }
      rule End on event Next { transition n = n + 1; }
    } }"""
    result = WorldExecutor(parse_world(tmp_path, source)).run(
        [Event(1, "E.Start", priority=7)]
    )
    assert [(e.name, e.priority) for e in result.processed] == [
        ("E.Start", 7), ("E.Next", 7)
    ]
    assert result.state["E"]["n"] == 1


def test_fractional_delay_uses_world_time_units(tmp_path):
    from funnelscript.runtime.world_executor import WorldExecutor

    source = WORLD.replace("emit Tick after 2;", "emit Tick after 0.25;")
    result = WorldExecutor(parse_world(tmp_path, source)).run(
        [Event(3, "Worker.Start")]
    )
    assert [(e.time, e.name) for e in result.processed] == [
        (3, "Worker.Start"), (3.25, "Worker.Tick")
    ]

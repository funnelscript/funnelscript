"""Proof obligations for the source-located World hygiene analyzer.

Research anchor: compiler control-flow and data-flow analysis.
Hypothesis: immutable-state contradiction implies a handler cannot execute,
and unhandled event declarations cannot dispatch to a World rule.
Invariant: every warning is anchored to its actual originating source span;
external-root handlers and guards on writable state remain valid.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from funnelscript.cli import check_command
from funnelscript.compiler.world_ast import WorldAST
from funnelscript.compiler.world_lint import WorldLinter
from funnelscript.parser import Parser

WORLD = """world Analysis {
  entity Counter {
    state count: int = 0;
    state enabled: bool = false;
    state limit: int = 10;
    event Data(used: int, ignored: int);
    event Forgotten(unseen: int);
    rule Apply on event Data {
      transition count = count + payload.used;
    }
    rule Disabled on event Shutdown when (enabled == true) {
      transition count = 0;
    }
    rule Open on event Open when (count >= 0) {
      transition count = count + 1;
    }
    rule Noop on event Idle {
    }
  }
}
"""


def _parse(tmp_path: Path, body: str = WORLD) -> tuple[WorldAST, Path]:
    file = tmp_path / "hygiene.fnls"
    file.write_text(body, encoding="utf-8")
    ast = Parser.from_file(file)
    assert isinstance(ast, WorldAST)
    return ast, file


def test_detects_unhandled_event_and_anchors_event_source(tmp_path):
    ast, file = _parse(tmp_path)
    findings = WorldLinter(ast).lint()
    dead = [item for item in findings if item.code == "FNL-W301"]
    assert len(dead) == 1
    finding = dead[0]
    assert finding.span is not None
    assert finding.span.file == str(file.resolve())
    assert finding.span.start_line == 7
    assert finding.span.start_col == 5
    assert finding.severity == "warning"
    assert finding.subject == "Counter.Forgotten"
    assert "never handled" in finding.message
    assert "rule" in finding.hint


def test_unused_payload_field_warns_only_where_not_read(tmp_path):
    ast, _ = _parse(tmp_path)
    diagnostics = [
        item for item in WorldLinter(ast).lint() if item.code == "FNL-W302"
    ]
    assert len(diagnostics) == 1
    assert diagnostics[0].subject == "Counter.Data.ignored"
    assert diagnostics[0].span.start_line == 6
    assert diagnostics[0].span.start_col > 10
    assert "ignored" in diagnostics[0].message


def test_static_invariant_marks_guard_with_immutable_false_state_unreachable(
    tmp_path,
):
    ast, _ = _parse(tmp_path)
    diagnostics = [
        item for item in WorldLinter(ast).lint() if item.code == "FNL-W303"
    ]
    assert len(diagnostics) == 1
    assert diagnostics[0].subject == "Counter.Disabled"
    assert diagnostics[0].span.start_line == 11
    assert "never changes" in diagnostics[0].message


def test_noop_handler_is_reported_separately_from_unreachable_guard(tmp_path):
    ast, _ = _parse(tmp_path)
    diagnostics = [
        item for item in WorldLinter(ast).lint() if item.code == "FNL-W304"
    ]
    assert len(diagnostics) == 1
    assert diagnostics[0].subject == "Counter.Noop"
    assert diagnostics[0].span.start_line == 17


def test_deterministic_order_and_readonly_repeatability(tmp_path):
    ast, _ = _parse(tmp_path)
    before = ast.model_dump_json()
    analyzer = WorldLinter(ast)
    first = analyzer.lint()
    second = analyzer.lint()
    assert first == second
    assert tuple(item.code for item in first) == (
        "FNL-W301", "FNL-W302", "FNL-W303", "FNL-W304",
    )
    assert ast.model_dump_json() == before


def test_diagnostic_renderer_includes_exact_source_and_hints(tmp_path):
    ast, path = _parse(tmp_path)
    unreachable = next(
        item for item in WorldLinter(ast).lint()
        if item.code == "FNL-W303"
    )
    detail = unreachable.render()
    assert str(path.resolve()) in detail
    assert "FNL-W303" in detail
    assert "line 11" in detail
    assert "column 5" in detail
    assert "when (enabled == true)" in detail
    assert "^" in detail
    assert "Hint:" in detail
    assert "Traceback" not in detail


def test_mutable_guard_state_must_not_be_classified_unreachable(tmp_path):
    src = """world GuardMutable {
  entity Holder {
    state active: bool = false;
    rule Arm on event Start {
      transition active = true;
    }
    rule Trigger on event Do when (active == true) {
      transition active = false;
    }
  }
}
"""
    ast, _ = _parse(tmp_path, src)
    assert all(item.code != "FNL-W303" for item in WorldLinter(ast).lint())


def test_externally_injected_rule_does_not_need_an_emitter(tmp_path):
    src = """world External {
  entity Sink {
    state value: int = 0;
    rule Receive on event Input {
      transition value = value + 1;
    }
  }
}
"""
    ast, _ = _parse(tmp_path, src)
    assert WorldLinter(ast).lint() == ()


def test_guard_that_matches_initial_state_is_reachable_without_writer(tmp_path):
    src = """world TrueGuard {
  entity Sink {
    state ready: bool = true;
    rule Receive on event Input when (ready == true) {
      transition ready = true;
    }
  }
}
"""
    ast, _ = _parse(tmp_path, src)
    assert all(item.code != "FNL-W303" for item in WorldLinter(ast).lint())


def test_nested_payload_access_and_emissions_count_as_field_usage(tmp_path):
    src = """world Usage {
  entity Sink {
    state total: int = 0;
    event Apply(first: int, second: int);
    event Follow(amount: int);
    rule ApplyValue on event Apply {
      transition total = total + (payload.first + payload.second);
      emit Follow(amount = payload.second) after 1;
    }
    rule FollowValue on event Follow {
      transition total = total + payload.amount;
    }
  }
}
"""
    ast, _ = _parse(tmp_path, src)
    assert all(item.code != "FNL-W302" for item in WorldLinter(ast).lint())


def test_imported_module_warning_points_to_original_file(tmp_path):
    module = tmp_path / "shared.fnls"
    entry = tmp_path / "entry.fnls"
    module.write_text(
        "world Shared {\n"
        "  entity E {\n"
        "    event Unhandled(item: int);\n"
        "  }\n"
        "}\n", encoding="utf-8",
    )
    entry.write_text(
        'world Root {\n  import "shared.fnls" as Imported;\n}\n',
        encoding="utf-8",
    )
    ast = Parser.from_file(entry)
    warnings = WorldLinter(ast).lint()
    assert len(warnings) == 1
    assert warnings[0].subject == "Imported.Unhandled"
    assert warnings[0].span.file == str(module.resolve())
    assert warnings[0].span.start_line == 3


def test_cli_world_check_reports_advisory_warnings_without_failure(
    tmp_path, capsys,
):
    _, file = _parse(tmp_path)
    assert check_command(str(file)) == 0
    output = capsys.readouterr().out
    for code in ("FNL-W301", "FNL-W302", "FNL-W303", "FNL-W304"):
        assert code in output
    assert "hygiene.fnls" in output or "hygiene.fnls" in "".join(output.split())


def test_cli_world_check_quiet_stays_silent(tmp_path, capsys):
    _, file = _parse(tmp_path)
    assert check_command(str(file), quiet=True) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "fixture",
    (
        "examples/counter_world.fnls",
        "tests/fixtures/world-conformance/typed.fnls",
        "tests/fixtures/world-conformance/ordering.fnls",
        "tests/fixtures/population-reference/identity-rng.fnls",
    ),
)
def test_existing_valid_world_examples_do_not_trigger_hygiene_diagnostics(
    fixture,
):
    path = Path(__file__).resolve().parents[2] / fixture
    ast = Parser.from_file(path)
    assert WorldLinter(ast).lint() == ()


def test_unused_constant_state_is_not_misclassified_as_dead_rule(tmp_path):
    src = """world Constants {
  entity Holder {
    state tax: float = 0.5;
    state total: float = 0.0;
    rule Process on event Input {
      transition total = total + tax;
    }
  }
}
"""
    ast, _ = _parse(tmp_path, src)
    assert WorldLinter(ast).lint() == ()


def test_multiple_diagnostics_keep_distinct_identical_names_in_two_owners(tmp_path):
    src = """world Multi {
  entity First {
    event Idle(amount: int);
  }
  agent Second {
    event Idle(amount: int);
  }
}
"""
    ast, _ = _parse(tmp_path, src)
    warnings = WorldLinter(ast).lint()
    assert tuple(item.subject for item in warnings) == (
        "First.Idle", "Second.Idle",
    )
    assert all(item.code == "FNL-W301" for item in warnings)


def test_missing_spans_on_programmatically_constructed_ast_remain_safe(tmp_path):
    from funnelscript.compiler.world_ast import (
        EntityDefinition,
        EventDefinition,
        WorldAST,
    )

    ast = WorldAST(
        name="Manual",
        declarations=[EntityDefinition(name="E", events=[EventDefinition(name="A")])],
    )
    findings = WorldLinter(ast).lint()
    assert len(findings) == 1
    assert findings[0].span is None
    assert "FNL-W301" in findings[0].render()
    assert "Hint:" in findings[0].render()

"""CLI validation diagnostics must reveal actual source facts, never invented spans.

Research anchor: structured compiler errors and JSON Schema / Pydantic location paths.
Falsifiable hypothesis: invalid JSON syntax yields an exact caret; schema validation
yields an accurate field path and bounded, actionable diagnostic without raw input.
Invariant: every reported line/column is grounded in the JSON decoder's offset;
Pydantic field paths are typed locators, not fabricated physical source spans.
"""

import json
from pathlib import Path

import pytest

from funnelscript.cli import check_command, run_world_command, simulate_command
from funnelscript.compiler.diagnostics import render_compiler_error
from funnelscript.compiler.world_ast import WorldTypeError
from funnelscript.models import StrategyAST
from funnelscript.parser import ParserError


def test_cli_validation_error_has_code_and_structural_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    invalid = {
        "strategy_name": "Invalid",
        "entities": {
            "budgets": {"total_budget": 10},
            "audiences": [{"id": "A", "estimated_size": 0}],
            "touchpoints": [{"id": "T", "type": "paid_traffic", "base_cpc": -1}],
        },
    }
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    assert check_command(str(path)) == 1
    rendered = capsys.readouterr().out
    assert "FNL-T202" in rendered
    assert "entities.audiences[0].estimated_size" in rendered
    assert "entities.touchpoints[0].base_cpc" in rendered
    assert "Hint:" in rendered
    assert "input_value=" not in rendered
    assert "pydantic.dev" not in rendered
    assert "Traceback" not in rendered
    assert "line 1, column" not in rendered


def test_json_syntax_error_has_real_line_column_caret(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    path = tmp_path / "invalid.json"
    path.write_text('{\n "strategy_name": "Bad",\n "entities": BAD\n}\n')
    assert check_command(str(path)) == 1
    rendered = capsys.readouterr().out
    assert "FNL-E103" in rendered
    assert "invalid.json" in rendered
    assert "line 3, column 14" in rendered
    assert '"entities": BAD' in rendered
    assert "^" in rendered
    assert "Hint:" in rendered
    assert "Traceback" not in rendered


def test_json_type_failure_is_bounded_and_does_not_dump_values():
    invalid = {
        "strategy_name": "Bad",
        "entities": {
            "budgets": {"total_budget": 5},
            "audiences": [
                {"id": f"test-{i}", "estimated_size": 0} for i in range(40)
            ],
            "touchpoints": [],
        },
    }
    with pytest.raises(Exception) as captured:
        StrategyAST.model_validate(invalid)
    output = render_compiler_error(captured.value, "invalid.json")
    assert "FNL-T202" in output
    assert "entities.audiences[0].estimated_size" in output
    assert "entities.audiences[31].estimated_size" in output
    assert "entities.audiences[32].estimated_size" not in output
    assert "8 further validation errors omitted" in output
    assert len(output) < 7000
    assert "input_value=" not in output
    assert "pydantic.dev" not in output


def test_diagnostic_renderer_keeps_existing_semantic_and_syntax_messages():
    for error in [WorldTypeError("semantic failure"), ParserError("syntax failure")]:
        assert render_compiler_error(error, "input.fnl") == str(error)


def test_simulate_reuses_validation_diagnostic_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    path = tmp_path / "wrong.json"
    path.write_text('{"strategy_name":"Example","entities":{"budgets":{"total_budget":0},"audiences":[],"touchpoints":[]}}')
    assert simulate_command(str(path), trials=1, agents=1) == 1
    rendered = capsys.readouterr().out
    assert "FNL-T202" in rendered
    assert "Hint:" in rendered
    assert "Traceback" not in rendered


def test_json_end_of_file_reports_decoder_position(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    path = tmp_path / "incomplete.json"
    path.write_text("{", encoding="utf-8")
    assert check_command(str(path)) == 1
    rendered = capsys.readouterr().out
    assert "FNL-E103" in rendered
    assert "line 1, column 2" in rendered
    assert "^" in rendered
    assert "Hint:" in rendered


def test_pydantic_root_validator_path_has_no_invented_source_span():
    invalid = {
        "strategy_name": "X",
        "entities": {
            "budgets": {"total_budget": 0},
            "audiences": [],
            "touchpoints": [],
        },
    }
    with pytest.raises(Exception) as captured:
        StrategyAST.model_validate(invalid)
    rendered = render_compiler_error(captured.value, "root.json")
    assert "FNL-T202 root.json" in rendered
    assert "<root>:" in rendered
    assert "line 1, column" not in rendered
    assert "Hint:" in rendered


def test_run_world_strategy_type_mismatch_is_caught_without_traceback(
    capsys: pytest.CaptureFixture[str],
):
    assert run_world_command("examples/black_friday_2026.json", []) == 1
    output = capsys.readouterr()
    assert "run-world requires a world declaration, not a strategy" in output.err
    assert "Traceback" not in output.out + output.err

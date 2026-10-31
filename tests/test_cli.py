"""Tests for FunnelScript CLI commands, exit codes, and flags.

Falsifiable Hypotheses:
- H_{4.1}: Package executes cleanly with < 300ms startup.
- H_{4.2}: Exit codes map to 0 (success), 1 (parse/lint failure), 2 (file not found).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import json
import pytest

from funnelscript.cli import check_command, init_command, schema_command, simulate_command


def test_cli_exit_code_file_not_found(tmp_path):
    """Exit code 2 when target file does not exist."""
    fake_file = str(tmp_path / "non_existent.json")
    code = check_command(fake_file, quiet=True)
    assert code == 2

    code_sim = simulate_command(fake_file, as_json=True)
    assert code_sim == 2


def test_cli_check_valid_strategy():
    """Exit code 0 on valid strategy file."""
    sample_file = "examples/black_friday_2026.json"
    code = check_command(sample_file, quiet=True)
    assert code == 0


def test_cli_check_invalid_syntax(tmp_path):
    """Exit code 1 on malformed JSON or AST invariant breach."""
    bad_file = tmp_path / "malformed.json"
    bad_file.write_text("{ not valid json: 123 }", encoding="utf-8")

    code = check_command(str(bad_file), quiet=True)
    assert code == 1


def test_cli_init_command(tmp_path):
    """init command generates clean, lintable starter strategy."""
    target_fnl = tmp_path / "summer_launch.fnl.json"
    code = init_command("Summer Launch", str(target_fnl))
    assert code == 0
    assert target_fnl.exists()

    # The generated template must pass check with 0 errors
    check_code = check_command(str(target_fnl), quiet=True)
    assert check_code == 0


def test_cli_schema_command(tmp_path):
    """schema command outputs valid JSON Schema."""
    schema_path = tmp_path / "schema.json"
    code = schema_command(str(schema_path))
    assert code == 0
    assert schema_path.exists()

    content = json.loads(schema_path.read_text(encoding="utf-8"))
    assert content["title"] == "FunnelScript Strategy Specification"


def test_cli_simulate_with_exports(tmp_path):
    """simulate command runs and writes CSV & JSON exports."""
    sample_file = "examples/black_friday_2026.json"
    csv_out = str(tmp_path / "trials.csv")
    json_out = str(tmp_path / "report.json")

    code = simulate_command(
        file_path=sample_file,
        trials=5,
        agents=2000,
        export_csv=csv_out,
        export_json_path=json_out,
        as_json=True,
    )
    assert code == 0
    assert Path(csv_out).exists()
    assert Path(json_out).exists()

    report_data = json.loads(Path(json_out).read_text(encoding="utf-8"))
    assert report_data["trials_count"] == 5
    assert "roas" in report_data["metrics"]


def test_cli_subprocess_invocation():
    """Test standard subprocess invocation through the installed entrypoint."""
    res = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "FunnelScript" in res.stdout
    assert "simulate" in res.stdout

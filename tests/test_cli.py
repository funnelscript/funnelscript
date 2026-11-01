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


# Phase 002: keep user input errors separate from internal faults and I/O failures.
def test_cli_check_propagates_unexpected_parser_fault(monkeypatch):
    from unittest.mock import Mock
    from funnelscript import cli

    monkeypatch.setattr(
        cli.Parser, "from_file", Mock(side_effect=AttributeError("internal parser fault"))
    )
    with pytest.raises(AttributeError, match="internal parser fault"):
        cli.check_command("examples/black_friday_2026.json")


def test_cli_simulate_propagates_unexpected_parser_fault(monkeypatch):
    from unittest.mock import Mock
    from funnelscript import cli

    monkeypatch.setattr(cli, "check_command", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        cli.Parser, "from_file", Mock(side_effect=AttributeError("internal parser fault"))
    )
    with pytest.raises(AttributeError, match="internal parser fault"):
        cli.simulate_command("examples/black_friday_2026.json")


@pytest.mark.parametrize("command", ["check", "simulate"])
def test_cli_parser_read_error_is_io_failure(monkeypatch, capsys, command):
    from unittest.mock import Mock
    from funnelscript import cli

    monkeypatch.setattr(
        cli.Parser, "from_file", Mock(side_effect=PermissionError("access denied"))
    )
    if command == "check":
        code = cli.check_command("examples/black_friday_2026.json")
    else:
        monkeypatch.setattr(cli, "check_command", lambda *args, **kwargs: 0)
        code = cli.simulate_command("examples/black_friday_2026.json")

    output = capsys.readouterr()
    assert code == 2
    assert "access denied" in output.err
    assert "Parse Error" not in output.out


def test_cli_world_lexer_error_is_controlled(monkeypatch, capsys):
    from unittest.mock import Mock
    from funnelscript import cli
    from funnelscript.tokens import LexerError

    monkeypatch.setattr(
        cli.Parser, "from_file", Mock(side_effect=LexerError("invalid token", 1, 1))
    )
    assert cli.check_command("examples/counter_world.fnl") == 1
    assert "Parse Error" in capsys.readouterr().out


def test_cli_simulate_malformed_input_is_controlled(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ this is not JSON", encoding="utf-8")
    assert simulate_command(str(bad_file), as_json=True) == 1


def test_cli_event_oversized_json_rejected_before_decode(monkeypatch):
    from unittest.mock import Mock
    from funnelscript import cli

    decoder = Mock(side_effect=AssertionError("decoder must not run"))
    monkeypatch.setattr(cli.json, "loads", decoder)
    with pytest.raises(ValueError, match="64 KiB"):
        cli._parse_world_input_event('{"name":"Counter.Tick","time":0,"payload":{"x":"' + "x" * 65536 + '"}}')
    decoder.assert_not_called()


def test_cli_event_size_is_measured_in_utf8_bytes_before_decode(monkeypatch):
    from unittest.mock import Mock
    from funnelscript import cli

    decoder = Mock(side_effect=AssertionError("decoder must not run"))
    monkeypatch.setattr(cli.json, "loads", decoder)
    with pytest.raises(ValueError, match="64 KiB"):
        cli._parse_world_input_event('{"name":"Counter.Tick","time":0,"payload":{"x":"' + "é" * 33000 + '"}}')
    decoder.assert_not_called()


def test_cli_event_json_exact_limit_is_valid():
    from funnelscript.cli import _parse_world_input_event

    base = '{"name":"Counter.Tick","time":0}'
    event = _parse_world_input_event(base + " " * (65536 - len(base)))
    assert event.name == "Counter.Tick" and event.time == 0


@pytest.mark.parametrize("spec", [
    '{"name":"Counter.Tick","name":"Other.Tick","time":0}',
    '{"name":"Counter.Tick","time":0,"unexpected":true}',
    '["Counter.Tick",0]',
    '{"name":"Counter.Tick","time":-1}',
    '{"name":"Counter.Tick","time":1e999}',
])
def test_cli_event_invalid_records_are_rejected(spec):
    from funnelscript.cli import _parse_world_input_event

    with pytest.raises((ValueError, TypeError)):
        _parse_world_input_event(spec)


def test_cli_export_io_failure_has_status_2_and_no_early_success(capsys, tmp_path):
    from funnelscript import cli

    csv_path = tmp_path / "trials.csv"
    code = cli.simulate_command(
        "examples/black_friday_2026.json",
        trials=1,
        agents=100,
        export_csv=str(csv_path),
        export_json_path=str(tmp_path),  # directory, not a writable JSON file
    )
    captured = capsys.readouterr()
    assert code == 2
    assert csv_path.exists()
    assert "Export I/O error" in captured.err
    assert "exported to CSV" not in captured.out


def test_cli_export_absolute_destination_remains_allowed(tmp_path):
    report_path = (tmp_path / "nested" / "report.json").resolve()
    code = simulate_command(
        "examples/black_friday_2026.json",
        trials=1,
        agents=100,
        export_json_path=str(report_path),
        as_json=True,
    )
    assert code == 0
    assert report_path.is_file()

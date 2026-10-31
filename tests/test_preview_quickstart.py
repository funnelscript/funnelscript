"""H-P1/H-P2: public CLI first-run and safe file creation contracts."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from funnelscript.parser import Parser
from funnelscript.compiler.world_ast import WorldAST


def cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", *args],
        cwd=cwd, text=True, capture_output=True, check=False,
    )


def test_init_world_creates_executable_marketing_starter(tmp_path):
    result = cli(tmp_path, "init-world", "trial.fnl")
    assert result.returncode == 0, result.stderr
    assert "\\nRun:" not in result.stdout
    assert "\nRun: funnelscript check trial.fnl" in result.stdout
    path = tmp_path / "trial.fnl"
    content = path.read_text(encoding="utf-8")
    assert 'import "std:marketing/lead_response.fnl" as Prospect;' in content
    ast = Parser.from_file(path)
    assert isinstance(ast, WorldAST)
    assert [(d.kind, d.name) for d in ast.declarations] == [("agent", "Prospect")]

    checked = cli(tmp_path, "check", "trial.fnl")
    assert checked.returncode == 0, checked.stderr

    event = json.dumps({
        "name": "Prospect.Impression",
        "time": 0,
        "payload": {
            "cpc": 2.0,
            "conversion_probability": 0.7,
            "order_value": 100.0,
        },
    })
    executed = cli(tmp_path, "run-world", "trial.fnl", "--event", event, "--seed", "1")
    assert executed.returncode == 0, executed.stderr
    report = json.loads(executed.stdout)
    assert report["processed_events"] == 2
    assert report["state"]["Prospect"] == {
        "exposed": True, "converted": True, "spend": 2.0, "revenue": 100.0
    }


def test_init_world_rejects_overwriting_existing_user_data(tmp_path):
    path = tmp_path / "trial.fnl"
    path.write_bytes(b"important user world\n")
    result = cli(tmp_path, "init-world", str(path))
    assert result.returncode != 0
    assert b"important user world\n" == path.read_bytes()
    assert "exists" in result.stderr.lower()


@pytest.mark.parametrize(
    ("target", "expected"),
    [("trial.json", ".fnl"), ("trial", ".fnl"), ("missing/trial.fnl", "directory")],
)
def test_init_world_rejects_invalid_targets_without_creating_files(tmp_path, target, expected):
    result = cli(tmp_path, "init-world", target)
    assert result.returncode != 0
    assert expected in result.stderr.lower()
    assert not (tmp_path / target).exists()


def test_init_world_help_discloses_command(tmp_path):
    result = cli(tmp_path, "--help")
    assert result.returncode == 0
    assert "init-world" in result.stdout


def test_preview_cli_reports_installed_distribution_version(tmp_path):
    result = cli(tmp_path, "--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "funnelscript 0.2.0a1"


def test_generated_world_can_import_documented_local_counter_module(tmp_path):
    assert cli(tmp_path, "init-world", "first.fnl").returncode == 0
    (tmp_path / "counter.fnl").write_text(
        """world CounterLibrary {
  entity Counter {
    state count: int = 0;
    event Pulse();
    rule Record on event Pulse {
      transition count = count + 1;
    }
  }
}
""", encoding="utf-8",
    )
    starter = tmp_path / "first.fnl"
    starter.write_text(
        starter.read_text(encoding="utf-8").replace(
            "\n}", '\n  import "./counter.fnl" as Tracker;\n}'
        ), encoding="utf-8",
    )
    checked = cli(tmp_path, "check", "first.fnl")
    assert checked.returncode == 0, checked.stderr
    executed = cli(tmp_path, "run-world", "first.fnl", "--event", "Tracker.Pulse@0")
    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout)["state"]["Tracker"]["count"] == 1

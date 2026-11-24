"""Verification suite for FunnelScript CLI 'fpm' command integration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import pytest

from funnelscript.cli import fpm_command


def _is_fpm_available() -> bool:
    if shutil.which("fpm") is not None:
        return True
    candidate_dirs = [
        Path(__file__).resolve().parents[2] / "fpm",
        Path(__file__).resolve().parents[3] / "fpm",
        Path.cwd().parent / "fpm",
        Path.cwd() / "fpm",
    ]
    for cand in candidate_dirs:
        if (cand / ".venv/bin/fpm").is_file() or (cand / "src/fpm").is_dir():
            return True
    return importlib.util.find_spec("fpm") is not None


def test_cli_fpm_command_help(capsys):
    code = fpm_command(["--help"])
    if not _is_fpm_available():
        assert code == 1
        assert "fpm (Funnel Package Manager) executable not found" in capsys.readouterr().out
    else:
        assert code == 0


def test_cli_fpm_command_init_scaffold(tmp_path: Path, capsys):
    target_dir = tmp_path / "test_pkg"
    code = fpm_command(["init", "myorg/custom_strategy", "--dir", str(target_dir)])
    if not _is_fpm_available():
        assert code == 1
        assert "fpm (Funnel Package Manager) executable not found" in capsys.readouterr().out
    else:
        assert code == 0
        assert (target_dir / "fpm.toml").is_file()
        assert (target_dir / "index.fnls").is_file()
        assert (target_dir / "README.md").is_file()
        assert (target_dir / ".gitignore").is_file()

        manifest_content = (target_dir / "fpm.toml").read_text(encoding="utf-8")
        assert 'name = "myorg/custom_strategy"' in manifest_content


def test_cli_fpm_command_verify_on_invalid_pkg(tmp_path: Path):
    # Empty dir without fpm.toml
    bad_dir = tmp_path / "empty_pkg"
    bad_dir.mkdir()
    code = fpm_command(["verify"])
    # Should exit non-zero since no fpm.toml/fpm.lock
    assert code != 0

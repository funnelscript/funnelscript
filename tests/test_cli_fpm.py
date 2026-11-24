"""Verification suite for FunnelScript CLI 'fpm' command integration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

from funnelscript.cli import fpm_command


def test_cli_fpm_command_help(capsys):
    code = fpm_command(["--help"])
    assert code == 0


def test_cli_fpm_command_init_scaffold(tmp_path: Path):
    target_dir = tmp_path / "test_pkg"
    code = fpm_command(["init", "myorg/custom_strategy", "--dir", str(target_dir)])
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

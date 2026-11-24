"""Pytest test suite for FunnelScript editor extension and syntax grammar."""

from __future__ import annotations

import sys
from pathlib import Path

# Add editors/vscode to sys.path so validate_grammar can be imported
VSCODE_TESTS_DIR = Path(__file__).resolve().parent.parent / "editors" / "vscode" / "tests"
if str(VSCODE_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(VSCODE_TESTS_DIR))

from validate_grammar import validate_extension


def test_funnelscript_editor_extension_validation():
    """Verify JSON manifests, regex compilation, icon assets, keyword coverage, and example parsing."""
    validate_extension()

"""Independent CLI contract tests for cross-repository accepted-ADR parity."""

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_decision_parity.py"


def ledger(*, title="Test Contract", status="Accepted", decision_id="DEC-001", repeat=False, detail_title=None):
    row = (
        f"| **{decision_id}** | [{title}](#test-contract) | 2026-11-01 | "
        f"**{status}** | Independent evidence |"
    )
    rows = row + ("\n" + row if repeat else "")
    return (
        "# Decisions\n\n## Decision Index\n\n"
        + rows
        + "\n\n---\n\n## Detailed Architecture Decision Records\n\n"
        + f"### {decision_id}: {detail_title or title}\n\n* **Decision:** Contract.\n"
    )


def check_pair(tmp_path, app_text, research_text):
    app = tmp_path / "application.md"
    research = tmp_path / "research.md"
    app.write_text(app_text, encoding="utf-8")
    research.write_text(research_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(app), str(research)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_identical_accepted_decisions_pass(tmp_path):
    result = check_pair(tmp_path, ledger(), ledger())
    assert result.returncode == 0, result.stderr


def test_historical_heading_punctuation_variant_does_not_block_parity(tmp_path):
    result = check_pair(tmp_path, ledger(detail_title="Test — Contract"), ledger())
    assert result.returncode == 0, result.stderr


def test_mutated_status_fails_closed(tmp_path):
    result = check_pair(tmp_path, ledger(), ledger(status="Proposed"))
    assert result.returncode == 1
    assert "DEC-001" in result.stderr


def test_missing_accepted_decision_fails(tmp_path):
    result = check_pair(tmp_path, ledger(), ledger(decision_id="DEC-002"))
    assert result.returncode == 1
    assert "DEC-001" in result.stderr
    assert "DEC-002" in result.stderr


def test_changed_title_fails(tmp_path):
    result = check_pair(tmp_path, ledger(), ledger(title="Different Contract"))
    assert result.returncode == 1
    assert "DEC-001" in result.stderr


def test_duplicate_index_entry_fails_before_comparison(tmp_path):
    result = check_pair(tmp_path, ledger(repeat=True), ledger())
    assert result.returncode == 1
    assert "duplicate" in result.stderr.lower()


def test_empty_ledgers_are_not_a_valid_parity_success(tmp_path):
    empty = "# Decisions\n\n## Decision Index\n\n## Detailed Architecture Decision Records\n"
    result = check_pair(tmp_path, empty, empty)
    assert result.returncode == 1
    assert "empty" in result.stderr.lower()


def test_missing_file_reports_io_error(tmp_path):
    missing = tmp_path / "missing.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing), str(missing)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2

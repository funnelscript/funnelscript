"""Suite 1: Trait Conformance & Negative Compiler Tests (Gate G1).

Research: docs/meta-ontology/04_TESTING_AND_VERIFICATION.md
Verifies:
1. Valid Conformance: Custom entities implementing 1 or multiple Traits compile cleanly.
2. Negative Cases: Strict compile/lint-time detection of all FNL-O3xx diagnostic codes:
   - FNL-O301: Missing required Trait field or lifecycle handler.
   - FNL-O302: Trait dimensional unit mismatch (e.g. Duration where Currency is required).
   - FNL-O303: Unbalanced double-entry posting inside a handler.
   - FNL-O304: Ambiguous Trait diamond collision without qualified disambiguation.
   - FNL-O305: Unsupported class inheritance ('extends').
3. Zero Raw Python Tracebacks: All failures emit structured, span-accurate diagnostics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from funnelscript.cli import check_command
from funnelscript.compiler.linter import WorldLinter
from funnelscript.formatter import format_funnelscript
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import Lexer

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "meta-ontology"


def _parse_and_lint(file_path: Path):
    source = file_path.read_text(encoding="utf-8")
    tokens = Lexer(source, file=str(file_path)).tokenize()
    ast = Parser(tokens).parse_world()
    linter = WorldLinter(ast)
    errors = linter.lint()
    return ast, errors


def test_valid_single_trait_conformance() -> None:
    """Valid entity implementing a single trait passes linter with zero errors."""
    fixture = FIXTURES_DIR / "valid_single_trait.fnls"
    ast, errors = _parse_and_lint(fixture)
    assert ast.name == "ValidSingleTraitWorld"
    assert len(errors) == 0, f"Unexpected linter errors: {[str(e) for e in errors]}"


def test_valid_multi_trait_conformance() -> None:
    """Valid entity implementing multiple traits passes linter cleanly."""
    fixture = FIXTURES_DIR / "valid_multi_trait.fnls"
    ast, errors = _parse_and_lint(fixture)
    assert ast.name == "ValidMultiTraitWorld"
    assert len(errors) == 0, f"Unexpected linter errors: {[str(e) for e in errors]}"


def test_missing_trait_member_fnl_o301() -> None:
    """Gate G1: Missing required Trait member emits FNL-O301 statically."""
    fixture = FIXTURES_DIR / "invalid_missing_member_fnl_o301.fnls"
    _ast, errors = _parse_and_lint(fixture)
    assert len(errors) > 0
    codes = [e.code for e in errors]
    assert "FNL-O301" in codes
    missing_error = next(e for e in errors if e.code == "FNL-O301")
    assert "Missing required Trait" in str(missing_error)
    assert missing_error.span is not None
    assert missing_error.remediation != ""


def test_dimensional_mismatch_fnl_o302() -> None:
    """Gate G1: Incompatible dimensional unit on Trait field emits FNL-O302."""
    fixture = FIXTURES_DIR / "invalid_dimensional_mismatch_fnl_o302.fnls"
    _ast, errors = _parse_and_lint(fixture)
    assert len(errors) > 0
    codes = [e.code for e in errors]
    assert "FNL-O302" in codes
    dim_error = next(e for e in errors if e.code == "FNL-O302")
    assert "Dimensional unit mismatch" in str(dim_error)
    assert "expected Currency" in str(dim_error)
    assert "got Duration" in str(dim_error)
    assert dim_error.span is not None


def test_unbalanced_ledger_posting_fnl_o303() -> None:
    """Gate G1: Unbalanced double-entry posting inside handler emits FNL-O303."""
    fixture = FIXTURES_DIR / "invalid_unbalanced_ledger_fnl_o303.fnls"
    _ast, errors = _parse_and_lint(fixture)
    assert len(errors) > 0
    codes = [e.code for e in errors]
    assert "FNL-O303" in codes
    ledger_error = next(e for e in errors if e.code == "FNL-O303")
    assert "Unbalanced double-entry posting" in str(ledger_error)
    assert "total debits (100) != total credits (60)" in str(ledger_error)
    assert ledger_error.span is not None


def test_diamond_collision_fnl_o304() -> None:
    """Gate G1: Conflicting member signatures across traits emit FNL-O304."""
    fixture = FIXTURES_DIR / "invalid_diamond_collision_fnl_o304.fnls"
    _ast, errors = _parse_and_lint(fixture)
    assert len(errors) > 0
    codes = [e.code for e in errors]
    assert "FNL-O304" in codes
    collision_error = next(e for e in errors if e.code == "FNL-O304")
    assert "Ambiguous Trait diamond collision" in str(collision_error)
    assert "status" in str(collision_error)
    assert collision_error.span is not None


def test_unsupported_extends_fnl_o305() -> None:
    """Gate G1: Unsupported class inheritance ('extends') emits FNL-O305 statically."""
    fixture = FIXTURES_DIR / "invalid_extends_fnl_o305.fnls"
    source = fixture.read_text(encoding="utf-8")
    tokens = Lexer(source, file=str(fixture)).tokenize()
    with pytest.raises(ParserError) as exc_info:
        Parser(tokens).parse_world()

    err_str = str(exc_info.value)
    assert "FNL-O305" in err_str
    assert "Unsupported class inheritance ('extends')" in err_str


def test_cli_check_command_diagnostics(capsys: pytest.CaptureFixture[str]) -> None:
    """funnelscript check outputs user-friendly diagnostics and returns correct exit codes."""
    # Valid fixtures return 0
    valid_1 = str(FIXTURES_DIR / "valid_single_trait.fnls")
    assert check_command(valid_1, quiet=True) == 0

    valid_2 = str(FIXTURES_DIR / "valid_multi_trait.fnls")
    assert check_command(valid_2, quiet=True) == 0

    # Negative fixtures return 1 and print formatted diagnostics
    missing_fix = str(FIXTURES_DIR / "invalid_missing_member_fnl_o301.fnls")
    assert check_command(missing_fix, quiet=False) == 1

    dim_fix = str(FIXTURES_DIR / "invalid_dimensional_mismatch_fnl_o302.fnls")
    assert check_command(dim_fix, quiet=False) == 1

    unbalanced_fix = str(FIXTURES_DIR / "invalid_unbalanced_ledger_fnl_o303.fnls")
    assert check_command(unbalanced_fix, quiet=False) == 1

    extends_fix = str(FIXTURES_DIR / "invalid_extends_fnl_o305.fnls")
    assert check_command(extends_fix, quiet=False) == 1


def test_meta_ontology_fmt_idempotency() -> None:
    """funnelscript fmt round-trips all valid meta-ontology fixtures idempotently."""
    for fixture in FIXTURES_DIR.glob("valid_*.fnls"):
        source = fixture.read_text(encoding="utf-8")
        f1 = format_funnelscript(source)
        f2 = format_funnelscript(f1)
        assert f1 == f2, f"Formatter not idempotent on {fixture.name}"

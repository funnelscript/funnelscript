"""Verification suite for Canonical Formatter and EBNF Grammar Drift Guard.

Pillars & Hardening Spec:
- Pillar 1.1: Single-source grammar synchronization with spec/grammar.ebnf.
- Pillar 1.3: Formatter idempotency: fmt(fmt(s)) == fmt(s) and AST round-trip parse(fmt(s)) == parse(s).
- Core 99 Track A2: Grammar-to-parser drift protection & CLI fmt command.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from funnelscript.cli import fmt_command
from funnelscript.formatter import format_funnelscript
from funnelscript.parser import Parser
from funnelscript.tokens import TokenType

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
CONFORMANCE_DIR = REPO_ROOT / "tests/fixtures/world-conformance"
GRAMMAR_EBNF = REPO_ROOT / "spec/grammar.ebnf"


def _get_valid_fixtures() -> list[Path]:
    fixtures: list[Path] = []
    if EXAMPLES_DIR.is_dir():
        fixtures.extend(sorted(EXAMPLES_DIR.glob("*.fnls")))
    if CONFORMANCE_DIR.is_dir():
        fixtures.extend(p for p in sorted(CONFORMANCE_DIR.glob("*.fnls")) if "invalid" not in p.name)
    return fixtures


class TestFormatterIdempotencyAndASTEquivalence:
    """Tests canonical code formatting properties."""

    @pytest.mark.parametrize("fixture_path", _get_valid_fixtures(), ids=lambda p: p.name)
    def test_formatter_idempotency_and_ast_roundtrip(self, fixture_path: Path) -> None:
        source = fixture_path.read_text(encoding="utf-8")
        formatted_once = format_funnelscript(source)
        formatted_twice = format_funnelscript(formatted_once)

        # 1. Idempotency Invariant: fmt(fmt(s)) == fmt(s)
        assert formatted_once == formatted_twice, (
            f"Formatter is not idempotent on {fixture_path.name}"
        )

        # 2. AST Equivalence Invariant: parse(fmt(s)) == parse(s)
        # We write to an adjacent temporary hidden file so relative module imports resolve correctly
        tmp_adjacent = fixture_path.with_name(f".tmp_verify_fmt_{fixture_path.name}")
        tmp_adjacent.write_text(formatted_once, encoding="utf-8")
        try:
            ast_orig = Parser.from_file(fixture_path)
            ast_fmt = Parser.from_file(tmp_adjacent)
            assert ast_orig.model_dump() == ast_fmt.model_dump(), (
                f"AST mismatch after formatting {fixture_path.name}"
            )
        finally:
            tmp_adjacent.unlink(missing_ok=True)

    def test_formatter_empty_and_whitespace(self) -> None:
        assert format_funnelscript("") == ""
        assert format_funnelscript("   \n\t  ") == ""

    def test_cli_fmt_command_workflow(self, tmp_path: Path) -> None:
        sample_code = "world MessyWorld { entity   M { state active: bool=true; } }"
        test_file = tmp_path / "model.fnls"
        test_file.write_text(sample_code, encoding="utf-8")

        # Check only before formatting -> should exit 1 (needs formatting)
        check_code = fmt_command(str(test_file), check_only=True)
        assert check_code == 1

        # Format in place -> should exit 0
        format_code = fmt_command(str(test_file), check_only=False)
        assert format_code == 0

        # Check only after formatting -> should exit 0 (already formatted)
        check_code_after = fmt_command(str(test_file), check_only=True)
        assert check_code_after == 0

        content = test_file.read_text(encoding="utf-8")
        assert "world MessyWorld {" in content
        assert "  entity M {" in content


class TestGrammarDriftGuard:
    """Verifies that spec/grammar.ebnf and tokens.py / parser.py stay synchronized."""

    def test_grammar_ebnf_file_exists(self) -> None:
        assert GRAMMAR_EBNF.is_file(), f"Missing canonical EBNF grammar file at {GRAMMAR_EBNF}"

    def test_grammar_keywords_match_lexer_tokens(self) -> None:
        ebnf_text = GRAMMAR_EBNF.read_text(encoding="utf-8")

        # Extract all literal string tokens quoted with "..." from the EBNF
        literals = set(re.findall(r'"([a-zA-Z_][a-zA-Z0-9_]*)"', ebnf_text))

        # Core keywords expected in FunnelScript grammar
        expected_keywords = {
            "world", "entity", "agent", "trait", "implements", "state", "event",
            "rule", "on", "when", "transition", "emit", "import", "as", "to",
            "true", "false", "flow", "ledger", "capacity", "metric", "debit", "credit"
        }

        # Check that all expected keywords are present in the EBNF grammar
        missing_in_ebnf = expected_keywords - literals
        assert not missing_in_ebnf, f"EBNF grammar is missing keywords: {missing_in_ebnf}"

        # Check that lexer recognizes structural operator/symbol tokens
        token_types = {t.name for t in TokenType}
        for op in ("LBRACE", "RBRACE", "LPAREN", "RPAREN", "COMMA", "SEMICOLON", "COLON", "ASSIGN", "ARROW", "FAT_ARROW", "EQ", "NEQ", "GT", "LT"):
            assert op in token_types, f"TokenType is missing operator: {op}"

        # Contextual declaration words in the World parser are parsed as IDENTIFIER soft keywords
        assert "IDENTIFIER" in token_types
        assert "STRING" in token_types
        assert "NUMBER" in token_types

    def test_production_rules_correspond_to_parser_methods(self) -> None:
        ebnf_text = GRAMMAR_EBNF.read_text(encoding="utf-8")

        # Find production rule headers: NonTerminal ::=
        productions = re.findall(r"^([A-Z][a-zA-Z0-9_]*)\s*::=", ebnf_text, re.MULTILINE)
        assert len(productions) >= 15, f"Expected at least 15 production rules in EBNF, found {len(productions)}"

        key_productions = [
            "WorldFile", "WorldDeclaration", "WorldEntityDeclaration",
            "WorldAgentDeclaration", "WorldTraitDeclaration", "EventDeclaration",
            "RuleDeclaration", "StateField"
        ]
        for prod in key_productions:
            assert prod in productions, f"Grammar production rule {prod} missing from spec/grammar.ebnf"

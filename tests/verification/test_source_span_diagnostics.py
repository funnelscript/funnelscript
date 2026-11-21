"""Source-location falsification tests for the FunnelScript compiler.

Research anchor: source-map provenance and precise compiler diagnostics.
H: emitted tokens retain end-exclusive source positions, including multiline
strings and imported modules, without changing their semantic token values.
Invariant: the reported location delimits exactly the token's source lexeme.
"""

from pathlib import Path

import pytest

from funnelscript.cli import check_command
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import Lexer, SourceSpan, TokenType


def test_token_spans_include_exclusive_end_and_real_lexeme_width():
    source = "world W { state n: float = 12.5; }"
    tokens = Lexer(source).tokenize()
    number = next(item for item in tokens if item.type is TokenType.NUMBER)
    assert number.span == SourceSpan("<memory>", 1, 28, 1, 32)
    assert source[number.span.start_col - 1 : number.span.end_col - 1] == "12.5"
    last = tokens[-1]
    assert last.span == SourceSpan("<memory>", 1, len(source) + 1, 1, len(source) + 1)


def test_multiline_string_span_covers_closing_quote():
    source = 'world W {\n  "first\nsecond"\n}'
    token = next(t for t in Lexer(source).tokenize() if t.type is TokenType.STRING)
    assert token.span == SourceSpan("<memory>", 2, 3, 3, 8)


def test_parser_error_points_to_originating_import_file(tmp_path: Path):
    source = tmp_path / "entry.fnl"
    module = tmp_path / "module.fnl"
    module.write_text("world M { entity E { state count: int = ; } }", encoding="utf-8")
    source.write_text('world Main { import "module.fnl" as Alias; }', encoding="utf-8")
    with pytest.raises(ParserError) as exc:
        Parser.from_file(source)
    assert exc.value.token is not None
    assert exc.value.token.span.file == str(module.resolve())
    assert exc.value.token.span.start_line == 1


def test_check_command_reports_code_snippet_and_caret(tmp_path: Path, capsys):
    source = tmp_path / "invalid.fnl"
    source.write_text("world W {\n  entity E { state count: int = ; }\n}", encoding="utf-8")
    assert check_command(str(source)) == 1
    text = capsys.readouterr().out
    assert "Parse Error" in text
    assert "FNL-E102" in text
    assert "state count: int = ;" in text
    assert "^" in text
    assert "line 2" in text


def test_lexical_error_reports_source_with_caret_and_code(tmp_path: Path, capsys):
    source = tmp_path / "illegal.fnl"
    source.write_text("world W {\n  entity E { ? }\n}", encoding="utf-8")
    assert check_command(str(source)) == 1
    text = capsys.readouterr().out
    assert "FNL-E101" in text
    assert "entity E { ? }" in text
    assert "^" in text
    assert "line 2" in text

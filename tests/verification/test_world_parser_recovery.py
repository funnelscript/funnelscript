"""Panic-mode parsing at World statement and declaration synchronization points.

Research anchor: compiler panic-mode error recovery at grammar FOLLOW boundaries.
H: independent malformed declarations and statements yield distinct source-mapped
diagnostics without emitting any executable, partially validated World AST.
Invariant: parser token position is monotonic, the diagnostic count is bounded
by 32, and any syntax error makes World compilation fail closed.
"""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.cli import check_command
from funnelscript.parser import Parser, ParserError, ParserErrors
from funnelscript.tokens import Lexer


def _parse(tmp_path: Path, source: str):
    path = tmp_path / "recovery.fnls"
    path.write_text(source, encoding="utf-8")
    return Parser.from_file(path)


def test_collects_independent_state_errors_without_losing_following_members(tmp_path):
    source = """world Errors {
  entity E {
    state missing: int = ;
    state fine: int = 10;
    state wrong: int = true + 1;
    state last: int = ;
  }
}"""
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, source)
    errors = caught.value.errors
    assert len(errors) == 3
    assert [err.token.line for err in errors] == [3, 5, 6]
    assert all(str(tmp_path / "recovery.fnls") in str(err) for err in errors)
    assert str(caught.value).count("FNL-E102") == 3


def test_collects_two_rule_statement_errors_across_successful_emit(tmp_path):
    source = """world Errors {
  agent A {
    state count: int = 0;
    event Ping();
    rule OnPing on event Ping {
      transition count = ;
      emit Ping() after 1;
      transition count = ;
    }
  }
}"""
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, source)
    assert [err.token.line for err in caught.value.errors] == [6, 8]


def test_recovers_from_invalid_top_level_block_to_later_declarations(tmp_path):
    source = """world Errors {
  touchpoint Bad {}
  entity E { state missing: int = ; }
  agent A { state missing: bool = ; }
}"""
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, source)
    assert [err.token.line for err in caught.value.errors] == [2, 3, 4]


def test_single_error_stays_legacy_parser_error(tmp_path):
    with pytest.raises(ParserError) as caught:
        _parse(tmp_path, "world Errors { entity E { state bad: int = ; } }")
    assert type(caught.value) is ParserError


def test_truncated_block_adds_unclosed_diagnostic_to_prior_error(tmp_path):
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, "world Errors { entity E { state a: int = ;")
    assert "Unclosed entity or agent" in str(caught.value)
    assert len(caught.value.errors) == 2


def test_cli_reports_multiple_diagnostics_without_traceback(tmp_path, capsys):
    path = tmp_path / "bad.fnls"
    path.write_text(
        "world X { entity E { state a: int = ; state b: bool = ; } }",
        encoding="utf-8",
    )
    assert check_command(str(path)) == 1
    output = capsys.readouterr()
    rendered = output.out + output.err
    assert rendered.count("FNL-E102") == 2
    assert "Traceback" not in rendered


@settings(max_examples=80, deadline=None, derandomize=True)
@given(st.integers(min_value=2, max_value=32))
def test_many_independent_state_errors_have_bounded_exact_counts(size):
    states = " ".join(f"state bad{i}: int = ;" for i in range(size))
    with pytest.raises(ParserErrors) as caught:
        Parser(Lexer("world W { entity E { " + states + " } }").tokenize()).parse_world()
    assert len(caught.value.errors) == size
    assert [e.token.column for e in caught.value.errors] == sorted(
        e.token.column for e in caught.value.errors
    )


def test_recovery_reports_error_limit_instead_of_unbounded_accumulation(tmp_path):
    states = " ".join(f"state bad{i}: int = ;" for i in range(100))
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, "world W { entity E { " + states + " } }")
    assert len(caught.value.errors) == 32
    assert "limit" in str(caught.value).lower()


def test_broken_emit_arguments_do_not_generate_cascading_rule_errors(tmp_path):
    source = """world Errors {
  agent A {
    state count: int = 0;
    event Ping(value: int);
    rule R on event Ping {
      emit Ping(value = ;) after 1;
      transition count = ;
    }
  }
}"""
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, source)
    assert [err.token.line for err in caught.value.errors] == [6, 7]


def test_missing_semicolon_recovery_preserves_next_statement(tmp_path):
    source = """world Errors {
  entity E {
    state first: int = 1
    state second: int = ;
  }
}"""
    with pytest.raises(ParserErrors) as caught:
        _parse(tmp_path, source)
    assert [err.token.line for err in caught.value.errors] == [4, 4]

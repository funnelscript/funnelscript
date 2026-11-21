"""Falsification cases for deterministic lexical error handling.

Research anchor: compiler exception safety and finite-number semantics.
H: malformed numeric tokens never leak Python conversion exceptions.
Invariant: invalid numeric input raises LexerError at its first source column;
valid numeric tokens retain their existing token kinds and values.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from funnelscript.tokens import Lexer, LexerError, TokenType


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("1.2.3", "Invalid numeric literal"),
        ("9" * 5000, "Invalid numeric literal"),
        ("9" * 350 + "." + "9" * 350, "Non-finite float literal"),
        ("9" * 4000 + "%", "Percentage literal out of range"),
    ],
)
def test_malformed_numeric_literals_are_typed_and_located(source, message):
    with pytest.raises(LexerError, match=message) as exc:
        Lexer("world W {}\n  " + source).tokenize()
    assert exc.value.line == 2
    assert exc.value.column == 3


def test_valid_numeric_lexing_and_range_remain_unchanged():
    tokens = Lexer("12..15 4. 25% 2h").tokenize()
    assert [(token.type, token.value) for token in tokens] == [
        (TokenType.NUMBER, 12),
        (TokenType.DOTDOT, ".."),
        (TokenType.NUMBER, 15),
        (TokenType.NUMBER, 4.0),
        (TokenType.PERCENTAGE, 0.25),
        (TokenType.DURATION, "2h"),
        (TokenType.EOF, ""),
    ]


@settings(max_examples=10000, deadline=None, derandomize=True)
@given(st.text(max_size=64))
def test_lexer_accepts_or_rejects_arbitrary_unicode_with_typed_errors(source):
    try:
        tokens = Lexer(source).tokenize()
    except LexerError:
        return
    assert tokens[-1].type == TokenType.EOF
    assert all(
        math.isfinite(token.value)
        for token in tokens
        if token.type in (TokenType.NUMBER, TokenType.PERCENTAGE)
    )

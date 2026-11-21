"""World parser crash-safety falsification over malformed Unicode inputs.

Research anchor: total parser validation at the DSL input trust boundary.
H: bounded user input never crashes the World parser with unexpected internal
exceptions, independently of its spelling, punctuation or nesting.
Invariant: inputs either produce a valid AST or a deliberate syntax/type
diagnostic; no RecursionError, IndexError, KeyError or AttributeError leaks.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from funnelscript.compiler.world_ast import WorldTypeError
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import Lexer, LexerError


@settings(max_examples=10000, deadline=None, derandomize=True)
@given(st.text(max_size=128))
def test_world_parser_reports_typed_diagnostics_for_arbitrary_source(payload):
    source = "world Fuzz { " + payload + " }"
    try:
        tokens = Lexer(source).tokenize()
        Parser(tokens).parse_world()
    except (LexerError, ParserError, WorldTypeError, ValidationError):
        return


@pytest.mark.parametrize(
    "payload",
    ["(" * 600, "}" * 600, "{" * 600, "a" * 8000],
)
def test_extreme_world_nesting_is_reported_deliberately(payload):
    source = f"world Fuzz {{ entity A {{ {payload} }} }}"
    try:
        tokens = Lexer(source).tokenize()
        Parser(tokens).parse_world()
    except (LexerError, ParserError, WorldTypeError, ValidationError):
        return
    pytest.fail("Malformed extreme nesting was unexpectedly accepted")

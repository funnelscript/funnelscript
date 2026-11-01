"""H-W1 through H-W4: executable tests for world declaration semantics."""

import pytest

from funnelscript.cli import check_command, simulate_command
from funnelscript.parser import Parser, ParserError


WORLD = """world Warehouse {
  entity Shelf {
    state quantity: int = 20;
    state label: string = "A";
  }
  agent Picker {
    state active: bool = true;
    state confidence: float = 0.75;
    state offset: int = -2;
  }
}
"""


def parse_world(tmp_path, source=WORLD):
    file_path = tmp_path / "world.fnl"
    file_path.write_text(source, encoding="utf-8")
    return Parser.from_file(file_path)


def test_parses_general_world_with_typed_entities_and_agents(tmp_path):
    ast = parse_world(tmp_path)
    from funnelscript.compiler.world_ast import AgentDefinition, EntityDefinition, WorldAST

    assert isinstance(ast, WorldAST)
    assert ast.name == "Warehouse"
    assert [node.name for node in ast.declarations] == ["Shelf", "Picker"]
    assert isinstance(ast.declarations[0], EntityDefinition)
    assert not isinstance(ast.declarations[0], AgentDefinition)
    assert isinstance(ast.declarations[1], AgentDefinition)
    assert isinstance(ast.declarations[1], EntityDefinition)
    assert [field.value for field in ast.declarations[1].states] == [True, 0.75, -2]


def test_empty_world_is_valid(tmp_path):
    ast = parse_world(tmp_path, "world Empty {}")
    assert ast.name == "Empty"
    assert ast.declarations == []


def test_rejects_duplicate_entity_and_agent_names(tmp_path):
    source = """world W { entity X {} agent X {} }"""
    with pytest.raises(ValueError, match="Duplicate declaration"):
        parse_world(tmp_path, source)


def test_rejects_duplicate_state_field_names(tmp_path):
    source = """world W { entity Box { state n: int = 2; state n: int = 4; } }"""
    with pytest.raises(ValueError, match="Duplicate state"):
        parse_world(tmp_path, source)


def test_rejects_unknown_types(tmp_path):
    source = """world W { entity Box { state score: marketing_metric = 1; } }"""
    with pytest.raises(ValueError, match="Unknown state type"):
        parse_world(tmp_path, source)


@pytest.mark.parametrize(
    ("declared", "literal"),
    [
        ("int", '"3"'),
        ("int", "true"),
        ("float", "3"),
        ("bool", "0"),
        ("string", "false"),
    ],
)
def test_rejects_mismatched_literal_types(tmp_path, declared, literal):
    source = f"world W {{ entity Box {{ state sample: {declared} = {literal}; }} }}"
    with pytest.raises(ValueError, match="Type mismatch"):
        parse_world(tmp_path, source)


@pytest.mark.parametrize(
    "source",
    [
        "world W { entity X { state n: int = 1 } }",
        "world W { agent X { state n: int = 1; }",
        "world W { touchpoint Ad {} }",
        "world W {} trailing",
    ],
)
def test_rejects_malformed_or_unknown_world_syntax(tmp_path, source):
    with pytest.raises(ParserError):
        parse_world(tmp_path, source)


def test_world_cli_check_accepts_valid_and_rejects_bad(tmp_path):
    valid = tmp_path / "valid.fnl"
    valid.write_text(WORLD, encoding="utf-8")
    bad = tmp_path / "bad.fnl"
    bad.write_text("world W { entity E { state n: bool = 8; } }", encoding="utf-8")

    assert check_command(str(valid), quiet=True) == 0
    assert check_command(str(bad), quiet=True) == 1


def test_legacy_simulator_rejects_world_instead_of_using_campaign_engine(tmp_path):
    path = tmp_path / "world.fnl"
    path.write_text(WORLD, encoding="utf-8")

    assert simulate_command(str(path), trials=1, agents=10, as_json=True) == 1


def test_world_types_are_available_from_compiler_api():
    import funnelscript.compiler as compiler
    from funnelscript.compiler.world_ast import AgentDefinition, EntityDefinition, WorldAST

    assert getattr(compiler, "WorldAST", None) is WorldAST
    assert getattr(compiler, "EntityDefinition", None) is EntityDefinition
    assert getattr(compiler, "AgentDefinition", None) is AgentDefinition


def test_soft_keywords_remain_valid_in_strategy_metadata(tmp_path):
    source = 'strategy Legacy { metadata { state = "draft"; agent = "author"; } }'
    ast = parse_world(tmp_path, source)
    assert ast.metadata["state"] == "draft"
    assert ast.metadata["agent"] == "author"


def test_existing_strategy_parser_remains_compatible():
    ast = Parser.from_file("examples/black_friday_2026.fnl")
    assert ast.strategy_name
    assert len(ast.entities.touchpoints) >= 1


@pytest.mark.parametrize("method", ["parse_world", "parse_strategy", "current"])
def test_empty_parser_tokens_fail_with_deliberate_diagnostic(method):
    with pytest.raises(ParserError, match="Unexpected end of token stream"):
        getattr(Parser([]), method)()


@pytest.mark.parametrize("source", ["", "  # comment only\n // another comment\n", "world", "world X { entity E { state x: int ="])
def test_empty_or_truncated_source_fails_without_index_error(tmp_path, source):
    with pytest.raises(ParserError):
        parse_world(tmp_path, source)


def test_exhausted_non_eof_token_stream_has_deliberate_diagnostic():
    from funnelscript.tokens import Token, TokenType

    with pytest.raises(ParserError, match="Unexpected end of token stream"):
        Parser([Token(TokenType.IDENTIFIER, "world", 1, 1)]).parse_world()

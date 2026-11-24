"""Source-map provenance for the domain-neutral World AST.

Research anchor: compiler source maps and traceable intermediate representations.
H: each parsed World AST node retains its exact lexical boundary and source
file without altering serialized domain data or imported-module provenance.
Invariant: node spans start at their first grammar token and end immediately
after their final token; model_dump excludes all source provenance.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import BaseModel

from funnelscript.compiler.world_ast import (
    AgentDefinition,
    BinaryExpression,
    EntityDefinition,
    EventDefinition,
    EventEmissionDefinition,
    EventFieldDefinition,
    EventRuleDefinition,
    GuardDefinition,
    LiteralExpression,
    PayloadFieldExpression,
    ReferenceExpression,
    SampleExpression,
    StateDefinition,
    StateTransitionDefinition,
    WorldAST,
    WorldTypeError,
)
from funnelscript.models import StrategyAST
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import SourceSpan

SOURCE = """world Experiment {
  agent Visitor {
    state count: int = 0;
    state passed: bool = false;
    event Seen(cost: int);
    rule React on event Seen when (count < 10) {
      transition count = (count + payload.cost);
      emit Seen(cost = count) after 1;
    }
    rule Sample on event Tick {
      transition passed = sample bernoulli(0.5);
    }
  }
}
"""


def _walk(node):
    yield node
    for name in node.__class__.model_fields:
        value = getattr(node, name)
        if isinstance(value, BaseModel):
            yield from _walk(value)
        elif isinstance(value, (list, dict)):
            for member in value.values() if isinstance(value, dict) else value:
                if isinstance(member, BaseModel):
                    yield from _walk(member)


def test_all_world_ast_models_have_exact_source_spans(tmp_path: Path):
    path = tmp_path / "source.fnls"
    path.write_text(SOURCE, encoding="utf-8")
    world = Parser.from_file(path)
    assert isinstance(world, WorldAST)
    nodes = list(_walk(world))
    assert {type(node) for node in nodes} == {
        WorldAST, AgentDefinition, StateDefinition, EventDefinition,
        EventFieldDefinition, EventRuleDefinition, GuardDefinition,
        StateTransitionDefinition, BinaryExpression, ReferenceExpression,
        PayloadFieldExpression, LiteralExpression, EventEmissionDefinition,
        SampleExpression,
    }
    for node in nodes:
        assert isinstance(node.span, SourceSpan), type(node)
        assert node.span.file == str(path.resolve())
        start = (node.span.start_line, node.span.start_col)
        end = (node.span.end_line, node.span.end_col)
        assert start < end

    expr = world.declarations[0].rules[0].transitions[0].expr
    assert expr.span.start_line == 7
    assert SOURCE.splitlines()[expr.span.start_line - 1][expr.span.start_col - 1:expr.span.end_col - 1] == "(count + payload.cost)"
    assert world.span.start_line == 1
    assert world.span.end_line == 14


def test_source_spans_are_immutable_and_excluded_from_ast_json(tmp_path: Path):
    source = tmp_path / "world.fnls"
    source.write_text(SOURCE, encoding="utf-8")
    world = Parser.from_file(source)
    with pytest.raises(FrozenInstanceError):
        world.span.start_line = 50
    assert "span" not in world.model_dump_json()
    assert "span" not in world.model_dump()
    assert world.declarations[0].model_dump() == AgentDefinition.model_validate(
        world.declarations[0].model_dump()
    ).model_dump()


def test_local_module_import_preserves_originating_ast_spans(tmp_path: Path):
    module = tmp_path / "module.fnls"
    source = tmp_path / "main.fnls"
    module.write_text("world Module { entity E { state n: int = 1; } }", encoding="utf-8")
    source.write_text('world Main { import "module.fnls" as Alias; }', encoding="utf-8")
    ast = Parser.from_file(source)
    assert ast.span.file == str(source.resolve())
    node = ast.declarations[0]
    assert isinstance(node, EntityDefinition)
    assert node.name == "Alias"
    assert node.span.file == str(module.resolve())
    assert node.states[0].span.file == str(module.resolve())
    assert node.states[0].span.start_col == 27
    assert "span" not in ast.model_dump_json()


def test_manual_ast_validation_remains_backward_compatible():
    model = StateDefinition.model_validate({"name": "x", "type_name": "int", "value": 1})
    assert model.span is None
    assert model.model_dump() == {"name": "x", "type_name": "int", "value": 1}


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORLD_CORPUS = sorted(
    candidate
    for folder in (_PROJECT_ROOT / "tests" / "fixtures", _PROJECT_ROOT / "examples")
    for candidate in folder.rglob("*.fnls")
)


@pytest.mark.parametrize(
    "file_path", _WORLD_CORPUS,
    ids=lambda path: str(path.relative_to(_PROJECT_ROOT)),
)
def test_entire_world_corpus_has_complete_source_mapping(file_path: Path):
    if file_path.name.startswith("invalid_"):
        try:
            world = Parser.from_file(file_path)
        except (WorldTypeError, ParserError):
            return
        if not isinstance(world, WorldAST):
            assert isinstance(world, StrategyAST)
            return
        nodes = list(_walk(world))
        assert nodes
        assert all(isinstance(node.span, SourceSpan) for node in nodes)
        assert "span" not in world.model_dump_json()
        return

    world = Parser.from_file(file_path)
    if not isinstance(world, WorldAST):
        assert isinstance(world, StrategyAST)
        return
    nodes = list(_walk(world))
    assert nodes
    assert all(isinstance(node.span, SourceSpan) for node in nodes)
    assert "span" not in world.model_dump_json()

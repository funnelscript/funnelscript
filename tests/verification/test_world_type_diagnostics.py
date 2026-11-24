"""World semantic errors carry exact originating spans and render safe diagnostics.

Research anchor: compiler semantic diagnostics that retain AST source provenance.
Hypothesis: type errors from nested nodes and imports identify the original source
location, while in-memory AST validation remains compatible with earlier clients.
Invariant: semantic validation never succeeds on an invalid World, and any
location attached to a semantic error names an existing originating AST span.
"""

from pathlib import Path

import pytest

from funnelscript.cli import check_command
from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker, WorldTypeError
from funnelscript.parser import Parser


@pytest.mark.parametrize(
    ("source", "line", "column", "message"),
    [
        (
            "world W {\n  entity E {\n    state active: bool = 1;\n  }\n}\n",
            3, 5, "Type mismatch",
        ),
        (
            "world W {\n  entity E {\n    state n: int = 1;\n    state n: int = 2;\n  }\n}\n",
            4, 5, "Duplicate state",
        ),
        (
            "world W {\n  entity E {}\n  agent E {}\n}\n",
            3, 3, "Duplicate declaration",
        ),
        (
            "world W {\n  entity E {\n    state n: int = 1;\n    rule R on event Tick {\n      transition missing = n + 1;\n    }\n  }\n}\n",
            5, 7, "Unknown transition target",
        ),
        (
            "world W {\n  entity E {\n    state n: int = 1;\n    rule R on event Tick when (missing == 1) {\n      transition n = 2;\n    }\n  }\n}\n",
            4, 26, "Unknown guard field",
        ),
        (
            "world W {\n  entity E {\n    event Tick(value: bogus);\n  }\n}\n",
            3, 16, "Unknown event field type",
        ),
    ],
)
def test_world_semantic_errors_have_source_location(
    tmp_path: Path, source: str, line: int, column: int, message: str,
):
    path = tmp_path / "world.fnls"
    path.write_text(source)
    with pytest.raises(WorldTypeError, match=message) as captured:
        Parser.from_file(path)
    error = captured.value
    assert error.span is not None
    assert error.span.file == str(path)
    assert (error.span.start_line, error.span.start_col) == (line, column)
    rendered = str(error)
    assert "FNL-T201" in rendered
    assert f"line {line}, column {column}" in rendered
    assert "^" in rendered
    assert "Hint:" in rendered
    assert "Traceback" not in rendered


def test_imported_world_type_failure_is_reported_at_library_source(tmp_path: Path):
    library = tmp_path / "lib.fnls"
    library.write_text("world Lib {\n  entity E {\n    state n: int = true;\n  }\n}\n")
    entry = tmp_path / "entry.fnls"
    entry.write_text('world Entry {\n  import "lib.fnls" as Linked;\n}\n')
    with pytest.raises(WorldTypeError) as captured:
        Parser.from_file(entry)
    assert captured.value.span is not None
    assert captured.value.span.file == str(library)
    assert "state n: int = true;" in str(captured.value)


def test_cli_displays_semantic_code_and_caret_without_traceback(tmp_path: Path, capsys):
    path = tmp_path / "bad.fnls"
    path.write_text("world W {\n  entity E {\n    state n: int = true;\n  }\n}\n")
    assert check_command(str(path)) == 1
    captured = capsys.readouterr()
    rendered = captured.out + captured.err
    assert "FNL-T201" in rendered
    assert "state n: int = true;" in rendered
    assert "^" in rendered
    assert "Traceback" not in rendered


def test_in_memory_world_type_error_keeps_legacy_message():
    world = WorldAST.model_validate({
        "name": "W",
        "declarations": [
            {"kind": "entity", "name": "A", "states": [
                {"name": "n", "type_name": "int", "value": True},
            ]},
        ],
    })
    with pytest.raises(WorldTypeError) as captured:
        WorldTypeChecker.check(world)
    assert captured.value.span is None
    assert str(captured.value) == "Type mismatch for 'A.n': expected int, got bool"

"""Source-accurate World module cycle detection without DAG false positives.

Research anchor: DFS recursion-stack back edges, not graph-wide visited nodes.
Hypothesis: self/cyclic imports report the exact closed file path and offending
import token, while independent diamond dependency branches remain valid.
Invariant: a cycle is reported iff a resolved module is already in the current
active ancestor stack; completed sibling imports never count as cycles.
"""

from pathlib import Path

import pytest

from funnelscript.cli import check_command
from funnelscript.compiler.world_ast import WorldAST
from funnelscript.parser import Parser, ParserError


def _module(path: Path, body: str) -> Path:
    path.write_text(f"world {path.stem.title()} {{\n{body}}}\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("names", [
    ("a.fnls",),
    ("a.fnls", "b.fnls"),
    ("a.fnls", "b.fnls", "c.fnls"),
])
def test_cycle_trace_and_error_source_token(
    tmp_path: Path, names: tuple[str, ...],
):
    paths = [tmp_path / name for name in names]
    for i, current in enumerate(paths):
        target = paths[(i + 1) % len(paths)]
        _module(current, f'  import "{target.name}" as Alias{i};\n')
    with pytest.raises(ParserError) as captured:
        Parser.from_file(paths[0])

    error = captured.value
    diagnostic = str(error)
    closed = " -> ".join(str(p.resolve()) for p in (*paths, paths[0]))
    assert "Cyclic World module import" in diagnostic
    assert closed in diagnostic
    assert "FNL-E102" in diagnostic
    assert error.token is not None
    assert error.token.span is not None
    assert error.token.span.file == str(paths[-1].resolve())
    assert (error.token.span.start_line, error.token.span.start_col) == (2, 10)
    assert f'import "{paths[0].name}"' in diagnostic
    assert "^" in diagnostic
    assert "Hint:" in diagnostic
    assert "Traceback" not in diagnostic


def test_same_basename_in_different_directories_is_not_a_cycle(tmp_path: Path):
    first = tmp_path / "x" / "index.fnls"
    second = tmp_path / "y" / "index.fnls"
    first.parent.mkdir()
    second.parent.mkdir()
    _module(first, "  entity First {}\n")
    _module(second, "  entity Second {}\n")
    entry = _module(
        tmp_path / "main.fnls",
        '  import "x/index.fnls" as MyFirst;\n'
        '  import "y/index.fnls" as MySecond;\n',
    )
    world = Parser.from_file(entry)
    assert [decl.name for decl in world.declarations] == ["MyFirst", "MySecond"]
    assert world.declarations[0].span.file == str(first.resolve())
    assert world.declarations[1].span.file == str(second.resolve())


def test_cycle_reports_minimal_back_edge_not_unrelated_entry_prefix(tmp_path: Path):
    entry = _module(tmp_path / "entry.fnls", '  import "middle.fnls" as Middle;\n')
    middle = _module(tmp_path / "middle.fnls", '  import "leaf.fnls" as Leaf;\n')
    leaf = _module(tmp_path / "leaf.fnls", '  import "middle.fnls" as Loop;\n')
    with pytest.raises(ParserError) as captured:
        Parser.from_file(entry)
    trace = " -> ".join(str(p.resolve()) for p in (middle, leaf, middle))
    error = str(captured.value)
    assert trace in error
    assert str(entry.resolve()) not in error
    assert captured.value.token is not None
    assert captured.value.token.span.file == str(leaf.resolve())


def test_diamond_import_is_not_a_cycle(tmp_path: Path):
    common = _module(tmp_path / "common.fnls", "  entity Shared { state n: int = 1; }\n")
    left = _module(
        tmp_path / "left.fnls",
        '  import "common.fnls" as CommonLeft;\n'
        '  entity Left { state n: int = 2; }\n',
    )
    right = _module(
        tmp_path / "right.fnls",
        '  import "common.fnls" as CommonRight;\n'
        '  entity Right { state n: int = 3; }\n',
    )
    entry = _module(
        tmp_path / "main.fnls",
        '  import "left.fnls" { Left as MyLeft };\n'
        '  import "right.fnls" { Right as MyRight };\n',
    )
    world = Parser.from_file(entry)
    assert isinstance(world, WorldAST)
    assert [decl.name for decl in world.declarations] == ["MyLeft", "MyRight"]
    assert left.exists() and right.exists() and common.exists()


def test_cycle_cli_reports_originating_import_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    a = _module(tmp_path / "a.fnls", '  import "b.fnls" as B;\n')
    _module(tmp_path / "b.fnls", '  import "a.fnls" as A;\n')
    assert check_command(str(a)) == 1
    output = capsys.readouterr()
    diagnostic = output.out + output.err
    assert "FNL-E102" in diagnostic
    assert "Cyclic World module import" in diagnostic
    assert "b.fnls" in diagnostic or "b.fnls" in "".join(diagnostic.split())
    assert "column 10" in diagnostic
    assert "ParserError at line 2, col 10" in diagnostic
    assert "Traceback" not in diagnostic

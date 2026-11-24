"""Phase 007G RED: deterministic named imports from multiple exports."""
import pytest
from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.runtime.world_executor import WorldExecutor


def test_explicit_named_import_selects_and_renames_multi_export(tmp_path):
    (tmp_path / 'bundle.fnls').write_text('''world Reuse {
      entity Counter { state n: int = 0; rule Up on event Tick { transition n = n + 1; } }
      agent Visitor { state visits: int = 0; rule Up on event Tick { transition visits = visits + 1; } }
      entity Hidden { state private: int = 9; }
    }''')
    path = tmp_path / 'main.fnls'
    path.write_text('world W { import "bundle.fnls" { Counter as Balance, Visitor as Lead }; }')
    ast = Parser.from_file(path)
    assert [(d.kind, d.name) for d in ast.declarations] == [('entity', 'Balance'), ('agent', 'Lead')]
    result = WorldExecutor(ast).run([Event(0, 'Balance.Tick'), Event(0, 'Lead.Tick')])
    assert result.state['Balance']['n'] == 1
    assert result.state['Lead']['visits'] == 1


@pytest.mark.parametrize('selector', [
    '{ Missing as X }', '{ Counter as Same, Visitor as Same }',
    '{ Counter as Lead, Counter as Lead }', '{}',
])
def test_invalid_named_import_bindings_fail_closed(tmp_path, selector):
    from funnelscript.compiler.world_ast import WorldTypeError
    (tmp_path / 'bundle.fnls').write_text('world Lib { entity Counter {} agent Visitor {} }')
    source = tmp_path / 'entry.fnls'
    source.write_text(f'world W {{ import "bundle.fnls" {selector}; }}')
    with pytest.raises((ParserError, WorldTypeError)):
        Parser.from_file(source)


def test_selective_named_import_only_exposes_requested_owner(tmp_path):
    (tmp_path / 'lib.fnls').write_text('world Lib { entity A {} agent B {} }')
    path = tmp_path / 'entry.fnls'
    path.write_text('world W { import "lib.fnls" { B }; }')
    result = Parser.from_file(path)
    assert [(d.kind, d.name) for d in result.declarations] == [('agent', 'B')]


def test_named_import_transitive_cycle_and_escape_still_rejected(tmp_path):
    (tmp_path / 'a.fnls').write_text('world A { import "b.fnls" { X }; entity A1 {} }')
    (tmp_path / 'b.fnls').write_text('world B { import "a.fnls" { A1 as X }; entity X {} }')
    path = tmp_path / 'root.fnls'
    path.write_text('world Root { import "a.fnls" { X }; }')
    with pytest.raises(ParserError, match='Cyclic'):
        Parser.from_file(path)
    for unsafe in ('../outside.fnls', '/tmp/outside.fnls'):
        path.write_text(f'world W {{ import "{unsafe}" {{ A }}; }}')
        with pytest.raises(ParserError, match='path'):
            Parser.from_file(path)
    outside = tmp_path.parent / 'outside-007g.fnls'
    outside.write_text('world W { entity A {} }')
    link = tmp_path / 'symlink-007g.fnls'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Symlink unsupported')
    path.write_text('world W { import "symlink-007g.fnls" { A }; }')
    with pytest.raises(ParserError, match='escapes'):
        Parser.from_file(path)

"""Phase 007G RED: deterministic named imports from multiple exports."""
import pytest
from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.runtime.world_executor import WorldExecutor


def test_explicit_named_import_selects_and_renames_multi_export(tmp_path):
    (tmp_path / 'bundle.fnl').write_text('''world Reuse {
      entity Counter { state n: int = 0; rule Up on event Tick { transition n = n + 1; } }
      agent Visitor { state visits: int = 0; rule Up on event Tick { transition visits = visits + 1; } }
      entity Hidden { state private: int = 9; }
    }''')
    path = tmp_path / 'main.fnl'
    path.write_text('world W { import "bundle.fnl" { Counter as Balance, Visitor as Lead }; }')
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
    (tmp_path / 'bundle.fnl').write_text('world Lib { entity Counter {} agent Visitor {} }')
    source = tmp_path / 'entry.fnl'
    source.write_text(f'world W {{ import "bundle.fnl" {selector}; }}')
    with pytest.raises((ParserError, WorldTypeError)):
        Parser.from_file(source)


def test_selective_named_import_only_exposes_requested_owner(tmp_path):
    (tmp_path / 'lib.fnl').write_text('world Lib { entity A {} agent B {} }')
    path = tmp_path / 'entry.fnl'
    path.write_text('world W { import "lib.fnl" { B }; }')
    result = Parser.from_file(path)
    assert [(d.kind, d.name) for d in result.declarations] == [('agent', 'B')]


def test_named_import_transitive_cycle_and_escape_still_rejected(tmp_path):
    (tmp_path / 'a.fnl').write_text('world A { import "b.fnl" { X }; entity A1 {} }')
    (tmp_path / 'b.fnl').write_text('world B { import "a.fnl" { A1 as X }; entity X {} }')
    path = tmp_path / 'root.fnl'
    path.write_text('world Root { import "a.fnl" { X }; }')
    with pytest.raises(ParserError, match='Cyclic'):
        Parser.from_file(path)
    for unsafe in ('../outside.fnl', '/tmp/outside.fnl'):
        path.write_text(f'world W {{ import "{unsafe}" {{ A }}; }}')
        with pytest.raises(ParserError, match='path'):
            Parser.from_file(path)
    outside = tmp_path.parent / 'outside-007g.fnl'
    outside.write_text('world W { entity A {} }')
    link = tmp_path / 'symlink-007g.fnl'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Symlink unsupported')
    path.write_text('world W { import "symlink-007g.fnl" { A }; }')
    with pytest.raises(ParserError, match='escapes'):
        Parser.from_file(path)

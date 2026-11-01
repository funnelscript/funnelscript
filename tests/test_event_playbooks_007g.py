"""Phase 007G RED: versioned file and inline event execution parity."""
import json
from funnelscript.cli import run_world_command


def test_versioned_file_playbook_equals_inline_events(tmp_path, capsys):
    source = tmp_path / 'run.fnl'
    source.write_text('world W { entity E { state n: int = 0; rule Up on event Tick { transition n = n + 1; } } }')
    path = tmp_path / 'events.json'
    entries = [{'name': 'E.Tick', 'time': 2, 'payload': {}},
               {'name': 'E.Tick', 'time': 1, 'payload': {}}]
    path.write_text(json.dumps({'schema': 'funnelscript-event-playbook-v1', 'events': entries}))
    assert run_world_command(str(source), [], events_file=str(path), seed=29) == 0
    file_result = json.loads(capsys.readouterr().out)
    assert run_world_command(str(source), [json.dumps(e) for e in entries], seed=29) == 0
    assert json.loads(capsys.readouterr().out) == file_result
    assert file_result['state']['E']['n'] == 2


import pytest
from funnelscript.cli import _load_event_playbook


@pytest.mark.parametrize('body', [
    b'{', b'\xff', b'{"schema":"not-supported","events":[]}',
    b'{"schema":"funnelscript-event-playbook-v1","events":[],"unexpected":1}',
    b'{"schema":"funnelscript-event-playbook-v1","events":[],"events":[]}',
    b'{"schema":"funnelscript-event-playbook-v1","events":[{"name":"E.Tick","time":0,"priority":false}]}',
    b'{"schema":"funnelscript-event-playbook-v1","events":[{"name":"E.Tick","time":-1}]}',
    b'{"schema":"funnelscript-event-playbook-v1","events":[{"name":"E.Tick","time":0,"extra":5}]}',
])
def test_playbook_invalid_records_fail_closed(tmp_path, body):
    path = tmp_path / 'bad.json'
    path.write_bytes(body)
    with pytest.raises((ValueError, TypeError, UnicodeError)):
        _load_event_playbook(str(path))


def test_playbook_bounded_size_and_count(tmp_path):
    path = tmp_path / 'events.json'
    path.write_bytes(b' ' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='1 MiB'):
        _load_event_playbook(str(path))
    path.write_text(json.dumps({'schema': 'funnelscript-event-playbook-v1',
                                'events': [{}] * 10001}))
    with pytest.raises(ValueError, match='count'):
        _load_event_playbook(str(path))


def test_events_file_and_inline_event_cannot_mix(tmp_path, capsys):
    source = tmp_path / 'run.fnl'
    source.write_text('world W { entity E {} }')
    path = tmp_path / 'events.json'
    path.write_text('{"schema":"funnelscript-event-playbook-v1","events":[]}')
    assert run_world_command(str(source), ['E.Tick@0'], events_file=str(path)) == 1
    assert 'mutually exclusive' in capsys.readouterr().err


def test_missing_file_returns_controlled_error(tmp_path, capsys):
    source = tmp_path / 'run.fnl'
    source.write_text('world W { entity E {} }')
    assert run_world_command(str(source), [], events_file=str(tmp_path / 'absent.json')) == 1
    assert 'World execution error' in capsys.readouterr().err


def test_playbook_wrong_payload_type_rejected_by_existing_world_validation(tmp_path, capsys):
    source = tmp_path / 'run.fnl'
    source.write_text('world W { entity E { event Tick(count: int); } }')
    path = tmp_path / 'events.json'
    path.write_text(json.dumps({'schema':'funnelscript-event-playbook-v1',
                                'events':[{'name':'E.Tick','time':0,'payload':{'count':'wrong'}}]}))
    assert run_world_command(str(source), [], events_file=str(path)) == 1
    assert 'World execution error' in capsys.readouterr().err


def test_actual_cli_events_file_matches_documented_fixture(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([
        sys.executable, '-m', 'funnelscript.cli', 'run-world',
        str(root / 'examples/phase007g_world.fnl'),
        '--events-file', str(root / 'examples/phase007g_events.json'), '--seed', '42',
    ], capture_output=True, text=True, check=True, cwd=tmp_path)
    assert json.loads(result.stdout)['state'] == {'Balance': {'count': 9}, 'Lead': {'visits': 6}}

"""Phase 007G RED: compositional arithmetic preserves typed snapshot execution."""
import pytest
from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor, WorldExecutionError


def world(tmp_path, expression):
    path = tmp_path / 'expr.fnl'
    path.write_text('''world W { entity Calc {
      state a: int = 20; state b: int = 6; state c: int = 2;
      state result: int = 0;
      rule Compute on event Tick { transition result = %s; }
    }}''' % expression)
    return Parser.from_file(path)


def test_nested_precedence_and_left_associativity(tmp_path):
    for expression, expected in [('a - b - c', 12), ('a - b * c', 8),
                                 ('(a - b) * c', 28), ('(a + b) * (c + 1)', 78),
                                 ('a * b + c', 122), ('a - (b - c)', 16)]:
        result = WorldExecutor(world(tmp_path, expression)).run([Event(0, 'Calc.Tick')])
        assert result.state['Calc']['result'] == expected


@pytest.mark.parametrize(('expression', 'message'), [
    ('a + unknown', 'Unknown state reference'),
    ('a / 0', 'Division by literal zero'),
    ('a + 1.0', 'Type mismatch'),
    ('a + true', 'numeric operands'),
])
def test_invalid_expressions_fail_static_type_check(tmp_path, expression, message):
    from funnelscript.compiler.world_ast import WorldTypeError
    with pytest.raises(WorldTypeError, match=message):
        world(tmp_path, expression)


def test_runtime_zero_divisor_fails_without_mutating_prior_world_snapshot(tmp_path):
    source = tmp_path / 'runtime.fnl'
    source.write_text('''world W { entity Calc {
      state numerator: int = 12; state denominator: int = 0;
      state ratio: float = 1.0; state other: int = 5;
      rule Calc on event Tick {
        transition other = other + 1;
        transition ratio = numerator / denominator;
      }
    }}''')
    subject = WorldExecutor(Parser.from_file(source))
    before = subject.initial_state()
    with pytest.raises(WorldExecutionError, match='Division by zero'):
        subject.advance(before, Event(0, 'Calc.Tick'))
    assert before['Calc'] == {'numerator': 12, 'denominator': 0, 'ratio': 1.0, 'other': 5}


def test_too_deep_expression_is_rejected_before_runtime(tmp_path):
    expression = '(' * 28 + 'a' + ')' * 28
    from funnelscript.parser import ParserError
    with pytest.raises(ParserError, match='depth limit'):
        world(tmp_path, expression)


def test_state_and_payload_expression_and_source_round_trip(tmp_path):
    source = tmp_path / 'payload.fnl'
    source.write_text('''world W { agent Calc {
      state base: float = 2.0; state multiplier: float = 3.0;
      state adjusted: float = 0.0;
      event Tick(increment: float, charge: float);
      rule Calc on event Tick {
        transition adjusted = (base + payload.increment) * (multiplier - payload.charge);
      }
    }}''')
    model = Parser.from_file(source)
    from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker
    rebuilt = WorldAST.model_validate_json(model.model_dump_json())
    WorldTypeChecker.check(rebuilt)
    event = Event(0, 'Calc.Tick', {'increment': 4.0, 'charge': 1.0})
    expected = {'base': 2.0, 'multiplier': 3.0, 'adjusted': 12.0}
    assert WorldExecutor(model).run([event]).state['Calc'] == expected
    assert WorldExecutor(rebuilt).run([event]).state['Calc'] == expected


def test_snapshot_atomic_composable_transition(tmp_path):
    source = tmp_path / 'snapshot.fnl'
    source.write_text('''world W { entity E {
      state a: int = 2; state b: int = 3;
      rule Swap on event Tick {
        transition a = a + b * 2;
        transition b = (a + b) * 2;
      }
    }}''')
    before = WorldExecutor(Parser.from_file(source)).initial_state()
    after = WorldExecutor(Parser.from_file(source)).advance(before, Event(0, 'E.Tick'))
    assert before['E'] == {'a': 2, 'b': 3}
    assert after['E'] == {'a': 8, 'b': 10}


def test_composable_emitted_payload_reuses_snapshot_and_event_calendar(tmp_path):
    source = tmp_path / 'emission.fnl'
    source.write_text('''world W { entity E {
      state n: int = 2; state total: int = 0;
      event Finish(amount: int);
      rule Start on event Begin {
        transition n = n + 10;
        emit Finish(amount = (n + 1) * 3) after 1;
      }
      rule Final on event Finish { transition total = total + payload.amount; }
    }}''')
    subject = WorldExecutor(Parser.from_file(source))
    first = subject.run([Event(0, 'E.Begin')], seed=11)
    second = subject.run([Event(0, 'E.Begin')], seed=11)
    assert first == second
    assert first.state['E'] == {'n': 12, 'total': 9}
    assert [event.name for event in first.processed] == ['E.Begin', 'E.Finish']

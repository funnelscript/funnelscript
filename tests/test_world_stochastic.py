"""H-S1 through H-S4: typed draws from the event kernel's seeded RNG."""

import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.compiler.world_ast import WorldTypeError
from funnelscript.runtime.world_executor import WorldExecutor, WorldExecutionError


WORLD = """world Experiment {
  agent Visitor {
    state probability: float = 0.4;
    state converted: bool = false;
    state score: float = 0.0;
    event View(p: float);
    rule React on event View {
      transition converted = sample bernoulli(payload.p);
      transition score = sample uniform(0.0, 10.0);
    }
  }
}
"""


def runner(tmp_path, source=WORLD):
    source_path = tmp_path / "stochastic.fnl"
    source_path.write_text(source, encoding="utf-8")
    return WorldExecutor(Parser.from_file(source_path))


def test_sampling_produces_typed_nodes(tmp_path):
    rules = runner(tmp_path).world.declarations[0].rules
    expressions = [transition.expr for transition in rules[0].transitions]
    assert [(expr.kind, expr.distribution) for expr in expressions] == [
        ("sample", "bernoulli"), ("sample", "uniform")
    ]
    assert [item.kind for item in expressions[0].arguments] == ["payload_field"]
    assert [item.kind for item in expressions[1].arguments] == ["literal", "literal"]


def test_same_seed_replays_exactly_and_consumes_one_draw_per_operator(tmp_path):
    subject = runner(tmp_path)
    events = [Event(0, "Visitor.View", payload={"p": 0.5})]
    one = subject.run(events, seed=21)
    two = subject.run(events, seed=21)
    rng = random.Random(21)
    expected_conversion = rng.random() < 0.5
    expected_score = 10.0 * rng.random()
    assert one == two
    assert one.state["Visitor"]["converted"] is expected_conversion
    assert one.state["Visitor"]["score"] == expected_score


def test_draw_order_follows_transition_order_not_field_order(tmp_path):
    source = """world W { agent A {
      state a: float = 0.0;
      state b: float = 0.0;
      rule R on event Tick {
        transition b = sample uniform(0.0, 1.0);
        transition a = sample uniform(0.0, 1.0);
      }
    } }"""
    state = runner(tmp_path, source).run([Event(0, "A.Tick")], seed=13).state["A"]
    rng = random.Random(13)
    rng = random.Random(13)
    expected_b, expected_a = rng.random(), rng.random()
    assert state == {"a": expected_a, "b": expected_b}


def test_false_guard_never_consumes_rng(tmp_path):
    source = """world W { agent A {
      state enabled: bool = false;
      state outcome: float = 0.0;
      rule Skip on event Skip when (enabled == true) {
        transition outcome = sample uniform(0.0, 1.0);
      }
      rule Run on event Tick {
        transition outcome = sample uniform(0.0, 1.0);
      }
    } }"""
    subject = runner(tmp_path, source)
    with_skip = subject.run([Event(0, "A.Skip"), Event(1, "A.Tick")], seed=44)
    without_skip = subject.run([Event(1, "A.Tick")], seed=44)
    assert with_skip.state == without_skip.state
    assert without_skip.state["A"]["outcome"] == random.Random(44).random()


def test_degenerate_probabilities_and_uniform_intervals_still_draw_once(tmp_path):
    source = """world W { agent A {
      state impossible: bool = true;
      state certain: bool = false;
      state constant: float = 0.0;
      state next: float = 0.0;
      rule R on event Tick {
        transition impossible = sample bernoulli(0.0);
        transition certain = sample bernoulli(1.0);
        transition constant = sample uniform(7.0, 7.0);
        transition next = sample uniform(0.0, 1.0);
      }
    } }"""
    state = runner(tmp_path, source).run([Event(0, "A.Tick")], seed=3).state["A"]
    rng = random.Random(3)
    for _ in range(3):
        rng.random()
    assert state == {
        "impossible": False, "certain": True, "constant": 7.0,
        "next": rng.random()
    }


def test_dynamic_state_parameter_reads_pre_event_snapshot(tmp_path):
    source = """world W { agent A {
      state p: float = 0.0;
      state outcome: bool = false;
      event Tick(p: float);
      rule R on event Tick {
        transition p = payload.p;
        transition outcome = sample bernoulli(p);
      }
    } }"""
    result = runner(tmp_path, source).run(
        [Event(0, "A.Tick", payload={"p": 1.0})], seed=4
    )
    assert result.state["A"] == {"p": 1.0, "outcome": False}


def test_dynamic_probability_validated_before_consuming_rng(tmp_path):
    source = """world W { agent A {
      state p: float = 0.0;
      state outcome: bool = false;
      event Tick(p: float);
      rule R on event Tick {
        transition outcome = sample bernoulli(payload.p);
      }
    } }"""
    subject = runner(tmp_path, source)
    for p in (-0.1, 1.1, float("nan"), float("inf")):
        with pytest.raises((WorldExecutionError, ValueError), match="(probability|finite)"):
            subject.run([Event(0, "A.Tick", payload={"p": p})], seed=4)


@pytest.mark.parametrize("bounds", [(-2.0, -3.0), (float("-inf"), 1.0), (-1e308, 1e308)])
def test_dynamic_uniform_invalid_bounds_are_rejected(tmp_path, bounds):
    source = """world W { agent A {
      state x: float = 0.0;
      event Tick(lo: float, hi: float);
      rule R on event Tick {
        transition x = sample uniform(payload.lo, payload.hi);
      }
    } }"""
    subject = runner(tmp_path, source)
    with pytest.raises((WorldExecutionError, ValueError), match="(bounds|finite|span)"):
        subject.run(
            [Event(0, "A.Tick", payload={"lo": bounds[0], "hi": bounds[1]})]
        )


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("transition done = sample bernoulli(2.0);", "probability"),
        ("transition done = sample bernoulli(-0.01);", "probability"),
        ("transition done = sample bernoulli(1);", "float"),
        ("transition done = sample bernoulli(true);", "float"),
        ("transition done = sample uniform(1.0, 0.0);", "bounds"),
        ("transition done = sample uniform(0.0, 1.0);", "Type mismatch"),
        ("transition done = sample unknown(0.5);", "distribution"),
        ("transition done = sample bernoulli();", "argument"),
        ("transition done = sample bernoulli(0.5, 0.2);", "argument"),
    ],
)
def test_invalid_source_is_rejected_before_execution(tmp_path, statement, message):
    source = f"""world W {{ agent A {{
      state done: bool = false;
      rule R on event Tick {{ {statement} }}
    }} }}"""
    with pytest.raises((ParserError, WorldTypeError), match=message):
        runner(tmp_path, source)


def test_sampling_in_emitted_event_argument_is_not_supported_yet(tmp_path):
    source = """world W { agent A {
      event Ping(flag: bool);
      rule R on event Tick {
        emit Ping(flag = sample bernoulli(0.5)) after 1;
      }
      rule Receive on event Ping {}
    } }"""
    with pytest.raises((ParserError, WorldTypeError), match="(transition|sampling)"):
        runner(tmp_path, source)


def test_direct_advance_requires_explicit_rng_for_sampled_rule(tmp_path):
    subject = runner(tmp_path)
    incoming = Event(0, "Visitor.View", payload={"p": 0.5})
    with pytest.raises(WorldExecutionError, match="RNG"):
        subject.advance(subject.initial_state(), incoming)
    state = subject.advance(subject.initial_state(), incoming, rng=random.Random(21))
    assert state["Visitor"]["converted"] is (random.Random(21).random() < 0.5)


def test_non_stochastic_world_remains_deterministic(tmp_path):
    source = """world W { entity E {
      state n: int = 0;
      rule R on event Tick { transition n = n + 1; }
    } }"""
    subject = runner(tmp_path, source)
    assert subject.advance(subject.initial_state(), Event(0, "E.Tick"))["E"]["n"] == 1
    assert subject.run([Event(0, "E.Tick")], seed=1).state == subject.run(
        [Event(0, "E.Tick")], seed=999
    ).state


def test_rejected_dynamic_probability_preserves_caller_rng_state(tmp_path):
    source = """world W { agent A {
      state result: bool = false;
      event Draw(p: float);
      rule R on event Draw { transition result = sample bernoulli(payload.p); }
    } }"""
    subject = runner(tmp_path, source)
    rng = random.Random(777)
    before = rng.getstate()
    with pytest.raises(WorldExecutionError, match="probability"):
        subject.advance(
            subject.initial_state(),
            Event(0, "A.Draw", payload={"p": 1.01}),
            rng=rng,
        )
    assert rng.getstate() == before


def test_emission_reads_pre_sample_state_not_random_update(tmp_path):
    source = """world W { agent A {
      state converted: bool = false;
      state observed: bool = true;
      event Observe(previous: bool);
      rule Begin on event Start {
        transition converted = sample bernoulli(1.0);
        emit Observe(previous = converted) after 1;
      }
      rule End on event Observe { transition observed = payload.previous; }
    } }"""
    result = runner(tmp_path, source).run([Event(0, "A.Start")], seed=8)
    assert result.state["A"] == {"converted": True, "observed": False}
    assert result.processed[1].payload == {"previous": False}


def test_packaged_cli_replays_seeded_stochastic_world():
    project_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable, "-m", "funnelscript.cli", "run-world",
        str(project_root / "examples" / "stochastic_world.fnl"),
        "--event",
        '{"name":"Shopper.Impression","time":0,"payload":{"conversion_probability":0.25}}',
        "--seed", "42",
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    result = json.loads(first.stdout)
    expected_rng = random.Random(42)
    expected_conversion = expected_rng.random() < 0.25
    expected_score = expected_rng.random()
    assert result["state"]["Shopper"] == {
        "converted": expected_conversion, "engagement_score": expected_score
    }

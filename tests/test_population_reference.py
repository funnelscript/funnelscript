"""Phase 007 STOP witness: the existing World RNG is not a keyed population RNG.

Do not mistake these boundary tests for a population conservation or metric
oracle. See research spec/population-reference-v0.md, P-RNG-ORDER-1.
"""

import json
from pathlib import Path

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor


ROOT = Path(__file__).parent / "fixtures" / "population-reference"
CASE = json.loads((ROOT / "order-coupling.json").read_text(encoding="utf-8"))


def test_existing_world_replays_pinned_first_order_golden():
    executor = WorldExecutor(Parser.from_file(ROOT / "order-coupling.fnl"))
    events = [Event(CASE["event_time"], name) for name in CASE["first"]]
    state = executor.run(events, seed=CASE["seed"]).state
    assert state == {
        name: {"draw": CASE["expected_first"][name]} for name in ("A", "B")
    }
    assert state == executor.run(events, seed=CASE["seed"]).state


def test_existing_world_draws_are_tied_to_event_order_not_agent_identity():
    executor = WorldExecutor(Parser.from_file(ROOT / "order-coupling.fnl"))
    first = executor.run(
        [Event(CASE["event_time"], name) for name in CASE["first"]],
        seed=CASE["seed"],
    ).state
    reversed_order = executor.run(
        [Event(CASE["event_time"], name) for name in CASE["reversed"]],
        seed=CASE["seed"],
    ).state
    assert reversed_order == {
        name: {"draw": CASE["expected_reversed"][name]} for name in ("A", "B")
    }
    assert first["A"]["draw"] != reversed_order["A"]["draw"]
    assert first["B"]["draw"] != reversed_order["B"]["draw"]

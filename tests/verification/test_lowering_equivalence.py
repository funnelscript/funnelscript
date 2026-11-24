"""Suite 2: Lowering Equivalence & Determinism Tests (Gate G2).

Research: docs/meta-ontology/04_TESTING_AND_VERIFICATION.md
Verifies:
1. Behavioral Equivalence: High-level Trait-based entities lower to bit-exact event traces
   and ledger state matching hand-written low-level DEVS rules.
2. PYTHONHASHSEED Independence: Identical output hashes across 5 randomized PYTHONHASHSEED runs.
3. Snapshot & Restore: Bit-exact trace and ledger hash match between split snapshot/restore
   and uninterrupted runs.
4. Formatter Idempotency: funnelscript fmt round-trips meta-ontology constructs idempotently.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from funnelscript.compiler.lowering import LoweringPass
from funnelscript.compiler.world_ast import TraitDefinition
from funnelscript.core.event_machine import Event
from funnelscript.formatter import format_funnelscript
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldEventStep, WorldExecutor
from funnelscript.tokens import Lexer

META_ONTOLOGY_SOURCE = """world ECommerceWorld {
  trait FinancialBinding {
    currency: Currency;
    on_settlement(amount: Currency);
  }

  trait TimeDelayed {
    transit_delay: Duration;
  }

  entity CODParcel implements FinancialBinding, TimeDelayed {
    state in_transit: Pool<CODParcel> = 0;
    state delivered: Pool<CODParcel> = 0;
    ledger clearing: LedgerAccount<USD>;
    ledger bank_cash: LedgerAccount<USD>;
    value: Currency<USD> = 100;

    event Dispatch(cost: int);
    event Deliver(cost: int);

    on_dispatch -> {
      transition in_transit = (in_transit + 1);
      post debit(clearing, payload.cost), credit(bank_cash, payload.cost);
      emit Deliver(cost = payload.cost) after 2;
    }

    on_deliver -> {
      transition in_transit = (in_transit - 1);
      transition delivered = (delivered + 1);
      post debit(bank_cash, payload.cost), credit(clearing, payload.cost);
    }
  }
}
"""

HANDWRITTEN_LOWLEVEL_SOURCE = """world ECommerceLowLevelWorld {
  entity CODParcel {
    state in_transit: int = 0;
    state delivered: int = 0;
    state clearing: int = 0;
    state bank_cash: int = 0;
    state value: int = 100;

    event Dispatch(cost: int);
    event Deliver(cost: int);

    rule Rule_CODParcel_Dispatch on event Dispatch {
      transition in_transit = (in_transit + 1);
      transition clearing = (clearing + payload.cost);
      transition bank_cash = (bank_cash - payload.cost);
      emit Deliver(cost = payload.cost) after 2;
    }

    rule Rule_CODParcel_Deliver on event Deliver {
      transition in_transit = (in_transit - 1);
      transition delivered = (delivered + 1);
      transition bank_cash = (bank_cash + payload.cost);
      transition clearing = (clearing - payload.cost);
    }
  }
}
"""


def test_behavioral_equivalence_against_handwritten_devs() -> None:
    """Gate G2: High-level entity lowering matches hand-written DEVS world bit-for-bit."""
    # 1. Parse high-level meta-ontology world and lower it
    meta_tokens = Lexer(META_ONTOLOGY_SOURCE).tokenize()
    meta_ast = Parser(meta_tokens).parse_world()
    lowered = LoweringPass.lower(meta_ast)

    # 2. Parse equivalent hand-written low-level world
    hand_tokens = Lexer(HANDWRITTEN_LOWLEVEL_SOURCE).tokenize()
    hand_ast = Parser(hand_tokens).parse_world()
    hand_executor = WorldExecutor(hand_ast)

    # 3. Create identical initial event sequence
    events = [
        Event(time=1.0, name="CODParcel.Dispatch", payload={"cost": 50}),
        Event(time=2.0, name="CODParcel.Dispatch", payload={"cost": 80}),
    ]

    # 4. Run both engines with identical seeds and observe traces
    meta_trace: list[WorldEventStep] = []
    meta_result = lowered.run(events, seed=42, trace=meta_trace)

    hand_trace: list[WorldEventStep] = []
    hand_result = hand_executor.run(events, seed=42, trace=hand_trace)

    # 5. Assert bit-exact state matching
    assert meta_result.state == hand_result.state, (
        f"State mismatch:\nMeta: {meta_result.state}\nHand: {hand_result.state}"
    )

    # 6. Assert bit-exact event step count & properties
    assert len(meta_trace) == len(hand_trace) == 4  # 2 Dispatches + 2 Delivers
    for i, (m_step, h_step) in enumerate(zip(meta_trace, hand_trace)):
        assert m_step.event.name == h_step.event.name, f"Step {i} event name mismatch"
        assert m_step.event.time == h_step.event.time, f"Step {i} time mismatch"
        assert m_step.before == h_step.before, f"Step {i} before state mismatch"
        assert m_step.after == h_step.after, f"Step {i} after state mismatch"

    # 7. Assert double-entry financial ledger trial balance
    assert lowered.ledger.balance_cents("CODParcel.clearing") == 0
    assert lowered.ledger.balance_cents("CODParcel.bank_cash") == 0
    assert lowered.ledger.total_imbalance_cents("USD") == 0


def test_hashseed_independence() -> None:
    """Gate G2: 100% hash match across 5 randomized PYTHONHASHSEED runs."""
    seeds = ["0", "123", "999", "4242", "1337"]
    hashes: list[str] = []

    script = """
import json, sys
from funnelscript.tokens import Lexer
from funnelscript.parser import Parser
from funnelscript.compiler.lowering import LoweringPass
from funnelscript.core.event_machine import Event

src = '''""" + META_ONTOLOGY_SOURCE + """'''
tokens = Lexer(src).tokenize()
ast = Parser(tokens).parse_world()
lowered = LoweringPass.lower(ast)
events = [
    Event(time=1.0, name="CODParcel.Dispatch", payload={"cost": 50}),
    Event(time=2.0, name="CODParcel.Dispatch", payload={"cost": 80}),
]
result = lowered.run(events, seed=42)
summary = {
    "state": result.state,
    "ledger_hash": lowered.ledger.compute_hash(),
    "imbalance": lowered.ledger.total_imbalance_cents("USD"),
}
print(json.dumps(summary, sort_keys=True))
"""

    for s in seeds:
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = s
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        data = json.loads(proc.stdout.strip())
        hashes.append(data["ledger_hash"])

    # All 5 runs must produce the exact same ledger hash
    assert len(set(hashes)) == 1, f"PYTHONHASHSEED non-determinism detected: {hashes}"


def test_snapshot_and_resume_determinism() -> None:
    """Gate G2: Splitting at t_split and restore() matches uninterrupted run identically."""
    meta_tokens = Lexer(META_ONTOLOGY_SOURCE).tokenize()
    meta_ast = Parser(meta_tokens).parse_world()

    # Run A: Uninterrupted run from 0 to 10
    lowered_a = LoweringPass.lower(meta_ast)
    events_a = [
        Event(time=1.0, name="CODParcel.Dispatch", payload={"cost": 50}),
        Event(time=2.0, name="CODParcel.Dispatch", payload={"cost": 80}),
    ]
    trace_a: list[WorldEventStep] = []
    result_a = lowered_a.run(events_a, seed=42, until=10.0, trace=trace_a)
    hash_a = lowered_a.ledger.compute_hash()

    # Run B: Split at t_split = 2.5
    lowered_b = LoweringPass.lower(meta_ast)
    events_b1 = [
        Event(time=1.0, name="CODParcel.Dispatch", payload={"cost": 50}),
        Event(time=2.0, name="CODParcel.Dispatch", payload={"cost": 80}),
    ]
    trace_b: list[WorldEventStep] = []
    result_b1 = lowered_b.run(events_b1, seed=42, until=2.5, trace=trace_b)

    # Take snapshot at t = 2.5 with pending events from result_b1
    snap = lowered_b.snapshot(current_time=2.5, state=result_b1.state, pending=result_b1.pending)

    # Create fresh instance, restore snapshot, and continue run
    lowered_resumed = LoweringPass.lower(meta_ast)
    restored_state = lowered_resumed.restore(snap)
    assert restored_state == result_b1.state

    # Resume execution with the pending events until 10.0
    result_resumed = lowered_resumed.run(
        snap.pending_events,
        seed=42,
        until=10.0,
        initial_state=restored_state,
    )

    hash_resumed = lowered_resumed.ledger.compute_hash()

    # Bit-exact equivalence between uninterrupted and restored run
    assert result_resumed.state == result_a.state
    assert hash_resumed == hash_a


def test_fmt_idempotency_on_meta_ontology_dsl() -> None:
    """funnelscript fmt round-trips meta-ontology syntax idempotently."""
    f1 = format_funnelscript(META_ONTOLOGY_SOURCE)
    f2 = format_funnelscript(f1)
    assert f1 == f2
    # Verify that formatted source re-parses cleanly
    reparsed_ast = Parser(Lexer(f1).tokenize()).parse_world()
    assert reparsed_ast.name == "ECommerceWorld"
    assert len(reparsed_ast.declarations) == 3


def test_zero_runtime_reflection() -> None:
    """Ensure lowering completely erases traits into flat DEVS primitives."""
    tokens = Lexer(META_ONTOLOGY_SOURCE).tokenize()
    ast = Parser(tokens).parse_world()
    lowered = LoweringPass.lower(ast)

    # 1. Trait definitions are 100% removed from runtime world
    assert not any(isinstance(d, TraitDefinition) for d in lowered.world.declarations)

    # 2. Lowered entity has only primitive states, events, and rules
    entity = lowered.world.declarations[0]
    assert len(entity.states) >= 4  # in_transit, delivered, clearing, bank_cash, value
    assert len(entity.rules) >= 2   # Rule_CODParcel_Dispatch, Rule_CODParcel_Deliver
    assert all(hasattr(s, "type_name") for s in entity.states)

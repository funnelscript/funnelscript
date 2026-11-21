"""Cross-process reproducibility of .fnl World execution and linked finance.

Research: deterministic DEVS ordering, keyed per-agent PRNG, canonical SHA-256 audit.
Hypothesis: PYTHONHASHSEED changes neither causal World evidence nor finance.
Invariant: SHA256(world_trace), SHA256(audit_bytes), and ledger balances are fixed
for identical source, model seed, and events across independent Python processes.
"""

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

_REPLAY_SOURCE = """
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import (
    PopulationAgent, PopulationExecutor, WorldExecutor,
)
from funnelscript.stdlib import marketing

source = Path("tests/fixtures/population-reference/identity-rng.fnl")
agents = {
    f"agent-{i:04d}": PopulationAgent(
        f"agent-{i:04d}", f"cohort-{i // 10:03d}",
        "north" if i < 4 else "south",
    )
    for i in range(10)
}
# Deliberately allow process hash randomization to permute enrollment.
enrollment = tuple(set(agents))
events = {
    agent_id: (Event(1, "Visitor.Tick"),)
    for agent_id in enrollment
    if agent_id in {"agent-0000", "agent-0004", "agent-0005"}
}
population = PopulationExecutor(
    WorldExecutor(Parser.from_file(source)),
    [agents[agent_id] for agent_id in enrollment],
    seed=int(os.environ["FNL_MODEL_SEED"]), trial_id="trial-1",
    state_field="phase", states=("new", "terminal", "inactive"),
).run(events, trace=True)

policy = marketing.DeclaredSalePolicy(
    event_name="Visitor.Tick", state_field="phase",
    from_state="new", to_state="terminal",
    amount=Decimal("20.00"), currency="SAR",
    attribution_label="synthetic-campaign",
)
sales = marketing.recognize_sales(population, policy)

def action(tx, kind, day, amount, source_id=None):
    entry = marketing.LedgerEntry(
        "trial-1", tx, kind, day, Decimal(amount), "SAR", source_id,
    )
    return marketing.DeclaredFinancialAction(
        entry, "campaign-finance", f"permit-{tx}",
    )

actions = [
    action("ads", "ad_spend", 0, "20.00"),
    action("ops", "other_cost", 0, "5.00"),
]
for index, sale in enumerate(sales):
    actions.append(action(
        f"receipt-{index}", "settlement", 3, "10.00", sale.entry.tx_id,
    ))
actions.append(action("loss", "writeoff", 3, "5.00", sales[0].entry.tx_id))
posted = marketing.post_authorized_trial(
    population, sales, policy, actions=actions,
    cash_initial=Decimal("100.00"), settlement_delay=2, horizon=3,
)
audit = marketing.export_audit(population, policy, posted)
revision_cost = "2.75" if os.environ["FNL_REVISION_VARIANT"] == "0" else "3.75"
amendments = (
    action("rev-cost", "other_cost", 3, revision_cost),
    action("rev-receipt", "settlement", 3, "7.25", sales[1].entry.tx_id),
    action("rev-loss", "writeoff", 3, "2.25", sales[2].entry.tx_id),
)
# Deliberately deliver different permutations from separate Python processes.
revision_delivery = tuple(set(amendments))
revision = marketing.replay_audit(
    audit, population, policy, actions=revision_delivery,
)
revision_retries = marketing.replay_audit(
    audit, population, policy, actions=(*amendments, *amendments),
)
revision_audit = marketing.export_audit(population, policy, revision)
restored_revision = marketing.restore_audit(
    revision_audit, population, policy,
    expected_sha256=sha256(revision_audit).hexdigest(),
)
revised_balance = revision.ledger.evaluate()
world = {
    agent_id: {
        "state": population.results[agent_id].state,
        "steps": [asdict(step) for step in population.steps[agent_id]],
        "processed": [
            asdict(event) for event in population.results[agent_id].processed
        ],
        "pending": [
            asdict(event) for event in population.results[agent_id].pending
        ],
        "intents": [
            asdict(intent) for intent in population.results[agent_id].intents
        ],
    }
    for agent_id in sorted(population.results)
}
canonical_world = json.dumps(
    world, sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode("utf-8")
balance = posted.ledger.evaluate()
print(json.dumps({
    "enrollment_order": enrollment,
    "world_sha256": sha256(canonical_world).hexdigest(),
    "audit_sha256": sha256(audit).hexdigest(),
    "revision_sha256": sha256(revision_audit).hexdigest(),
    "revision_ingress_order": [item.entry.tx_id for item in revision_delivery],
    "revision_is_restorable": restored_revision == revision,
    "revision_retries_are_idempotent": revision_retries == revision,
    "revision_entries": len(revision.ledger.entries),
    "revision_cash": str(revised_balance.cash),
    "revision_receivables": str(revised_balance.receivables),
    "revision_writeoffs": str(revised_balance.writeoffs),
    "revision_profit": str(revised_balance.profit),
    "draws": {
        agent_id: world[agent_id]["state"]["Visitor"]["draw"]
        for agent_id in sorted(events)
    },
    "recognized_sales": len(sales),
    "cash": str(balance.cash),
    "receivables": str(balance.receivables),
    "recognized_revenue": str(balance.recognized_revenue),
}, sort_keys=True))
"""


def _run_replay(hash_seed: int, model_seed: int, *, revision_variant: int = 0) -> dict:
    env = {
        **os.environ,
        "PYTHONHASHSEED": str(hash_seed),
        "FNL_MODEL_SEED": str(model_seed),
        "FNL_REVISION_VARIANT": str(revision_variant),
        "PYTHONPATH": os.pathsep.join(sys.path),
    }
    run = subprocess.run(
        [sys.executable, "-c", _REPLAY_SOURCE],
        text=True, capture_output=True, check=False, timeout=30,
        env=env, cwd=Path(__file__).resolve().parents[2],
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_world_trace_draws_and_financial_audit_are_hashseed_independent():
    outputs = [_run_replay(seed, model_seed=11) for seed in (0, 1, 7, 79, 999)]
    enrollment_orders = {tuple(item.pop("enrollment_order")) for item in outputs}
    revision_orders = {tuple(item.pop("revision_ingress_order")) for item in outputs}
    assert len(enrollment_orders) > 1
    assert len(revision_orders) > 1
    assert outputs == [outputs[0]] * 5
    result = outputs[0]
    assert result["recognized_sales"] == 3
    assert (
        Decimal(result["cash"]),
        Decimal(result["receivables"]),
        Decimal(result["recognized_revenue"]),
    ) == (Decimal(105), Decimal(25), Decimal(60))
    assert all(len(result[key]) == 64 for key in ("world_sha256", "audit_sha256"))
    assert len(set(result["draws"].values())) == 3


def test_changed_model_seed_changes_world_draws_not_hashseed_invariant():
    original = _run_replay(0, model_seed=11)
    changed = _run_replay(0, model_seed=12)
    assert original["draws"] != changed["draws"]
    assert original["world_sha256"] != changed["world_sha256"]
    assert changed["recognized_sales"] == original["recognized_sales"] == 3


def test_authorized_financial_revision_is_hashseed_independent_and_balanced():
    """External journal ordering cannot affect canonical financial replay.

    Anchor: deterministic append-only financial event sourcing.
    H: revised audit bytes are identical across five randomized Python hash seeds.
    Invariants: cash = initial - cash costs + settled receipts;
    receivables = recognized sales - settled receipts - writeoffs.
    """
    outputs = [_run_replay(seed, model_seed=11) for seed in (0, 1, 7, 79, 999)]
    orders = {tuple(item.pop("enrollment_order")) for item in outputs}
    revisions = {tuple(item.pop("revision_ingress_order")) for item in outputs}
    assert len(orders) > 1
    assert len(revisions) > 1
    assert outputs == [outputs[0]] * 5
    result = outputs[0]
    assert result["revision_sha256"] != result["audit_sha256"]
    assert result["revision_is_restorable"] is True
    assert result["revision_retries_are_idempotent"] is True
    assert result["revision_entries"] == 12
    assert Decimal(result["revision_cash"]) == Decimal("109.50")
    assert Decimal(result["revision_receivables"]) == Decimal("15.50")
    assert Decimal(result["revision_writeoffs"]) == Decimal("7.25")
    assert Decimal(result["revision_profit"]) == Decimal("25.00")
    assert Decimal(result["revision_cash"]) == (
        Decimal(100) - Decimal("27.75") + Decimal("37.25")
    )
    assert Decimal(result["revision_receivables"]) == (
        Decimal(60) - Decimal("37.25") - Decimal("7.25")
    )


def test_changed_external_revision_changes_audit_not_world_or_baseline():
    original = _run_replay(79, model_seed=11, revision_variant=0)
    changed = _run_replay(79, model_seed=11, revision_variant=1)
    assert original["world_sha256"] == changed["world_sha256"]
    assert original["audit_sha256"] == changed["audit_sha256"]
    assert original["revision_sha256"] != changed["revision_sha256"]
    assert Decimal(original["revision_cash"]) - Decimal(changed["revision_cash"]) == 1
    assert original["revision_receivables"] == changed["revision_receivables"]
    assert original["revision_writeoffs"] == changed["revision_writeoffs"]
    assert Decimal(original["revision_profit"]) - Decimal(changed["revision_profit"]) == 1

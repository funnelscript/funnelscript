"""Phase 007E cross-process recovery experiment: reproducible, single-writer only."""

from __future__ import annotations

from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import PopulationAgent, PopulationExecutor, WorldExecutor
from funnelscript.stdlib import marketing
from funnelscript.stdlib.marketing.provenance import PROVENANCE_VERSION

SOURCE = Path(__file__).resolve().parents[1] / "tests/fixtures/population-reference/identity-rng.fnl"
POLICY = marketing.DeclaredSalePolicy("Visitor.Tick", "phase", "new", "terminal", D(20), "SAR", "synthetic-campaign")


def execute_population(size: int, seed: int):
    agents = [PopulationAgent(f"agent-{i:04}", f"cohort-{i // 10:03}",
                              "north" if i % 10 < 4 else "south") for i in range(size)]
    runner = PopulationExecutor(WorldExecutor(Parser.from_file(SOURCE)), agents,
                                seed=seed, trial_id=f"trial-seed-{seed}",
                                state_field="phase", states=("new", "terminal", "inactive"))
    events = {a.agent_id: (Event(1, "Visitor.Tick"),) for i, a in enumerate(agents)
              if i % 10 in (0, 4, 5)}
    return runner.run(events, trace=True)


def external_actions(pop, sales, size: int):
    trial_id = pop.trial_id
    actions = [
        marketing.DeclaredFinancialAction(marketing.LedgerEntry(
            trial_id, "ads", "ad_spend", 0, D(size * 2), "SAR"), "finance", "auth-ads"),
        marketing.DeclaredFinancialAction(marketing.LedgerEntry(
            trial_id, "cost", "other_cost", 0, D(size) / 2, "SAR"), "finance", "auth-cost"),
    ]
    actions.extend(marketing.DeclaredFinancialAction(marketing.LedgerEntry(
        trial_id, f"pay-{i:04}", "settlement", 3, D(10), "SAR", sale.entry.tx_id),
        "finance", f"auth-pay-{i:04}") for i, sale in enumerate(sales))
    actions.append(marketing.DeclaredFinancialAction(marketing.LedgerEntry(
        trial_id, "loss", "writeoff", 3, D(5), "SAR", sales[0].entry.tx_id),
        "finance", "auth-loss"))
    return tuple(actions)


def check_oracle(linked, size: int) -> None:
    day1, day3 = linked.ledger.evaluate(until=1), linked.ledger.evaluate()
    assert (day1.cash, day1.receivables, day1.recognized_revenue, day1.settled_receipts) == (
        D(size) * D("7.5"), D(size) * D(6), D(size) * D(6), D(0))
    assert (day3.cash, day3.receivables, day3.profit, day3.writeoffs) == (
        D(size) * D("10.5"), D(size) * D(3) - 5, D(size) * D("3.5") - 5, D(5))


def restore_process(path: Path, size: int, seed: int, pinned: str) -> None:
    population = execute_population(size, seed)
    started = perf_counter()
    evidence = marketing.read_audit_checkpoint(path)
    restored = marketing.restore_audit(evidence, population, POLICY, expected_sha256=pinned)
    restoration = perf_counter() - started
    started = perf_counter()
    replayed = marketing.replay_audit(evidence, population, POLICY,
                                     actions=external_actions(population, marketing.recognize_sales(population, POLICY), size),
                                     expected_sha256=pinned)
    replay = perf_counter() - started
    check_oracle(restored, size)
    assert replayed == restored
    assert marketing.export_audit(population, POLICY, restored) == evidence
    print(json.dumps({"restoration_seconds": restoration, "replay_seconds": replay,
                      "recovered_actions": len(restored.financial_actions),
                      "recovered_entries": len(restored.ledger.entries),
                      "canonical_sha256": sha256(evidence).hexdigest(),
                      "cash": str(restored.ledger.evaluate().cash), "replay_agrees": True}))


def run(size: int, seed: int) -> dict:
    tracemalloc.start()
    overall_start = perf_counter()
    start = overall_start
    population = execute_population(size, seed)
    population_seconds = perf_counter() - start
    start = perf_counter()
    sales = marketing.recognize_sales(population, POLICY)
    actions = external_actions(population, sales, size)
    linked = marketing.post_authorized_trial(population, sales, POLICY, actions=actions,
                                              cash_initial=D(size * 10), settlement_delay=2, horizon=3)
    integration_seconds = perf_counter() - start
    check_oracle(linked, size)
    start = perf_counter()
    evidence = marketing.export_audit(population, POLICY, linked)
    serialize_seconds = perf_counter() - start
    start = perf_counter()
    with TemporaryDirectory(prefix="funnelscript-007e-") as tmp:
        path = Path(tmp) / "financial.audit"
        marketing.write_audit_checkpoint(path, evidence)
        pinned = sha256(evidence).hexdigest()
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--restore",
                                str(path), str(size), str(seed), pinned],
                               capture_output=True, text=True, check=True)
        restored = json.loads(child.stdout)
    persistence_and_process_seconds = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert restored["canonical_sha256"] == pinned
    assert restored["recovered_entries"] == len(linked.ledger.entries)
    assert restored["recovered_actions"] == len(actions)
    return {"population": size, "segments": 2, "seed": seed,
            "population_seconds": round(population_seconds, 6),
            "financial_seconds": round(integration_seconds, 6),
            "serialization_seconds": round(serialize_seconds, 6),
            "persistence_and_process_seconds": round(persistence_and_process_seconds, 6),
            "restoration_seconds_child": round(restored["restoration_seconds"], 6),
            "replay_seconds_child": round(restored["replay_seconds"], 6),
            "total_seconds": round(perf_counter() - overall_start, 6),
            "tracemalloc_peak_bytes_parent": peak, "sales": len(sales),
            "actions": len(actions), "entries": len(linked.ledger.entries),
            "audit_sha256": pinned, "audit_bytes": len(evidence),
            "cash": restored["cash"], "replay_agrees": restored["replay_agrees"]}


def main() -> None:
    if len(sys.argv) == 6 and sys.argv[1] == "--restore":
        restore_process(Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
        return
    runs = [run(size, seed) for size in (10, 100, 1000) for seed in (11, 29)]
    print(json.dumps({"python": sys.version, "os": platform.platform(),
                      "source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
                      "provenance_version": PROVENANCE_VERSION,
                      "audit_schema": marketing.AUDIT_SCHEMA,
                      "memory_kind": "parent tracemalloc traced allocations only",
                      "runs": runs}, indent=2))


if __name__ == "__main__":
    main()

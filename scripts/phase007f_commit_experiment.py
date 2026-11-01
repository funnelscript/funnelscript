"""Phase 007F independently reproducible six-case commit and restart experiment."""

from __future__ import annotations

from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc
from unittest.mock import patch

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import PopulationAgent, PopulationExecutor, WorldExecutor
from funnelscript.stdlib import marketing
from funnelscript.stdlib.marketing.provenance import PROVENANCE_VERSION

SOURCE = Path(__file__).resolve().parents[1] / "tests/fixtures/population-reference/identity-rng.fnl"
POLICY = marketing.DeclaredSalePolicy(
    "Visitor.Tick", "phase", "new", "terminal", D(20), "SAR", "synthetic-campaign"
)


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


def oracle(linked, size: int, *, written_off: bool) -> None:
    early, late = linked.ledger.evaluate(until=1), linked.ledger.evaluate()
    assert (early.cash, early.receivables, early.recognized_revenue) == (
        D(size) * D("7.5"), D(size) * D(6), D(size) * D(6))
    assert (late.cash, late.receivables, late.settled_receipts) == (
        D(size) * D("10.5"), D(size) * D(3) - (5 if written_off else 0),
        D(size) * D(3))
    assert late.profit == D(size) * D("3.5") - (5 if written_off else 0)
    assert late.writeoffs == (5 if written_off else 0)


def child_recovery(path: Path, receipt_file: Path, size: int, seed: int) -> None:
    started = perf_counter()
    population = execute_population(size, seed)
    evidence = marketing.FinancialCommitReceipt.from_bytes(receipt_file.read_bytes())
    restored, matched = marketing.recover_financial_checkpoint(
        path, population, POLICY, expected_receipt=evidence)
    recovery_seconds = perf_counter() - started
    start = perf_counter()
    sales = marketing.recognize_sales(population, POLICY)
    replayed = marketing.replay_audit(
        marketing.read_audit_checkpoint(path), population, POLICY,
        actions=external_actions(population, sales, size))
    replay_seconds = perf_counter() - start
    oracle(restored, size, written_off=True)
    assert replayed == restored
    assert evidence == matched
    print(json.dumps({"recovery_seconds_child": recovery_seconds,
                      "replay_seconds_child": replay_seconds,
                      "recovered_actions": len(restored.financial_actions),
                      "recovered_entries": len(restored.ledger.entries),
                      "receipt_id": matched.commit_id,
                      "cash": str(restored.ledger.evaluate().cash),
                      "receipt_verified": True, "replay_agrees": True}))


def run(size: int, seed: int) -> dict:
    tracemalloc.start()
    overall = perf_counter()
    start = perf_counter()
    population = execute_population(size, seed)
    population_seconds = perf_counter() - start
    start = perf_counter()
    sales = marketing.recognize_sales(population, POLICY)
    actions = external_actions(population, sales, size)
    baseline = marketing.post_authorized_trial(
        population, sales, POLICY, actions=actions[:-1], cash_initial=D(size * 10),
        settlement_delay=2, horizon=3)
    upgraded = marketing.post_authorized_trial(
        population, sales, POLICY, actions=actions, cash_initial=D(size * 10),
        settlement_delay=2, horizon=3)
    integration_seconds = perf_counter() - start
    oracle(baseline, size, written_off=False)
    oracle(upgraded, size, written_off=True)
    start = perf_counter()
    data = marketing.export_audit(population, POLICY, upgraded)
    serialization_seconds = perf_counter() - start
    with TemporaryDirectory(prefix="funnelscript-007f-") as tmp:
        path = Path(tmp) / "financial.audit"
        receipt_file = Path(tmp) / "receipt.json"
        start = perf_counter()
        one = marketing.commit_financial_checkpoint(path, population, POLICY, baseline)
        initial_publication_seconds = perf_counter() - start
        with patch("funnelscript.stdlib.marketing.audit.os.replace",
                   side_effect=OSError("fault before rename")):
            try:
                marketing.commit_financial_checkpoint(
                    path, population, POLICY, upgraded, expected_receipt=one)
                raise AssertionError("faulted publication was acknowledged")
            except marketing.CommitOutcomeUncertain:
                pass
        assert marketing.recover_financial_checkpoint(path, population, POLICY)[1] == one
        start = perf_counter()
        two = marketing.commit_financial_checkpoint(
            path, population, POLICY, upgraded, expected_receipt=one)
        publication_seconds = perf_counter() - start
        assert marketing.commit_financial_checkpoint(
            path, population, POLICY, upgraded, expected_receipt=two) == two
        receipt_file.write_bytes(two.to_bytes())
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--recover",
             str(path), str(receipt_file), str(size), str(seed)],
            capture_output=True, text=True, check=True)
        recovered = json.loads(child.stdout)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert recovered["receipt_id"] == two.commit_id
    assert recovered["recovered_actions"] == len(actions)
    assert recovered["recovered_entries"] == len(upgraded.ledger.entries)
    assert sha256(data).hexdigest() == two.audit_sha256
    return {
        "population": size, "segments": 2, "seed": seed,
        "population_seconds": round(population_seconds, 6),
        "financial_seconds": round(integration_seconds, 6),
        "serialization_seconds": round(serialization_seconds, 6),
        "initial_publication_seconds": round(initial_publication_seconds, 6),
        "commit_publication_seconds": round(publication_seconds, 6),
        "recovery_seconds_child": round(recovered["recovery_seconds_child"], 6),
        "replay_seconds_child": round(recovered["replay_seconds_child"], 6),
        "total_seconds": round(perf_counter() - overall, 6),
        "tracemalloc_peak_bytes_parent": peak,
        "sales": len(sales), "actions": len(actions),
        "entries": len(upgraded.ledger.entries),
        "audit_sha256": two.audit_sha256, "receipt_id": two.commit_id,
        "cash": recovered["cash"], "receipt_verified": True,
        "replay_agrees": True, "injected_rename_interruption_detected": True,
    }


def main() -> None:
    if len(sys.argv) == 6 and sys.argv[1] == "--recover":
        child_recovery(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
        return
    runs = [run(size, seed) for size in (10, 100, 1000) for seed in (11, 29)]
    print(json.dumps({
        "python": sys.version, "os": platform.platform(),
        "source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
        "commit_source_sha256": sha256(
            (Path(__file__).resolve().parents[1] /
             "src/funnelscript/stdlib/marketing/commit.py").read_bytes()).hexdigest(),
        "provenance_version": PROVENANCE_VERSION,
        "audit_schema": marketing.AUDIT_SCHEMA,
        "receipt_schema": marketing.RECEIPT_SCHEMA,
        "memory_kind": "parent tracemalloc allocations; excludes child process",
        "failure_model": "single writer, local atomic rename, external trusted receipt",
        "runs": runs,
    }, indent=2))


if __name__ == "__main__":
    main()

"""Bounded reproducible Phase 007D World-to-ledger integration measurement."""

from __future__ import annotations

from decimal import Decimal as D
from hashlib import sha256
import json
import platform
from pathlib import Path
import sys
from time import perf_counter
import tracemalloc

from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import PopulationAgent, PopulationExecutor, WorldExecutor
from funnelscript.stdlib import marketing
from funnelscript.stdlib.marketing.provenance import PROVENANCE_VERSION

SOURCE = Path(__file__).resolve().parents[1] / "tests/fixtures/population-reference/identity-rng.fnl"
POLICY = marketing.DeclaredSalePolicy("Visitor.Tick", "phase", "new", "terminal", D(20), "SAR", "synthetic-campaign")


def execute(size: int, seed: int) -> dict:
    trial_id = f"trial-seed-{seed}"
    tracemalloc.start()
    started = perf_counter()
    agents = [PopulationAgent(f"agent-{i:04}", f"cohort-{i // 10:03}",
               "north" if i % 10 < 4 else "south") for i in range(size)]
    runner = PopulationExecutor(WorldExecutor(Parser.from_file(SOURCE)), agents,
        seed=seed, trial_id=trial_id, state_field="phase", states=("new", "terminal", "inactive"))
    events = {a.agent_id: (Event(1, "Visitor.Tick"),) for i, a in enumerate(agents)
              if i % 10 in (0, 4, 5)}
    result = runner.run(events, trace=True)
    population_seconds = perf_counter() - started
    processing_started = perf_counter()
    sales = marketing.recognize_sales(result, POLICY)
    actions = [
        marketing.DeclaredFinancialAction(marketing.LedgerEntry(trial_id, "ads", "ad_spend", 0, D(size * 2), "SAR"), "finance", "auth-ads"),
        marketing.DeclaredFinancialAction(marketing.LedgerEntry(trial_id, "cost", "other_cost", 0, D(size) / 2, "SAR"), "finance", "auth-cost"),
    ]
    actions.extend(marketing.DeclaredFinancialAction(
        marketing.LedgerEntry(trial_id, f"pay-{i:04}", "settlement", 3, D(10), "SAR", sale.entry.tx_id),
        "finance", f"auth-pay-{i:04}") for i, sale in enumerate(sales))
    actions.append(marketing.DeclaredFinancialAction(
        marketing.LedgerEntry(trial_id, "loss", "writeoff", 3, D(5), "SAR", sales[0].entry.tx_id),
        "finance", "auth-loss"))
    linked = marketing.post_authorized_trial(result, sales, POLICY, actions=actions,
        cash_initial=D(size * 10), settlement_delay=2, horizon=3)
    first, final = linked.ledger.evaluate(until=1), linked.ledger.evaluate()
    financial_seconds = perf_counter() - processing_started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(result.segments["north"]) == size * 4 // 10
    assert len(set().union(*result.partitions.values())) == size
    assert len(sales) == size * 3 // 10
    assert len(linked.financial_actions) == 3 + len(sales)
    assert len(linked.ledger.entries) == 3 + 2 * len(sales)
    assert (first.cash, first.receivables, first.recognized_revenue, first.settled_receipts) == (
        D(size) * D("7.5"), D(size) * D(6), D(size) * D(6), D(0))
    assert (final.cash, final.receivables, final.profit, final.writeoffs) == (
        D(size) * D("10.5"), D(size) * D(3) - 5, D(size) * D("3.5") - 5, D(5))
    trace = [(s.provenance.agent_id, s.entry.tx_id) for s in linked.sales]
    journal = [(e.trial_id, e.tx_id, e.kind, e.day, str(e.amount), e.currency,
                e.source_tx_id) for e in linked.ledger.entries]
    evidence = sha256(json.dumps([trace, journal], separators=(",", ":")).encode()).hexdigest()
    return {"agents": size, "segments": 2, "seed": seed, "trial_id": trial_id,
        "population_seconds": round(population_seconds, 6),
        "financial_seconds": round(financial_seconds, 6),
        "total_seconds": round(population_seconds + financial_seconds, 6),
        "peak_traced_bytes": peak_bytes, "sales": len(sales),
        "authorized_external_actions": len(linked.financial_actions),
        "unique_financial_operations": len(linked.ledger.entries),
        "cash_day1": str(first.cash), "cash_day3": str(final.cash),
        "receivables_day3": str(final.receivables), "profit_day3": str(final.profit),
        "writeoff_day3": str(final.writeoffs), "trace_journal_sha256": evidence}


def main() -> None:
    runs = []
    for size in (10, 100, 1000):
        for seed in (11, 29):
            first = execute(size, seed)
            second = execute(size, seed)
            assert first["trace_journal_sha256"] == second["trace_journal_sha256"]
            first["deterministic_replay"] = True
            runs.append(first)
    print(json.dumps({"platform": platform.platform(), "python": sys.version,
        "fixture_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
        "provenance_version": PROVENANCE_VERSION,
        "rng_contract": "population-rng-v1/sha256-mt19937",
        "memory_type": "tracemalloc Python allocations (peak bytes)", "runs": runs}, indent=2))


if __name__ == "__main__":
    main()

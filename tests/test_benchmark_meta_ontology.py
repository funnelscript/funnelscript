"""Suite 6 Smoke Test: Verify benchmark_meta_ontology runs and passes Gate G6."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.benchmark_meta_ontology import run_benchmark


def test_meta_ontology_benchmark_gate_g6_smoke() -> None:
    """Smoke test ensuring zero-cost lowering abstraction executes cleanly with low memory footprint."""
    results = run_benchmark(num_events=5000)
    assert results["num_events"] == 5000
    assert results["mem_overhead_pct"] <= 5.0, (
        f"Memory overhead {results['mem_overhead_pct']:.2f}% exceeded 5.0% threshold"
    )
    # Verify high-throughput execution (> 10,000 events/sec) proving zero reflection in hot path
    lowered_eps = results["num_events"] / results["lowered_time_sec"]
    assert lowered_eps >= 10000, f"Lowered throughput {lowered_eps:,.0f} ev/s is below target"

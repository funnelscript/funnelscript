"""Measure the current EventMachine calendar and result retention, without changing it.

Research: spec/runtime-resource-envelope-v0.md, H-RQ1/H-RQ2/H-RT1.
Run one scenario per fresh process; timings are diagnostic, never CI thresholds.
"""

import argparse
import json
import platform
import resource
import sys
import time
import tracemalloc

from funnelscript.core.event_machine import Event, EventMachine, Transition


def run_scenario(scenario: str, count: int) -> dict[str, object]:
    def no_effect(state, event, rng):
        return Transition(state)

    def fanout(state, event, rng):
        return Transition(state, events=tuple(Event(1.0, "later") for _ in range(count)))

    reducer = fanout if scenario == "fanout" else no_effect
    if scenario == "fanout":
        inputs = (Event(0.0, "now"),)
    else:
        timestamp = 0.0 if scenario == "due" else 1.0
        inputs = (Event(timestamp, "sample") for _ in range(count))

    tracemalloc.start()
    start = time.perf_counter()
    result = EventMachine(reducer).run(
        0,
        inputs,
        seed=0,
        until=0.0 if scenario != "due" else None,
        max_events=count if scenario == "due" else 1,
    )
    elapsed = time.perf_counter() - start
    _, traced_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    expected_processed = count if scenario == "due" else int(scenario == "fanout")
    expected_pending = 0 if scenario == "due" else count
    if (len(result.processed), len(result.pending)) != (
        expected_processed,
        expected_pending,
    ):
        raise AssertionError("unexpected EventMachine calendar outcome")

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "scenario": scenario,
        "count": count,
        "processed": len(result.processed),
        "pending": len(result.pending),
        "elapsed_seconds": elapsed,
        "tracemalloc_peak_bytes": traced_peak,
        "process_peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("initial", "fanout", "due"), required=True)
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.count <= 100_000:
        parser.error("--count must be between 1 and 100000")
    print(json.dumps(run_scenario(args.scenario, args.count), sort_keys=True))


if __name__ == "__main__":
    main()

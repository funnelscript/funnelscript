"""Phase 3 Empirical Verification: Vectorized Engine, Scale & Invariants.

Falsifiable Tests:
1. H_{3.1}: 100,000 agents over 14 days executes in < 500ms (> 500,000 agent-days/sec).
2. H_{3.2}: Cash starvation occurs when initial cash < settlement delay * daily spend.
3. H_{3.3}: Conservation of Mass: sum(N_states(t)) == N_total for all days t in [0, T].
4. Telemetry: Value-at-Risk, Expected Shortfall, and Cannibalization metrics.
5. Exporters: CSV and JSON serialization roundtrips.
"""

from __future__ import annotations

import time
import json
from pathlib import Path
import pytest
import numpy as np

from funnelscript.parser import Parser
from funnelscript.runtime.engine import SimulationEngine
from funnelscript.runtime.exporters import (
    export_report_to_json,
    export_trajectories_to_csv,
    export_trials_to_csv,
)

SAMPLE_STRATEGY = """{
  "$schema": "https://marketing-lang.org",
  "strategy_name": "Scale_Stress_Test",
  "metadata": {
    "author": "Marketing Engineer",
    "industry": "Electronics",
    "currency": "USD"
  },
  "environment": {
    "market_volatility": "low",
    "competitor_activity": "moderate"
  },
  "entities": {
    "budgets": {
      "total_budget": 10000,
      "max_cpc_limit": 1.50,
      "initial_cash": 15000,
      "settlement_delay_days": 3
    },
    "audiences": [
      {
        "id": "aud_scale",
        "name": "General Tech Audience",
        "type": "cold",
        "estimated_size": 200000,
        "attributes": {
          "brand_affinity": 0.50,
          "price_sensitivity": 0.40,
          "fomo_index": 0.60
        }
      }
    ],
    "touchpoints": [
      {
        "id": "tp_google_search",
        "type": "paid_traffic",
        "platform": "Google",
        "base_cpc": 0.50,
        "ad_creative_score": 0.80
      },
      {
        "id": "tp_store",
        "type": "conversion_surface",
        "base_conversion_rate": 0.05
      },
      {
        "id": "tp_email",
        "type": "retargeting_channel",
        "medium": "Email",
        "base_open_rate": 0.35
      }
    ]
  },
  "logic_flow": [
    {
      "step": 1,
      "action": "TriggerTraffic",
      "source": "aud_scale",
      "via": "tp_google_search",
      "destination": "tp_store"
    },
    {
      "step": 2,
      "type": "ConditionalBranch",
      "condition": {
        "user_action": "AbandonCart",
        "time_elapsed": "2h"
      },
      "true_branch": [
        {
          "action": "ExecuteRetargeting",
          "channel": "tp_email",
          "payload": {
            "offer_type": "Discount_15",
            "discount_percentage": 15
          },
          "expected_impact": {
            "conversion_boost": 0.03
          }
        }
      ],
      "false_branch": [
        {
          "action": "DoNothing"
        }
      ]
    }
  ],
  "simulation_engine": {
    "engine_type": "Agent-Based_Monte_Carlo",
    "parameters": {
      "virtual_agents_count": 100000,
      "timeframe_days": 14,
      "randomness_factor_sigma": 0.10
    },
    "output_metrics_requested": ["ROAS", "CAC"]
  }
}"""


@pytest.fixture
def base_ast():
    return Parser.from_json_str(SAMPLE_STRATEGY)


def test_mass_conservation_invariant(base_ast):
    """H_{3.3}: At every single day, the sum of agents across all states equals N_total."""
    engine = SimulationEngine(base_ast)
    agent_count = 50000
    timeframe = 14

    report = engine.run(num_trials=2, agents_count=agent_count, record_trajectories=True)
    assert len(report.raw_trials) == 2

    for trial in report.raw_trials:
        assert len(trial.daily_snapshots) == timeframe
        for snap in trial.daily_snapshots:
            state_sum = sum(snap.state_distribution.values())
            assert state_sum == agent_count, (
                f"Conservation violated on day {snap.day}: sum={state_sum} != {agent_count}"
            )


def test_engine_throughput_benchmark(base_ast):
    """H_{3.1}: 100,000 agents over 14 days executes in < 300ms (> 500,000 agent-days/sec)."""
    engine = SimulationEngine(base_ast)
    agent_count = 100000
    timeframe = 14

    t0 = time.perf_counter()
    report = engine.run(num_trials=1, agents_count=agent_count, record_trajectories=False)
    elapsed = time.perf_counter() - t0

    total_agent_days = agent_count * timeframe
    throughput = total_agent_days / elapsed

    print(f"\nThroughput: {throughput:,.0f} agent-days/sec (Elapsed: {elapsed:.3f}s for 100k agents)")
    assert throughput >= 500000, f"Throughput too low: {throughput} agent-days/sec"
    assert elapsed < 0.50, f"Execution too slow: {elapsed:.3f}s > 0.5s"


def test_liquidity_starvation_and_insolvency(base_ast):
    """H_{3.2}: Extreme settlement delay + inadequate initial cash triggers insolvency."""
    # Scenario A: Under-capitalized merchant (Cash=$200, Delay=7 days, Daily Budget=$1000/day)
    base_ast.entities.budgets.initial_cash = 200.0
    base_ast.entities.budgets.settlement_delay_days = 7
    base_ast.entities.budgets.total_budget = 14000.0

    engine = SimulationEngine(base_ast)
    report = engine.run(num_trials=5, agents_count=10000)

    # Merchant should run out of cash before day 7 receivables settle
    assert report.cash_ruin_probability >= 0.80, "Expected high insolvency under severe cash starvation"

    # Scenario B: Well-capitalized merchant (Cash=$50,000)
    base_ast.entities.budgets.initial_cash = 50000.0
    engine_safe = SimulationEngine(base_ast)
    report_safe = engine_safe.run(num_trials=5, agents_count=10000)
    assert report_safe.cash_ruin_probability == 0.0, "Expected 0 insolvency with adequate reserve"


def test_telemetry_var_and_cannibalization(base_ast):
    """Verifies Value-at-Risk (VaR), CVaR, and discount cannibalization rate."""
    engine = SimulationEngine(base_ast)
    report = engine.run(num_trials=10, agents_count=10000)

    assert report.trials_count == 10
    assert report.roas.mean > 0.0
    assert report.cac.mean > 0.0
    assert report.var_95 >= 0.0
    assert report.cvar_95 >= report.var_95
    assert 0.0 <= report.cannibalization_rate <= 1.0


def test_exporters(base_ast, tmp_path):
    """Verifies CSV and JSON export pipelines."""
    engine = SimulationEngine(base_ast)
    report = engine.run(num_trials=3, agents_count=5000, record_trajectories=True)

    # 1. Export trials CSV
    csv_trials = tmp_path / "trials.csv"
    export_trials_to_csv(report, csv_trials)
    assert csv_trials.exists()
    lines = csv_trials.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4  # header + 3 trials

    # 2. Export daily trajectories CSV
    csv_traj = tmp_path / "trajectories.csv"
    export_trajectories_to_csv(report, csv_traj, trial_id=0)
    assert csv_traj.exists()
    traj_lines = csv_traj.read_text(encoding="utf-8").strip().splitlines()
    assert len(traj_lines) == 15  # header + 14 days

    # 3. Export JSON Report
    json_report = tmp_path / "report.json"
    raw_json = export_report_to_json(report, json_report)
    assert json_report.exists()
    parsed = json.loads(raw_json)
    assert parsed["strategy_name"] == "Scale_Stress_Test"
    assert "metrics" in parsed
    assert "risk_telemetry" in parsed
    assert "var_95" in parsed["risk_telemetry"]

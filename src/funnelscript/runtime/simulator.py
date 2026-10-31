"""FunnelScript Monte Carlo Simulation Adapter.

Provides backward-compatible interface to the optimized SimulationEngine.
"""

from __future__ import annotations

from funnelscript.models import StrategyAST
from funnelscript.runtime.engine import SimulationEngine
from funnelscript.runtime.telemetry import (
    DailySnapshot,
    DistributionMetrics,
    SimulationReport,
    TrialResult,
)


class MonteCarloSimulator:
    """Multi-Scale Discrete-Event Simulation Engine with Working Capital & Settlement Latency."""

    def __init__(
        self,
        ast: StrategyAST,
        average_order_value: float = 120.0,
        payment_fee_pct: float = 0.029,
        min_operational_reserve: float = 50.0,
    ) -> None:
        self.engine = SimulationEngine(
            ast=ast,
            average_order_value=average_order_value,
            payment_fee_pct=payment_fee_pct,
            min_operational_reserve=min_operational_reserve,
        )
        self.ast = ast

    def run(
        self,
        num_trials: int = 100,
        agents_count: int | None = None,
        seed: int = 42,
    ) -> SimulationReport:
        return self.engine.run(
            num_trials=num_trials,
            agents_count=agents_count,
            seed=seed,
            record_trajectories=True,
        )


__all__ = [
    "MonteCarloSimulator",
    "SimulationReport",
    "TrialResult",
    "DailySnapshot",
    "DistributionMetrics",
]

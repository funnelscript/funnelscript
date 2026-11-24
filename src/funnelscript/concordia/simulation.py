"""Concordia Multi-Agent Funnel Simulation Engine.

Orchestrates Generative Agent-Based Models (GABMs) using Google DeepMind's Concordia
with FunnelScript financial ledgers, catalog inventories, and governance circuit-breakers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from concordia.environment.engines import sequential

from funnelscript.concordia.circuit_breaker import GovernanceCircuitBreaker
from funnelscript.concordia.game_master import FunnelScriptConcordiaGameMaster
from funnelscript.concordia.prefabs import make_consumer_entity


@dataclass(frozen=True)
class ConcordiaSimulationResult:
    """Telemetry report produced by a Concordia multi-agent simulation run."""

    total_steps: int
    transactions_count: int
    total_revenue_cents: int
    ending_inventory: dict[str, int]
    circuit_breaker_tripped: bool
    tripped_reason: str | None
    event_log: list[str]


class ConcordiaFunnelSimulation:
    """Executes multi-agent social and commercial simulations using DeepMind Concordia."""

    def __init__(
        self,
        currency: str = "USD",
        circuit_breaker: GovernanceCircuitBreaker | None = None,
        max_steps: int = 10,
    ) -> None:
        self.currency = currency.upper()
        self.circuit_breaker = circuit_breaker or GovernanceCircuitBreaker()
        self.game_master = FunnelScriptConcordiaGameMaster(
            name="Marketplace_GameMaster",
            currency=self.currency,
            circuit_breaker=self.circuit_breaker,
            max_steps=max_steps,
        )
        self.entities = []

    def add_product(self, product_name: str, price_cents: int, initial_stock: int) -> None:
        """Add product to the simulation market catalog."""
        self.game_master.register_product(product_name, price_cents, initial_stock)

    def add_consumer(
        self,
        name: str,
        initial_wallet_cents: int = 20_000,
        preferred_product: str = "basic_plan",
        should_refund: bool = False,
        brand_affinity: float = 0.5,
        price_sensitivity: float = 0.5,
        fomo_index: float = 0.3,
    ) -> None:
        """Register and build a consumer agent."""
        self.game_master.register_agent_customer(name, initial_wallet_cents)
        entity = make_consumer_entity(
            name=name,
            ledger=self.game_master.ledger,
            initial_wallet_cents=initial_wallet_cents,
            preferred_product=preferred_product,
            should_refund=should_refund,
            brand_affinity=brand_affinity,
            price_sensitivity=price_sensitivity,
            fomo_index=fomo_index,
        )
        self.entities.append(entity)

    def run(self, max_steps: int | None = None, verbose: bool = False) -> ConcordiaSimulationResult:
        """Execute the Concordia simulation loop."""
        steps = max_steps or self.game_master.max_steps
        self.game_master.max_steps = steps

        env = sequential.Sequential()
        env.run_loop(
            game_masters=[self.game_master],
            entities=self.entities,
            max_steps=steps,
            verbose=verbose,
        )

        rev_balance = self.game_master.ledger.balance_cents("Revenue:General")

        return ConcordiaSimulationResult(
            total_steps=self.game_master.step_count,
            transactions_count=len(self.game_master.ledger.transactions),
            total_revenue_cents=rev_balance,
            ending_inventory=dict(self.game_master.inventory),
            circuit_breaker_tripped=self.circuit_breaker.status.name == "TRIPPED",
            tripped_reason=self.circuit_breaker.tripped_reason,
            event_log=list(self.game_master.resolved_events),
        )

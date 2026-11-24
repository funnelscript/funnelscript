"""Concordia Game Master with FunnelScript Double-Entry Ledger & Governance Integration.

Bridges Google DeepMind's Concordia Entity-Component architecture with
FunnelScript's exact-arithmetic double-entry financial ledger and
operational governance circuit breakers.
"""

from __future__ import annotations

import functools
import re
from typing import Sequence, override

from concordia.components.game_master import event_resolution
from concordia.environment.engine import action_spec_to_string
from concordia.typing import entity as entity_lib

from funnelscript.ledger import FinancialLedger, _cents_to_decimal
from funnelscript.concordia.circuit_breaker import GovernanceCircuitBreaker, CircuitBreakerStatus


class FunnelScriptConcordiaGameMaster(entity_lib.Entity):
    """DeepMind Concordia Game Master acting as Operational Financial & Ontology Custodian."""

    def __init__(
        self,
        name: str = "World_GameMaster",
        currency: str = "USD",
        circuit_breaker: GovernanceCircuitBreaker | None = None,
        turn_order: Sequence[str] | None = None,
        max_steps: int = 10,
    ) -> None:
        self._name = name
        self.currency = currency.upper()
        self.ledger = FinancialLedger()
        self.circuit_breaker = circuit_breaker or GovernanceCircuitBreaker()
        self.turn_order = list(turn_order or [])
        self.max_steps = max_steps
        self.step_count = 0
        self._turn_index = 0

        # System accounts
        self.ledger.declare_account("Revenue:General", self.currency)
        self.ledger.declare_account("Cash:Operating", self.currency)
        self.ledger.declare_account("Inventory:Asset", self.currency)

        # Inventory levels (product_name -> quantity)
        self.inventory: dict[str, int] = {}
        # Product prices in minor units (product_name -> price_cents)
        self.catalog_prices: dict[str, int] = {}

        # Observation queues per entity
        self._observations: dict[str, list[str]] = {}
        # Historical resolved events log
        self.resolved_events: list[str] = []
        # Current active putative event to resolve
        self._current_putative_event: str | None = None

    @functools.cached_property
    @override
    def name(self) -> str:
        return self._name

    def register_product(self, product_name: str, price_cents: int, initial_stock: int) -> None:
        """Register a product in the operational catalog with inventory."""
        self.catalog_prices[product_name.lower()] = price_cents
        self.inventory[product_name.lower()] = initial_stock

    def register_agent_customer(self, agent_name: str, initial_wallet_cents: int) -> None:
        """Register an agent customer account with initial funded wallet."""
        account_name = f"Customer:{agent_name}"
        self.ledger.declare_account(account_name, self.currency)
        if initial_wallet_cents > 0:
            # Fund wallet: Debit Customer (holds positive balance), Credit Cash:Operating
            tx_id = f"tx-fund-{agent_name}-{len(self.ledger.transactions) + 1}"
            self.ledger.post(
                tx_id=tx_id,
                timestamp=float(self.step_count),
                postings=[
                    (account_name, "debit", _cents_to_decimal(initial_wallet_cents)),
                    ("Cash:Operating", "credit", _cents_to_decimal(initial_wallet_cents)),
                ],
                description=f"Initial wallet funding for {agent_name}",
            )

        if agent_name not in self.turn_order:
            self.turn_order.append(agent_name)
        self._observations[agent_name] = [
            f"Welcome to the market, {agent_name}. Your wallet balance is ${_cents_to_decimal(initial_wallet_cents)} {self.currency}."
        ]

    @override
    def observe(self, observation: str) -> None:
        """Receive incoming observation or event signal from the simulation engine."""
        if observation.startswith(event_resolution.PUTATIVE_EVENT_TAG):
            self._current_putative_event = observation.removeprefix(event_resolution.PUTATIVE_EVENT_TAG).strip()
        elif observation.startswith(event_resolution.EVENT_TAG):
            clean_event = observation.removeprefix(event_resolution.EVENT_TAG).strip()
            self.resolved_events.append(clean_event)

    @override
    def act(
        self,
        action_spec: entity_lib.ActionSpec = entity_lib.DEFAULT_ACTION_SPEC,
    ) -> str:
        """Core Game Master decision dispatch requested by Concordia's engine."""
        out_type = action_spec.output_type

        # 1. Engine asks who acts next
        if out_type == entity_lib.OutputType.NEXT_ACTING:
            if not self.turn_order:
                raise ValueError("No entities registered in turn order.")
            active_entity = self.turn_order[self._turn_index % len(self.turn_order)]
            self._turn_index += 1
            self.step_count += 1
            return active_entity

        # 2. Engine asks what ActionSpec the acting entity should receive
        if out_type == entity_lib.OutputType.NEXT_ACTION_SPEC:
            return action_spec_to_string(entity_lib.DEFAULT_ACTION_SPEC)

        # 3. Engine asks to resolve the proposed action into a world event
        if out_type == entity_lib.OutputType.RESOLVE:
            return self._resolve_putative_event()

        # 4. Engine requests an observation for a specific entity
        if out_type == entity_lib.OutputType.MAKE_OBSERVATION:
            return self._make_observation_for_entity(action_spec.call_to_action)

        # 5. Engine checks if episode should terminate
        if out_type == entity_lib.OutputType.TERMINATE:
            if self.step_count >= self.max_steps:
                return entity_lib.BINARY_OPTIONS["affirmative"]
            if self.circuit_breaker.status == CircuitBreakerStatus.TRIPPED:
                return entity_lib.BINARY_OPTIONS["affirmative"]
            return entity_lib.BINARY_OPTIONS["negative"]

        # 6. Fallback
        return "Acknowledged"

    def _resolve_putative_event(self) -> str:
        """Parse, validate invariants, and execute double-entry ledger mutation."""
        event_text = self._current_putative_event or ""

        # Check circuit-breaker safety first (Fail-Closed)
        safety_ok, safety_reason = self.circuit_breaker.check_safety()
        if not safety_ok:
            resolution = f"GOVERNANCE INTERVENTION: Action halted. {safety_reason}"
            self._broadcast_observation(resolution)
            return resolution

        # Parse action pattern: "{AgentName} [buys/purchases/refunds] {Product}"
        buy_match = re.search(r"(\w+)\s+(?:buys|purchases|orders)\s+(\w+)", event_text, re.IGNORECASE)
        refund_match = re.search(r"(\w+)\s+(?:requests\s+refund\s+for|refunds)\s+(\w+)", event_text, re.IGNORECASE)

        if buy_match:
            agent_name = buy_match.group(1)
            product_name = buy_match.group(2).lower()
            return self._execute_buy_action(agent_name, product_name)

        elif refund_match:
            agent_name = refund_match.group(1)
            product_name = refund_match.group(2).lower()
            return self._execute_refund_action(agent_name, product_name)

        else:
            # Passive / conversational action
            resolution = f"Market observation: {event_text}"
            self._broadcast_observation(resolution)
            return resolution

    def _execute_buy_action(self, agent_name: str, product_name: str) -> str:
        """Execute governed buy action with invariant checks."""
        price_cents = self.catalog_prices.get(product_name)
        if price_cents is None:
            resolution = f"Action failed: Product '{product_name}' not found in catalog."
            self._send_observation(agent_name, resolution)
            return resolution

        # Check circuit-breaker safety for this specific transaction amount (Fail-Closed)
        safety_ok, safety_reason = self.circuit_breaker.check_safety(proposed_financial_cents=price_cents)
        if not safety_ok:
            resolution = f"GOVERNANCE INTERVENTION: Action halted. {safety_reason}"
            self._broadcast_observation(resolution)
            return resolution

        # Invariant 1: Inventory stock availability
        current_stock = self.inventory.get(product_name, 0)
        if current_stock <= 0:
            resolution = f"Action failed: Product '{product_name}' is out of stock."
            self._send_observation(agent_name, resolution)
            return resolution

        # Invariant 2: Sufficient customer wallet balance
        customer_account = f"Customer:{agent_name}"
        if self.ledger.get_account(customer_account) is None:
            self.register_agent_customer(agent_name, 0)

        customer_balance_cents = self.ledger.balance_cents(customer_account)
        if customer_balance_cents < price_cents:
            resolution = (
                f"Action failed for {agent_name}: Insufficient wallet balance "
                f"(${_cents_to_decimal(customer_balance_cents)}) for {product_name} (${_cents_to_decimal(price_cents)})."
            )
            self._send_observation(agent_name, resolution)
            self.circuit_breaker.record_usage(is_failure=True)
            return resolution

        # Execute atomic double-entry transaction:
        # Credit Customer Account (decreases balance), Credit Revenue (or Debit Revenue)
        # Note: In double-entry, Asset accounts have Debit balances, Revenue accounts have Credit balances.
        # Customer wallet is an asset for the customer (Debit balance). Spending reduces it (Credit Customer).
        # Revenue is an income account (Credit Revenue, Debit Cash or Receivables).
        tx_id = f"tx-buy-{agent_name}-{product_name}-{len(self.ledger.transactions) + 1}"
        self.ledger.post(
            tx_id=tx_id,
            timestamp=float(self.step_count),
            postings=[
                (customer_account, "credit", _cents_to_decimal(price_cents)),
                ("Revenue:General", "debit", _cents_to_decimal(price_cents)),
            ],
            description=f"{agent_name} purchase of {product_name}",
        )

        # Decrement inventory
        self.inventory[product_name] -= 1

        # Record financial usage in circuit-breaker
        self.circuit_breaker.record_usage(financial_mutation_cents=price_cents)

        new_balance = self.ledger.balance_cents(customer_account)
        resolution = (
            f"{agent_name} successfully purchased {product_name} for ${_cents_to_decimal(price_cents)}. "
            f"Remaining wallet: ${_cents_to_decimal(new_balance)} {self.currency}."
        )
        self._broadcast_observation(resolution)
        return resolution

    def _execute_refund_action(self, agent_name: str, product_name: str) -> str:
        """Execute governed refund action."""
        price_cents = self.catalog_prices.get(product_name, 0)
        if price_cents <= 0:
            return f"Action failed: Unknown product '{product_name}' for refund."

        customer_account = f"Customer:{agent_name}"
        tx_id = f"tx-ref-{agent_name}-{product_name}-{len(self.ledger.transactions) + 1}"
        self.ledger.post(
            tx_id=tx_id,
            timestamp=float(self.step_count),
            postings=[
                (customer_account, "debit", _cents_to_decimal(price_cents)),
                ("Revenue:General", "credit", _cents_to_decimal(price_cents)),
            ],
            description=f"Refund to {agent_name} for {product_name}",
        )
        self.inventory[product_name] = self.inventory.get(product_name, 0) + 1

        resolution = f"Refund issued to {agent_name} for {product_name} (${_cents_to_decimal(price_cents)})."
        self._broadcast_observation(resolution)
        return resolution

    def _make_observation_for_entity(self, call_to_action: str) -> str:
        """Extract entity name from call_to_action and return queued observations."""
        target_name = None
        for name in self.turn_order:
            if name in call_to_action:
                target_name = name
                break

        if target_name and self._observations.get(target_name):
            obs_list = self._observations[target_name]
            combined = " ".join(obs_list)
            self._observations[target_name] = []
            return combined

        return "The marketplace is active. The current stock and prices remain visible."

    def _send_observation(self, entity_name: str, observation: str) -> None:
        if entity_name not in self._observations:
            self._observations[entity_name] = []
        self._observations[entity_name].append(observation)

    def _broadcast_observation(self, observation: str) -> None:
        for name in self.turn_order:
            self._send_observation(name, observation)

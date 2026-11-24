"""Verification test suite for Google DeepMind Concordia & FunnelScript Engine Integration.

Tests:
1. Entity-Component compatibility with Concordia EntityAgent.
2. Double-entry financial ledger accuracy during agent transactions.
3. Invariant enforcement (insufficient funds, inventory limits).
4. Governance circuit-breaker fail-closed trip protection.
5. Multi-agent turn-based market execution.
"""

from __future__ import annotations

import pytest

concordia = pytest.importorskip("concordia")
from concordia.agents.entity_agent import EntityAgent
from concordia.environment.engines import sequential

from funnelscript.concordia import (
    ConcordiaFunnelSimulation,
    GovernanceCircuitBreaker,
    CircuitBreakerStatus,
    FunnelScriptConcordiaGameMaster,
    make_consumer_entity,
)
from funnelscript.ledger import FinancialLedger


def test_concordia_entity_agent_wallet_awareness():
    """Verify that a Concordia EntityAgent dynamically perceives its wallet balance."""
    ledger = FinancialLedger()
    ledger.declare_account("Customer:Alice", "USD")
    ledger.declare_account("Cash:Operating", "USD")
    ledger.post("tx-fund", 0.0, [("Customer:Alice", "debit", 250.0), ("Cash:Operating", "credit", 250.0)])

    agent = make_consumer_entity(
        name="Alice",
        ledger=ledger,
        initial_wallet_cents=25_000,
        preferred_product="saas_starter",
    )

    assert agent.name == "Alice"
    action = agent.act()
    assert "Alice buys saas_starter" in action


def test_concordia_single_agent_purchase_and_ledger_balance():
    """Verify Concordia turn-based execution modifies FunnelScript ledger with balanced transactions."""
    sim = ConcordiaFunnelSimulation(max_steps=2)
    sim.add_product("saas_pro", price_cents=10_000, initial_stock=5)  # $100.00
    sim.add_consumer(name="Bob", initial_wallet_cents=20_000, preferred_product="saas_pro")  # $200.00

    result = sim.run(max_steps=1)

    assert result.total_steps == 1
    assert result.ending_inventory["saas_pro"] == 4
    # Initial funding ($200) + 1 purchase ($100) = 2 transactions
    assert result.transactions_count == 2

    gm = sim.game_master
    assert gm.ledger.balance_cents("Customer:Bob") == 10_000  # $100 remaining
    assert gm.ledger.balance_cents("Revenue:General") == 10_000  # $100 revenue

    # Check total trial balance is perfectly balanced (Debits - Credits == 0)
    assert gm.ledger.total_imbalance_cents("USD") == 0


def test_concordia_insufficient_funds_fails_gracefully():
    """Verify that an agent with insufficient funds cannot execute an overdraft."""
    sim = ConcordiaFunnelSimulation(max_steps=2)
    sim.add_product("enterprise_suite", price_cents=50_000, initial_stock=10)  # $500.00
    sim.add_consumer(name="Charlie", initial_wallet_cents=10_000, preferred_product="enterprise_suite")  # Only $100.00

    result = sim.run(max_steps=1)

    # Inventory remains untouched
    assert result.ending_inventory["enterprise_suite"] == 10
    # No purchase transaction recorded (only initial funding)
    assert result.transactions_count == 1
    assert sim.game_master.ledger.balance_cents("Revenue:General") == 0

    # Charlie still has his original $100
    assert sim.game_master.ledger.balance_cents("Customer:Charlie") == 10_000


def test_concordia_circuit_breaker_trips_on_runaway_spending():
    """Verify governance circuit breaker trips fail-closed when financial ceiling is breached."""
    # Set strict financial cap of $150.00 (15,000 cents)
    breaker = GovernanceCircuitBreaker(max_financial_mutation_cents=15_000)
    sim = ConcordiaFunnelSimulation(circuit_breaker=breaker, max_steps=5)

    sim.add_product("course_pack", price_cents=10_000, initial_stock=10)  # $100.00
    sim.add_consumer(name="Dave", initial_wallet_cents=50_000, preferred_product="course_pack")  # $500.00

    # Step 1: Dave buys course_pack ($100 spent, accumulated: $100 <= $150 -> ALLOWED)
    result_step1 = sim.run(max_steps=1)
    assert not result_step1.circuit_breaker_tripped
    assert sim.game_master.ledger.balance_cents("Revenue:General") == 10_000

    # Step 2: Dave attempts to buy second course_pack ($100 spent -> total $200 > $150 -> TRIPPED)
    result_step2 = sim.run(max_steps=2)
    assert result_step2.circuit_breaker_tripped
    assert "Financial mutation ceiling" in (result_step2.tripped_reason or "")

    # Further purchases blocked
    assert sim.game_master.ledger.balance_cents("Revenue:General") == 10_000


def test_concordia_multi_agent_market_simulation():
    """Verify multi-agent sequential market simulation with multiple personas."""
    sim = ConcordiaFunnelSimulation(max_steps=4)
    sim.add_product("tier_a", price_cents=5_000, initial_stock=10)  # $50.00
    sim.add_product("tier_b", price_cents=8_000, initial_stock=5)   # $80.00

    sim.add_consumer(name="Eve", initial_wallet_cents=20_000, preferred_product="tier_a")
    sim.add_consumer(name="Frank", initial_wallet_cents=20_000, preferred_product="tier_b")

    # Run 2 complete cycles (2 steps each = 4 steps total)
    result = sim.run(max_steps=4)

    assert result.total_steps == 4
    # Eve bought tier_a twice (2 * $50 = $100)
    # Frank bought tier_b twice (2 * $80 = $160)
    # Total revenue = $260.00 (26,000 cents)
    assert result.total_revenue_cents == 26_000
    assert result.ending_inventory["tier_a"] == 8
    assert result.ending_inventory["tier_b"] == 3
    assert sim.game_master.ledger.total_imbalance_cents("USD") == 0


def test_concordia_refund_lifecycle():
    """Verify purchase followed by refund restores ledger balances and inventory."""
    sim = ConcordiaFunnelSimulation(max_steps=2)
    sim.add_product("widget", price_cents=4_000, initial_stock=3)  # $40.00
    sim.add_consumer(
        name="Grace",
        initial_wallet_cents=10_000,  # $100.00
        preferred_product="widget",
        should_refund=True,  # Buys on step 1, refunds on step 2
    )

    # Step 1: Purchase
    sim.run(max_steps=1)
    assert sim.game_master.inventory["widget"] == 2
    assert sim.game_master.ledger.balance_cents("Revenue:General") == 4_000
    assert sim.game_master.ledger.balance_cents("Customer:Grace") == 6_000

    # Step 2: Refund
    result = sim.run(max_steps=2)
    assert sim.game_master.inventory["widget"] == 3  # Restored
    assert sim.game_master.ledger.balance_cents("Revenue:General") == 0  # Reversed
    assert sim.game_master.ledger.balance_cents("Customer:Grace") == 10_000  # Reimbursed
    assert sim.game_master.ledger.total_imbalance_cents("USD") == 0

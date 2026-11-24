"""Comprehensive verification suite for flagship package ecommerce/d2c_scale.

Covers:
1. Parse & Lint Cleanliness across all package modules & stress example
2. Deterministic Replay (byte-for-byte reproducibility across runs)
3. Exact Double-Entry Conservation in MarketingLedger (zero float drift)
4. Monotonic Business Invariants (Sensitivity Checks)
5. Parameter Bounds Validation
6. Realized Stress Scenario Liquidity Breach (Profitable Paper ROAS vs. Cash Insolvency)
7. DEVS WorldExecutor Integration
"""

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

PKG_PARENT = Path(__file__).resolve().parents[1]
if str(PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(PKG_PARENT))

from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker
from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor
from packages.ecommerce.d2c_scale.engine import D2CScaleConfig, D2CScaleSimulator

PKG_DIR = Path(__file__).resolve().parents[1] / "packages" / "ecommerce" / "d2c_scale"
EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


# =========================================================================
# 1. Parse & Lint Cleanliness
# =========================================================================

@pytest.mark.parametrize(
    "filename",
    [
        "acquisition.fnls",
        "fulfillment.fnls",
        "treasury.fnls",
        "entities.fnls",
        "index.fnls",
    ],
)
def test_package_modules_compile_and_typecheck_cleanly(filename: str):
    module_path = PKG_DIR / filename
    assert module_path.is_file(), f"Missing module {module_path}"
    ast = Parser.from_file(module_path)
    assert isinstance(ast, WorldAST)
    # Statically type check declarations
    WorldTypeChecker.check(ast)
    from funnelscript.compiler.linter import WorldLinter
    WorldLinter(ast).check()
    assert len(ast.declarations) >= 1


def test_stress_example_compiles_and_resolves_package():
    example_path = EXAMPLES_DIR / "d2c_scale_stress.fnls"
    assert example_path.is_file(), f"Missing example {example_path}"
    ast = Parser.from_file(example_path)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)
    # Assert D2C was imported as the declaration
    assert any(d.name == "D2C" for d in ast.declarations)


# =========================================================================
# 2. Deterministic Replay
# =========================================================================

def test_deterministic_replay_produces_identical_telemetry_and_hashes():
    cfg = D2CScaleConfig(
        base_daily_ad_spend=Decimal("5000.00"),
        scale_daily_ad_spend=Decimal("10000.00"),
        cod_share_rate=Decimal("0.65"),
        cod_rto_rate=Decimal("0.18"),
        cod_remittance_days=7,
        horizon_days=30,
    )
    sim = D2CScaleSimulator(cfg)
    run1 = sim.run(seed=999)
    run2 = sim.run(seed=999)

    # Scalar outputs must match exactly
    assert run1.ending_cash == run2.ending_cash
    assert run1.min_cash_trough == run2.min_cash_trough
    assert run1.min_cash_trough_day == run2.min_cash_trough_day
    assert run1.total_booked_gmv == run2.total_booked_gmv
    assert run1.total_settled_cash == run2.total_settled_cash
    assert run1.total_ad_spend == run2.total_ad_spend
    assert run1.total_orders_booked == run2.total_orders_booked
    assert run1.total_rto_orders == run2.total_rto_orders
    assert run1.total_rto_loss == run2.total_rto_loss

    # Daily timelines must serialize to identical SHA-256 digests
    def hash_timeline(run):
        dump = json.dumps([
            {
                "day": m.day,
                "ad_spend": str(m.ad_spend),
                "orders_booked": m.orders_booked,
                "booked_gmv": str(m.booked_gmv),
                "settled_cash_inflow": str(m.settled_cash_inflow),
                "ending_settled_cash": str(m.ending_settled_cash),
                "accounts_receivable": str(m.accounts_receivable),
            }
            for m in run.daily_timeline
        ], sort_keys=True)
        return hashlib.sha256(dump.encode("utf-8")).hexdigest()

    assert hash_timeline(run1) == hash_timeline(run2)


# =========================================================================
# 3. Double-Entry Conservation & Zero Float Drift
# =========================================================================

@pytest.mark.parametrize("seed", [1, 42, 100, 777])
def test_double_entry_ledger_conservation_invariant(seed: int):
    cfg = D2CScaleConfig(
        base_daily_ad_spend=Decimal("6000.00"),
        scale_daily_ad_spend=Decimal("12000.00"),
        cod_share_rate=Decimal("0.70"),
        cod_rto_rate=Decimal("0.22"),
        cod_remittance_days=10,
        gateway_settle_days=4,
        horizon_days=30,
    )
    result = D2CScaleSimulator(cfg).run(seed=seed)

    # Invariant: Ending Cash == Starting Cash + Settled Receipts - Paid Ad Spend - Other Costs
    snapshot = result.ledger_snapshot
    expected_ending_cash = (
        cfg.initial_cash + snapshot.settled_receipts - snapshot.paid_ad_spend - snapshot.paid_other_costs
    )
    assert snapshot.cash == expected_ending_cash
    assert result.ending_cash == snapshot.cash
    assert result.ledger_conserved is True

    # Invariant: Profit == Recognized Revenue - Paid Ad Spend - Other Costs - Writeoffs
    expected_profit = (
        snapshot.recognized_revenue - snapshot.paid_ad_spend - snapshot.paid_other_costs - snapshot.writeoffs
    )
    assert snapshot.profit == expected_profit


# =========================================================================
# 4. Monotonic Business Invariants (Sensitivity Checks)
# =========================================================================

def test_remittance_lag_sensitivity_lowers_cash_trough_without_changing_gmv():
    """Increasing COD remittance lag strictly lowers or maintains cash trough, GMV constant."""
    cfg_fast = D2CScaleConfig(cod_remittance_days=3, horizon_days=30)
    cfg_slow = D2CScaleConfig(cod_remittance_days=14, horizon_days=30)

    res_fast = D2CScaleSimulator(cfg_fast).run(seed=42)
    res_slow = D2CScaleSimulator(cfg_slow).run(seed=42)

    # Customer demand / GMV is unchanged by back-office courier remittance speed
    assert res_fast.total_booked_gmv == res_slow.total_booked_gmv
    assert res_fast.total_orders_booked == res_slow.total_orders_booked

    # But longer remittance lag creates a deeper liquidity trough
    assert res_slow.min_cash_trough <= res_fast.min_cash_trough


def test_rto_rate_sensitivity_decreases_settled_cash_and_increases_loss():
    """Higher COD RTO rate strictly lowers settled cash and increases shipping loss."""
    cfg_low_rto = D2CScaleConfig(cod_rto_rate=Decimal("0.05"), horizon_days=30)
    cfg_high_rto = D2CScaleConfig(cod_rto_rate=Decimal("0.35"), horizon_days=30)

    res_low = D2CScaleSimulator(cfg_low_rto).run(seed=42)
    res_high = D2CScaleSimulator(cfg_high_rto).run(seed=42)

    assert res_high.total_rto_orders > res_low.total_rto_orders
    assert res_high.total_rto_loss > res_low.total_rto_loss
    assert res_high.total_settled_cash < res_low.total_settled_cash
    assert res_high.ending_cash < res_low.ending_cash


def test_zero_cod_share_eliminates_cod_orders_and_remittance():
    """Setting cod_share_rate = 0.0 means 100% prepaid orders."""
    cfg = D2CScaleConfig(cod_share_rate=Decimal("0.00"), horizon_days=30)
    res = D2CScaleSimulator(cfg).run(seed=42)

    assert res.total_cod_orders == 0
    assert res.total_prepaid_orders == res.total_orders_booked
    assert res.total_rto_orders == 0
    assert res.total_rto_loss == Decimal("0.00")


# =========================================================================
# 5. Parameter Bounds Validation
# =========================================================================

@pytest.mark.parametrize(
    ("param_kwargs", "expected_msg"),
    [
        ({"cod_rto_rate": Decimal("1.50")}, "cod_rto_rate"),
        ({"cod_remittance_days": -5}, "cod_remittance_days"),
        ({"cogs_rate": Decimal("-0.10")}, "cogs_rate"),
        ({"cogs_rate": Decimal("1.00")}, "cogs_rate"),
        ({"cod_share_rate": Decimal("1.20")}, "cod_share_rate"),
        ({"cod_confirmation_rate": Decimal("0.00")}, "cod_confirmation_rate"),
        ({"hill_alpha": 0.0}, "hill_alpha"),
        ({"hill_alpha": 2.8}, "hill_alpha"),
        ({"adstock_decay": 1.0}, "adstock_decay"),
        ({"initial_cash": Decimal("-500.00")}, "initial_cash"),
        ({"forward_shipping_cost": Decimal("-2.00")}, "forward_shipping_cost"),
        ({"delivery_delay_days": -1}, "delivery_delay_days"),
    ],
)
def test_parameter_bounds_rejection(param_kwargs, expected_msg):
    with pytest.raises(ValueError, match=expected_msg):
        D2CScaleConfig(**param_kwargs)


# =========================================================================
# 6. Stress Scenario Liquidity Breach Verification
# =========================================================================

def test_scaling_liquidity_breach_scenario():
    """Demonstrates: Paper ROAS is strong (> 2.8x) yet cash balance goes insolvent."""
    cfg = D2CScaleConfig(
        base_daily_ad_spend=Decimal("3000.00"),
        scale_daily_ad_spend=Decimal("6000.00"),
        scale_start_day=8,
        cod_share_rate=Decimal("0.65"),
        cod_confirmation_rate=Decimal("0.88"),
        cod_rto_rate=Decimal("0.18"),
        forward_shipping_cost=Decimal("4.50"),
        return_shipping_cost=Decimal("3.50"),
        packaging_cost=Decimal("1.00"),
        delivery_delay_days=4,
        cod_remittance_days=7,
        gateway_settle_days=3,
        initial_cash=Decimal("75000.00"),
        min_safety_cash=Decimal("15000.00"),
        horizon_days=30,
    )
    result = D2CScaleSimulator(cfg).run(seed=42)

    # 1. Paper ROAS looks commercially attractive
    assert result.paper_roas >= Decimal("2.50"), f"Expected ROAS >= 2.50, got {result.paper_roas}"

    # 2. Cash runway is breached
    assert result.cash_runway_breached is True
    assert result.breach_day is not None
    assert 8 <= result.breach_day <= 20, f"Breach expected mid-month, occurred day {result.breach_day}"

    # 3. Minimum cash trough goes deep into the negative (insolvency without debt/overdraft)
    assert result.min_cash_trough < Decimal("0.00")


# =========================================================================
# 7. DEVS WorldExecutor Integration
# =========================================================================

def test_world_executor_simulation_integration():
    """Runs a simulated sequence of events directly through the WorldExecutor on D2CSeasonalScaleStress."""
    example_path = EXAMPLES_DIR / "d2c_scale_stress.fnls"
    ast = Parser.from_file(example_path)
    executor = WorldExecutor(ast)

    events = [
        Event(0, "D2C.DailyAdSpend", payload={"spend": 5000.0}),
        Event(0, "D2C.NewOrder", payload={"order_id": 1, "order_value": 85.0, "is_cod": False, "cogs": 29.75, "shipping": 4.5}),
        Event(1, "D2C.DailyAdSpend", payload={"spend": 10000.0}),
        Event(1, "D2C.NewOrder", payload={"order_id": 2, "order_value": 85.0, "is_cod": True, "cogs": 29.75, "shipping": 4.5}),
        Event(3, "D2C.GatewaySettlement", payload={"gross": 85.0, "net": 80.0, "fee": 2.47, "reserve": 4.25}),
        Event(11, "D2C.OrderRTO", payload={"order_id": 2, "order_value": 85.0, "return_shipping": 3.5}),
        Event(15, "D2C.CheckSafetyThreshold", payload={"day": 15}),
    ]

    res = executor.run(events, seed=42)
    state = res.state["D2C"]

    assert state["total_ad_spend"] == 15000.0
    assert state["orders_count"] == 2
    assert state["rto_count"] == 1
    assert state["settled_cash"] == 80.0
    assert state["total_fees"] == 2.47
    assert state["total_writeoffs"] == 85.0
    assert state["cash_runway_breached"] is True

"""Comprehensive verification suite for flagship package leadgen/sales_capacity.

Covers:
1. Parse & Lint Cleanliness across all package modules & stress example
2. Deterministic Replay (byte-for-byte reproducibility across runs)
3. Exact Double-Entry Conservation in MarketingLedger (zero float drift)
4. Monotonic Business Invariants (Sensitivity Checks)
5. Parameter Bounds Validation
6. Realized Stress Scenario Capacity Bottleneck (Queue Overflow, SLA Degradation, CAC Spike)
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
from packages.leadgen.sales_capacity.engine import (
    SalesCapacityConfig,
    SalesCapacitySimulator,
)

PKG_DIR = Path(__file__).resolve().parents[1] / "packages" / "leadgen" / "sales_capacity"
EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


# =========================================================================
# 1. Parse & Lint Cleanliness
# =========================================================================

@pytest.mark.parametrize(
    "filename",
    [
        "acquisition.fnls",
        "queue_and_sla.fnls",
        "pipeline_and_hiring.fnls",
        "economics.fnls",
        "entities.fnls",
        "index.fnls",
    ],
)
def test_package_modules_compile_and_typecheck_cleanly(filename: str):
    module_path = PKG_DIR / filename
    assert module_path.is_file(), f"Missing module {module_path}"
    ast = Parser.from_file(module_path)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)
    from funnelscript.compiler.linter import WorldLinter
    WorldLinter(ast).check()
    assert len(ast.declarations) >= 1


def test_stress_example_compiles_and_resolves_package():
    example_path = EXAMPLES_DIR / "sales_capacity_stress.fnls"
    assert example_path.is_file(), f"Missing example {example_path}"
    ast = Parser.from_file(example_path)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)
    assert any(d.name == "SalesCap" for d in ast.declarations)


# =========================================================================
# 2. Deterministic Replay
# =========================================================================

def test_deterministic_replay_produces_identical_telemetry_and_hashes():
    cfg = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("2000.00"),
        scale_daily_ad_spend=Decimal("5000.00"),
        active_reps=4,
        max_leads_per_rep_per_day=12,
        deal_value=Decimal("4500.00"),
        horizon_days=30,
    )
    sim = SalesCapacitySimulator(cfg)
    run1 = sim.run(seed=999)
    run2 = sim.run(seed=999)

    # Scalar metrics must match exactly
    assert run1.ending_cash == run2.ending_cash
    assert run1.min_cash_trough == run2.min_cash_trough
    assert run1.min_cash_trough_day == run2.min_cash_trough_day
    assert run1.total_leads_generated == run2.total_leads_generated
    assert run1.total_leads_contacted == run2.total_leads_contacted
    assert run1.total_appointments_booked == run2.total_appointments_booked
    assert run1.total_deals_closed == run2.total_deals_closed
    assert run1.total_ad_spend == run2.total_ad_spend
    assert run1.total_payroll == run2.total_payroll
    assert run1.total_booked_revenue == run2.total_booked_revenue
    assert run1.total_collected_revenue == run2.total_collected_revenue
    assert run1.peak_queue_backlog == run2.peak_queue_backlog
    assert run1.avg_speed_to_lead_minutes == run2.avg_speed_to_lead_minutes
    assert run1.effective_close_rate == run2.effective_close_rate
    assert run1.effective_cac == run2.effective_cac

    # Daily timelines must serialize to identical SHA-256 digests
    def hash_timeline(run):
        dump = json.dumps(
            [
                {
                    "day": m.day,
                    "ad_spend": str(m.ad_spend),
                    "leads_generated": m.leads_generated,
                    "active_capacity": m.active_capacity,
                    "backlog_queue_depth": m.backlog_queue_depth,
                    "speed_to_lead_minutes": m.speed_to_lead_minutes,
                    "leads_contacted": m.leads_contacted,
                    "appointments_booked": m.appointments_booked,
                    "deals_closed": m.deals_closed,
                    "deals_booked_revenue": str(m.deals_booked_revenue),
                    "cash_collected": str(m.cash_collected),
                    "ending_cash": str(m.ending_cash),
                }
                for m in run.daily_timeline
            ],
            sort_keys=True,
        )
        return hashlib.sha256(dump.encode("utf-8")).hexdigest()

    assert hash_timeline(run1) == hash_timeline(run2)


# =========================================================================
# 3. Double-Entry Conservation & Zero Float Drift
# =========================================================================

@pytest.mark.parametrize("seed", [1, 42, 100, 777])
def test_double_entry_ledger_conservation_invariant(seed: int):
    cfg = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("2500.00"),
        scale_daily_ad_spend=Decimal("5500.00"),
        active_reps=5,
        max_leads_per_rep_per_day=10,
        deal_value=Decimal("5000.00"),
        planned_new_hires=2,
        hire_start_day=10,
        horizon_days=30,
    )
    result = SalesCapacitySimulator(cfg).run(seed=seed)

    snapshot = result.ledger_snapshot
    expected_ending_cash = (
        cfg.initial_cash + snapshot.settled_receipts - snapshot.paid_ad_spend - snapshot.paid_other_costs
    )
    assert snapshot.cash == expected_ending_cash
    assert result.ending_cash == snapshot.cash
    assert result.ledger_conserved is True

    expected_profit = (
        snapshot.recognized_revenue - snapshot.paid_ad_spend - snapshot.paid_other_costs - snapshot.writeoffs
    )
    assert snapshot.profit == expected_profit


# =========================================================================
# 4. Monotonic Business Invariants (Sensitivity Checks)
# =========================================================================

def test_active_reps_sensitivity_improves_speed_to_lead_and_throughput():
    """Adding active sales reps strictly lowers speed-to-lead and handles queue backlog."""
    cfg_low_rep = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("4000.00"),
        scale_daily_ad_spend=Decimal("4000.00"),
        active_reps=2,
        horizon_days=30,
    )
    cfg_high_rep = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("4000.00"),
        scale_daily_ad_spend=Decimal("4000.00"),
        active_reps=8,
        horizon_days=30,
    )

    res_low = SalesCapacitySimulator(cfg_low_rep).run(seed=42)
    res_high = SalesCapacitySimulator(cfg_high_rep).run(seed=42)

    # Lead generation is constant (same ad spend)
    assert res_low.total_leads_generated == res_high.total_leads_generated

    # High rep capacity processes faster, keeping speed-to-lead strictly shorter
    assert res_high.avg_speed_to_lead_minutes < res_low.avg_speed_to_lead_minutes
    assert res_high.peak_queue_backlog < res_low.peak_queue_backlog
    # Faster response preserves conversion rate, yielding more closed deals
    assert res_high.total_deals_closed >= res_low.total_deals_closed


def test_decay_half_life_sensitivity_modulates_close_rate():
    """Faster lead cooling (shorter half-life) reduces closed deals under backlog."""
    cfg_fast_decay = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("4000.00"),
        scale_daily_ad_spend=Decimal("4000.00"),
        active_reps=3,
        lead_decay_half_life_minutes=20.0,
        horizon_days=30,
    )
    cfg_slow_decay = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("4000.00"),
        scale_daily_ad_spend=Decimal("4000.00"),
        active_reps=3,
        lead_decay_half_life_minutes=180.0,
        horizon_days=30,
    )

    res_fast = SalesCapacitySimulator(cfg_fast_decay).run(seed=42)
    res_slow = SalesCapacitySimulator(cfg_slow_decay).run(seed=42)

    assert res_fast.total_leads_generated == res_slow.total_leads_generated
    assert res_slow.total_deals_closed >= res_fast.total_deals_closed
    assert res_slow.effective_close_rate >= res_fast.effective_close_rate


def test_zero_backlog_under_light_load():
    """When lead generation rate is well below team capacity, queue depth remains 0."""
    cfg = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("500.00"),
        scale_daily_ad_spend=Decimal("500.00"),
        active_reps=10,
        max_leads_per_rep_per_day=20,  # 200 daily capacity vs ~15 leads
        baseline_response_minutes=10.0,
        horizon_days=20,
    )
    res = SalesCapacitySimulator(cfg).run(seed=42)

    assert res.peak_queue_backlog == 0
    # Average speed to lead must equal baseline exactly
    assert res.avg_speed_to_lead_minutes == 10.0
    assert res.capacity_utilization_pct < 20.0


def test_hiring_ramp_payroll_vs_capacity_lag():
    """New hires incur recruitment fee and payroll immediately, but capacity ramps with delay."""
    cfg_no_hire = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("3000.00"),
        scale_daily_ad_spend=Decimal("3000.00"),
        active_reps=3,
        planned_new_hires=0,
        horizon_days=30,
    )
    cfg_hire = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("3000.00"),
        scale_daily_ad_spend=Decimal("3000.00"),
        active_reps=3,
        planned_new_hires=2,
        hire_start_day=10,
        hiring_cost_per_rep=Decimal("2500.00"),
        onboarding_ramp_days=14,
        ramp_productivity_rate=0.30,
        horizon_days=30,
    )

    res_no = SalesCapacitySimulator(cfg_no_hire).run(seed=42)
    res_hire = SalesCapacitySimulator(cfg_hire).run(seed=42)

    # Hiring costs are immediately realized
    assert res_hire.total_hiring_costs == Decimal("5000.00")
    assert res_hire.total_payroll > res_no.total_payroll

    # Capacity ramp: Before day 10, capacity is identical
    assert res_hire.daily_timeline[8].active_capacity == res_no.daily_timeline[8].active_capacity
    # On day 10, capacity reflects partial ramp productivity (3 + 2*0.3 = 3.6 reps * 12 = 43)
    assert res_hire.daily_timeline[9].active_capacity > res_no.daily_timeline[9].active_capacity
    # After day 24 (day 10 + 14 ramp), capacity reaches full (5 reps * 12 = 60)
    assert res_hire.daily_timeline[25].active_capacity == 60


# =========================================================================
# 5. Parameter Bounds Validation
# =========================================================================

@pytest.mark.parametrize(
    ("param_kwargs", "expected_msg"),
    [
        ({"active_reps": 0}, "active_reps"),
        ({"max_leads_per_rep_per_day": -1}, "max_leads_per_rep_per_day"),
        ({"baseline_response_minutes": 0.0}, "baseline_response_minutes"),
        ({"lead_decay_half_life_minutes": -10.0}, "lead_decay_half_life_minutes"),
        ({"baseline_contact_rate": 0.0}, "baseline_contact_rate"),
        ({"baseline_contact_rate": 1.5}, "baseline_contact_rate"),
        ({"deal_close_rate": -0.1}, "deal_close_rate"),
        ({"sales_commission_rate": Decimal("0.80")}, "sales_commission_rate"),
        ({"planned_new_hires": -2}, "planned_new_hires"),
        ({"onboarding_ramp_days": -1}, "onboarding_ramp_days"),
        ({"ramp_productivity_rate": 1.5}, "ramp_productivity_rate"),
        ({"initial_cash": Decimal("-100.00")}, "initial_cash"),
        ({"deal_value": Decimal("0.00")}, "deal_value"),
    ],
)
def test_parameter_bounds_rejection(param_kwargs, expected_msg):
    with pytest.raises(ValueError, match=expected_msg):
        SalesCapacityConfig(**param_kwargs)


# =========================================================================
# 6. Stress Scenario Sales Capacity Bottleneck Verification
# =========================================================================

def test_scaling_sales_capacity_bottleneck_scenario():
    """Demonstrates: 2.5x ad spend scaling against fixed rep capacity causes queue overflow,
    stretching speed-to-lead > 120m, collapsing close rates, and spiking Effective CAC.
    """
    cfg = SalesCapacityConfig(
        base_daily_ad_spend=Decimal("2000.00"),
        scale_daily_ad_spend=Decimal("5000.00"),
        scale_start_day=1,
        active_reps=4,
        max_leads_per_rep_per_day=12,  # Team capacity = 48 leads/day
        baseline_response_minutes=15.0,
        lead_decay_half_life_minutes=45.0,
        deal_value=Decimal("4500.00"),
        horizon_days=30,
        initial_cash=Decimal("30000.00"),
        min_safety_cash=Decimal("10000.00"),
    )
    result = SalesCapacitySimulator(cfg).run(seed=42)

    # 1. Lead volume saturates and exceeds daily capacity
    assert result.peak_queue_backlog > 50, f"Expected backlog > 50, got {result.peak_queue_backlog}"

    # 2. Speed-to-lead dramatically degrades past 120 minutes (often reaching hours)
    assert result.avg_speed_to_lead_minutes > 120.0, (
        f"Expected SLA degradation > 120 min, got {result.avg_speed_to_lead_minutes}"
    )

    # 3. Capacity utilization is practically 100%
    assert result.capacity_utilization_pct >= 95.0

    # 4. Effective close rate collapses due to exponential decay
    nominal_baseline_cvr = Decimal(str(cfg.baseline_contact_rate * cfg.qualified_appointment_rate * cfg.deal_close_rate))
    assert result.effective_close_rate < nominal_baseline_cvr * Decimal("0.60"), (
        f"Effective CVR {result.effective_close_rate} should collapse relative to nominal {nominal_baseline_cvr}"
    )

    # 5. Effective CAC spikes and net contribution margin drops
    assert result.effective_cac > Decimal("2000.00")
    assert result.ledger_conserved is True


# =========================================================================
# 7. DEVS WorldExecutor Integration
# =========================================================================

def test_world_executor_simulation_integration():
    """Runs a simulated sequence of events directly through the WorldExecutor on SalesCapacityStressRun."""
    example_path = EXAMPLES_DIR / "sales_capacity_stress.fnls"
    ast = Parser.from_file(example_path)
    executor = WorldExecutor(ast)

    events = [
        Event(0, "SalesCap.DailyAdSpend", payload={"spend": 5000.0, "leads": 65}),
        Event(0, "SalesCap.DeductDailyPayroll", payload={"payroll_amount": 533.33}),
        Event(0, "SalesCap.ProcessBacklog", payload={"processed": 48, "speed_to_lead": 185.0, "contacted": 12}),
        Event(1, "SalesCap.ScheduleDeal", payload={"appointments": 5}),
        Event(15, "SalesCap.CloseDeals", payload={"deals_count": 1, "deal_value": 4500.0}),
        Event(22, "SalesCap.CollectDeals", payload={"net_cash": 4140.0, "gross_collected": 4500.0, "commission": 360.0}),
        Event(25, "SalesCap.CheckSafetyThreshold", payload={"day": 25}),
    ]

    res = executor.run(events, seed=42)
    state = res.state["SalesCap"]

    assert state["total_ad_spend"] == 5000.0
    assert state["total_leads_generated"] == 65
    assert state["total_leads_contacted"] == 12
    assert state["qualified_appointments"] == 5
    assert state["closed_won_deals"] == 1
    assert state["booked_revenue"] == 4500.0
    assert state["collected_revenue"] == 4500.0
    assert state["total_commissions"] == 360.0
    assert state["total_payroll"] == 533.33
    assert state["effective_speed_to_lead"] == 185.0
    assert state["backlog_depth"] == 17  # 65 generated - 48 processed
    assert state["cash_runway_breached"] is False

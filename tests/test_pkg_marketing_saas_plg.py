"""Verification suite for official flagship package marketing/saas_plg.

Covers:
1. Parse & Typecheck Cleanliness across all package modules & entry point.
2. Simulation reproducibility and MRR / cash runway mechanics.
3. DEVS WorldExecutor integration.
4. Runway breach verification under high burn vs. growth.
"""

from __future__ import annotations

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
from packages.marketing.saas_plg.engine import SaasPLGConfig, SaasPLGSimulator

PKG_DIR = Path(__file__).resolve().parents[1] / "packages" / "marketing" / "saas_plg"


@pytest.mark.parametrize(
    "filename",
    [
        "index.fnls",
        "acquisition.fnls",
        "activation.fnls",
        "subscription.fnls",
        "treasury.fnls",
    ],
)
def test_saas_plg_modules_compile_and_typecheck_cleanly(filename: str):
    file_path = PKG_DIR / filename
    assert file_path.is_file(), f"Missing module {filename}"
    ast = Parser.from_file(file_path)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)


def test_saas_plg_simulation_growth_and_runway():
    config = SaasPLGConfig(
        starting_cash=Decimal("150000.00"),
        monthly_ad_spend=Decimal("8000.00"),
        fixed_monthly_burn=Decimal("20000.00"),
    )
    sim = SaasPLGSimulator(config)
    timeline = sim.simulate(months=12)

    assert len(timeline) == 12
    # MRR should grow monotonically as active subscribers compound
    assert timeline[-1].ending_mrr > timeline[0].ending_mrr
    assert timeline[-1].active_subscribers > timeline[0].active_subscribers
    # First month subscribers
    assert timeline[0].new_subscribers > 0


def test_saas_plg_runway_breach_detection():
    # Model under-capitalized company with high burn
    config = SaasPLGConfig(
        starting_cash=Decimal("30000.00"),
        min_safety_floor=Decimal("25000.00"),
        fixed_monthly_burn=Decimal("40000.00"),
        monthly_ad_spend=Decimal("10000.00"),
    )
    sim = SaasPLGSimulator(config)
    timeline = sim.simulate(months=6)

    # Cash should breach safety floor in month 1
    assert timeline[0].cash_runway_breached is True
    assert timeline[0].ending_cash < config.min_safety_floor


def test_saas_plg_devs_event_execution():
    index_file = PKG_DIR / "index.fnls"
    ast = Parser.from_file(index_file)
    executor = WorldExecutor(ast)

    events = [
        Event(
            time=1.0,
            name="Acquisition.TrackCampaignSpend",
            payload={"spend": 5000.0, "impressions": 50000, "clicks": 2000},
        ),
        Event(
            time=2.0,
            name="Acquisition.StartTrial",
        ),
        Event(
            time=3.0,
            name="Activation.CompleteSetup",
        ),
        Event(
            time=4.0,
            name="Activation.ReachAhaMoment",
        ),
        Event(
            time=5.0,
            name="Subscription.ConvertToPaid",
            payload={"plan_mrr": 199.0},
        ),
        Event(
            time=6.0,
            name="Treasury.CollectBilling",
            payload={"amount": 199.0, "fee": 6.07},
        ),
        Event(
            time=7.0,
            name="Treasury.DeductMonthlyBurn",
            payload={"salaries": 15000.0, "hosting": 2000.0},
        ),
        Event(
            time=8.0,
            name="Treasury.AuditRunway",
        ),
    ]

    result = executor.run(events)

    # Assert Acquisition state
    assert result.state["Acquisition"]["total_ad_spend"] == 5000.0
    assert result.state["Acquisition"]["visitors"] == 2000
    assert result.state["Acquisition"]["free_trials_started"] == 1

    # Assert Activation state
    assert result.state["Activation"]["onboarding_completed"] == 1
    assert result.state["Activation"]["pql_qualified"] == 1

    # Assert Subscription state
    assert result.state["Subscription"]["total_active"] == 1
    assert result.state["Subscription"]["current_mrr"] == 199.0

    # Assert Treasury state
    assert result.state["Treasury"]["total_collected_revenue"] == 199.0
    assert result.state["Treasury"]["total_burn_expended"] == 17000.0
    # Initial 100k + (199 - 6.07) - 17000 = 83192.93
    expected_cash = round(100000.0 + (199.0 - 6.07) - 17000.0, 2)
    assert round(result.state["Treasury"]["cash_balance"], 2) == expected_cash
    assert result.state["Treasury"]["cash_runway_breached"] is False


def test_import_saas_plg_package_from_consumer_world(tmp_path: Path):
    source = tmp_path / "consumer.fnls"
    source.write_text(
        'world MyEnterprisePLGStrategy {\n'
        '  import "marketing/saas_plg" as SaaS;\n'
        '}\n',
        encoding="utf-8",
    )
    ast = Parser.from_file(source)
    assert isinstance(ast, WorldAST)
    assert ast.name == "MyEnterprisePLGStrategy"
    WorldTypeChecker.check(ast)


"""Tests for Automated Parameter Calibration & Empirical Backtesting Engine.

Validates:
1. CampaignCalibrator fits empirical non-linear curves from campaign CSV.
2. Code generator emits valid .fnls World models that parse and pass type checking.
3. EmpiricalBacktester executes 50/50 temporal holdout and benchmarks against linear spreadsheet.
4. Liquidity starvation and cash ruin prediction under payment delay.
"""

from pathlib import Path
import pytest

from funnelscript.parser import Parser
from funnelscript.compiler.world_ast import WorldAST
from funnelscript.stdlib.marketing.ingestion import MarketingDataIngestor
from funnelscript.stdlib.marketing.calibration import CampaignCalibrator
from funnelscript.stdlib.marketing.backtest import EmpiricalBacktester


@pytest.fixture
def sample_data_path() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    campaign_csv = root / "examples/data/ecommerce_campaign_30d.csv"
    settlement_csv = root / "examples/data/payment_settlement_logs.csv"
    return campaign_csv, settlement_csv


def test_calibration_fits_parameters_and_generates_valid_fnl(sample_data_path, tmp_path: Path):
    campaign_csv, settlement_csv = sample_data_path
    assert campaign_csv.exists()
    assert settlement_csv.exists()

    campaign_records = MarketingDataIngestor.load_campaign_csv(campaign_csv)
    settlement_records = MarketingDataIngestor.load_payment_settlement_csv(settlement_csv)

    calibrated_model = CampaignCalibrator.calibrate(
        campaign_records, settlement_records, campaign_name="CalibratedTestWorld"
    )

    assert len(calibrated_model.channels) == 2
    assert calibrated_model.settlement_delay_days == 3
    assert calibrated_model.blended_cac > 0
    assert calibrated_model.average_order_value > 0

    for ch in calibrated_model.channels:
        assert ch.v_max > 0
        assert ch.k_sat > 0
        assert ch.alpha > 0
        assert ch.r_squared > 0.70  # High fit accuracy
        assert ch.min_observed_spend < ch.max_observed_spend

    # Validate generated .fnls syntax and type-check
    fnl_code = calibrated_model.generate_fnl_source()
    target_fnl = tmp_path / "calibrated_world.fnls"
    target_fnl.write_text(fnl_code, encoding="utf-8")

    ast = Parser.from_file(str(target_fnl))
    assert isinstance(ast, WorldAST)
    assert ast.name == "CalibratedTestWorld"
    assert len(ast.declarations) >= 3


def test_empirical_backtester_benchmarks_against_spreadsheet(sample_data_path):
    campaign_csv, settlement_csv = sample_data_path
    campaign_records = MarketingDataIngestor.load_campaign_csv(campaign_csv)
    settlement_records = MarketingDataIngestor.load_payment_settlement_csv(settlement_csv)

    report = EmpiricalBacktester.run_backtest(
        campaign_records,
        settlement_records,
        split_ratio=0.50,
        initial_cash=15000.0,
    )

    assert report.holdout_days == 15
    assert report.holdout_total_spend > 0

    # FunnelScript must demonstrate superior revenue & conversion accuracy over static spreadsheet
    assert report.revenue_comparison.funnelscript_mape < report.revenue_comparison.spreadsheet_mape
    assert report.conversions_comparison.funnelscript_mape < report.conversions_comparison.spreadsheet_mape
    assert report.revenue_comparison.superiority_ratio > 1.2

    # Liquidity crash prediction:
    # Ground truth encounters cash ruin due to spend scaling + 3-day payment lag.
    # Spreadsheet predicts ruin NEVER happens (false safe).
    # FunnelScript accurately predicts cash ruin!
    assert report.liquidity_ruin_actual_day is not None
    assert report.liquidity_ruin_funnelscript_day is not None
    assert abs(report.liquidity_ruin_actual_day - report.liquidity_ruin_funnelscript_day) <= 1
    assert report.liquidity_ruin_spreadsheet_day is None  # Spreadsheets miss the cash crisis

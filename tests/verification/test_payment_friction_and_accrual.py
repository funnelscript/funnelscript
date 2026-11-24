"""Verification tests for Phase 2: Payment Friction, Rolling Reserves, Refunds, Chargebacks, and Audited Metrics.

Validates:
1. Accrual vs. cash separation (RevenueRecognized at t vs. CashAvailable at t + delta_settle).
2. Payment gateway friction: processing fees and rolling reserve holds.
3. Rolling reserve maturity and release schedule into cash.
4. Partial and full refunds with retained gateway processing fees.
5. Chargeback dispute penalties and revenue reversals.
6. Ad-platform Net-30 credit line facility with credit breach protection.
7. Audited financial metrics (min_cash_balance, cash_exhaustion_tick, working_capital_gap, contribution_margin).
"""

from decimal import Decimal

import pytest

from funnelscript.ledger import FinancialLedger
from funnelscript.runtime.world_executor import PopulationResult
from funnelscript.stdlib.marketing import (
    LedgerEntry,
    MarketingLedger,
    evaluate_trial,
)


class TestPaymentFrictionDoubleEntry:
    def test_accrual_to_settlement_cash_lifecycle(self):
        ledger = FinancialLedger()

        # Day 1: Sale of $1,000 recognized on accrual basis
        ledger.post_accrual_sale("sale-1", timestamp=1.0, amount="1000.00")
        assert ledger.balance("Receivables") == Decimal("1000.00")
        assert ledger.balance("Revenue") == Decimal("-1000.00")
        assert "Cash" not in ledger._balances

        # Day 3: Settlement of $1,000 with 2.9% gateway fee ($29) and 10% rolling reserve ($100)
        # Net cash received = 1000 - 29 - 100 = $871.00
        ledger.post_payment_with_friction(
            "settle-1",
            timestamp=3.0,
            gross_amount="1000.00",
            fee_amount="29.00",
            reserve_amount="100.00",
        )

        assert ledger.balance("Receivables") == Decimal("0.00")
        assert ledger.balance("Cash") == Decimal("871.00")
        assert ledger.balance("GatewayFees") == Decimal("29.00")
        assert ledger.balance("RollingReserve") == Decimal("100.00")
        assert ledger.total_imbalance_cents("USD") == 0

        # Day 33: Release $100 rolling reserve after 30-day lockup
        ledger.post_reserve_release("release-1", timestamp=33.0, amount="100.00")
        assert ledger.balance("RollingReserve") == Decimal("0.00")
        assert ledger.balance("Cash") == Decimal("971.00")
        assert ledger.total_imbalance_cents("USD") == 0

    def test_refund_and_chargeback_flows(self):
        ledger = FinancialLedger()
        ledger.post_accrual_sale("sale-1", 1.0, "200.00")
        ledger.post_settlement("settle-1", 2.0, "200.00")

        # Process a partial refund of $50
        ledger.post_refund("refund-1", 5.0, refund_amount="50.00")
        assert ledger.balance("Cash") == Decimal("150.00")
        assert ledger.balance("Revenue") == Decimal("-150.00")

        # Process a chargeback of remaining $150 with $15 dispute fee penalty
        ledger.post_chargeback("chargeback-1", 10.0, disputed_amount="150.00", dispute_penalty="15.00")
        assert ledger.balance("Cash") == Decimal("-15.00")  # Overdraft/negative due to dispute fee
        assert ledger.balance("Revenue") == Decimal("0.00")  # Revenue fully reversed
        assert ledger.balance("DisputeFees") == Decimal("15.00")
        assert ledger.total_imbalance_cents("USD") == 0

    def test_credit_facility_drawdown_and_limit_breach(self):
        ledger = FinancialLedger()

        # Draw $4,000 on a $5,000 credit limit
        ledger.post_credit_facility_drawdown(
            "draw-1", 1.0, amount="4000.00", credit_limit="5000.00"
        )
        assert ledger.balance("AdSpend") == Decimal("4000.00")
        assert ledger.balance("CreditFacility") == Decimal("-4000.00")

        # Drawing another $1,500 breaches the $5,000 limit (4000 + 1500 = 5500 > 5000)
        with pytest.raises(ValueError, match="Credit line breach"):
            ledger.post_credit_facility_drawdown(
                "draw-2", 2.0, amount="1500.00", credit_limit="5000.00"
            )


class TestMarketingLedgerFrictionAndAuditedMetrics:
    def test_marketing_ledger_with_friction_kinds(self):
        entries = (
            LedgerEntry("trial-1", "sale-1", "sale", 0, Decimal("100.00"), "USD"),
            LedgerEntry("trial-1", "settle-1", "settlement", 2, Decimal("80.00"), "USD", "sale-1"),
            LedgerEntry("trial-1", "fee-1", "fee", 2, Decimal("2.50"), "USD"),
            LedgerEntry("trial-1", "reserve-1", "reserve_hold", 2, Decimal("10.00"), "USD"),
            LedgerEntry("trial-1", "refund-1", "refund", 3, Decimal("20.00"), "USD", "sale-1"),
            LedgerEntry("trial-1", "release-1", "reserve_release", 4, Decimal("10.00"), "USD"),
        )
        ledger = MarketingLedger("trial-1", "USD", Decimal("50.00"), horizon=5, settlement_delay=1, entries=entries)
        snapshot = ledger.evaluate()

        # Initial cash = 50.00
        # Day 2: settlement +80, fee -2.50, reserve -10 -> cash = 117.50
        # Day 3: refund -20 -> cash = 97.50
        # Day 4: release +10 -> cash = 107.50
        assert snapshot.cash == Decimal("107.50")
        assert snapshot.receivables == Decimal("0.00")
        assert snapshot.refunds == Decimal("20.00")
        assert snapshot.gateway_fees == Decimal("2.50")
        assert snapshot.rolling_reserves == Decimal("0.00")
        # Recognized revenue = 100 - 20 (refund) = 80.00
        assert snapshot.recognized_revenue == Decimal("80.00")
        # Profit = 80 (rev) - 2.50 (fee) = 77.50
        assert snapshot.profit == Decimal("77.50")

    def test_audited_financial_metrics_computation(self):
        # Create a mock PopulationResult
        pop = PopulationResult(
            trial_id="trial-1",
            stream_role="population",
            rng_version="threefry2x64-20",
            results=("user-1", "user-2", "user-3", "user-4"),
            partitions={
                "new": frozenset(),
                "terminal": frozenset({"user-1", "user-2"}),
                "inactive": frozenset({"user-3", "user-4"}),
            },
            segments={"default": frozenset({"user-1", "user-2", "user-3", "user-4"})},
            cohorts={"batch": frozenset({"user-1", "user-2", "user-3", "user-4"})},
            steps=(),
        )

        entries = (
            LedgerEntry("trial-1", "ad-1", "ad_spend", 0, Decimal("20.00"), "USD"),
            LedgerEntry("trial-1", "sale-1", "sale", 1, Decimal("100.00"), "USD"),
            LedgerEntry("trial-1", "settle-1", "settlement", 3, Decimal("50.00"), "USD", "sale-1"),
        )
        ledger = MarketingLedger("trial-1", "USD", Decimal("10.00"), horizon=4, settlement_delay=2, entries=entries)
        snapshot = ledger.evaluate()

        metrics = evaluate_trial(
            pop,
            snapshot,
            converted_state="terminal",
            attribution_label="direct",
            insolvency_threshold=Decimal("0.00"),
        )

        assert metrics.converted_count == 2
        assert metrics.eligible_count == 4
        assert metrics.conversion_rate == Decimal("0.5")
        assert metrics.cac == Decimal("10.00")  # 20 / 2
        assert metrics.roas == Decimal("5.00")  # 100 / 20
        assert metrics.min_cash_balance == Decimal("-10.00")  # 10 - 20 = -10 at day 0
        assert metrics.cash_exhaustion_tick == 0  # Fell below 0 at day 0
        assert metrics.working_capital_gap == Decimal("10.00")  # Receivables 50 - Cash 40 = 10
        assert metrics.contribution_margin == Decimal("1.00")  # 100 / 100 (no other costs)

    def test_undefined_metrics_zero_denominators(self):
        pop = PopulationResult(
            trial_id="trial-zero",
            stream_role="population",
            rng_version="threefry2x64-20",
            results=("user-1",),
            partitions={"new": frozenset({"user-1"}), "terminal": frozenset()},
            segments={"default": frozenset({"user-1"})},
            cohorts={"batch": frozenset({"user-1"})},
            steps=(),
        )
        ledger = MarketingLedger("trial-zero", "USD", Decimal("100.00"), horizon=1, settlement_delay=0, entries=())
        snapshot = ledger.evaluate()

        metrics = evaluate_trial(
            pop,
            snapshot,
            converted_state="terminal",
            attribution_label="none",
            insolvency_threshold=Decimal("0.00"),
        )

        assert metrics.cac is None
        assert metrics.roas is None
        assert metrics.contribution_margin is None

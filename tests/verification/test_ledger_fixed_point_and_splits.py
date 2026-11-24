"""Verification tests for Phase 1: Fixed-Point Arithmetic, Remainder Allocation, and Continuous Trial Balance.

Validates:
1. Largest Remainder Method (Hare-Niemeyer) penny-exact lump-sum allocation with zero drift.
2. Hypothesis property-based fuzzing of multi-currency transactions and remainder splits.
3. Continuous per-currency trial-balance invariant (sum(Debits) - sum(Credits) == 0).
4. Multi-currency isolation and FX clearing account routing.
5. Cryptographic SHA-256 transaction audit chain verification and tamper detection.
"""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from funnelscript.ledger import (
    FinancialLedger,
    Posting,
    Transaction,
    allocate_remainder,
)


class TestPennyExactAllocation:
    def test_allocate_remainder_basic_equal_split(self):
        # 10.00 USD split across 3 equal weights: 3.34, 3.33, 3.33 -> sum = 10.00
        allocations = allocate_remainder(10.00, [1, 1, 1], as_decimal=True)
        assert len(allocations) == 3
        assert sum(allocations) == Decimal("10.00")
        assert allocations[0] == Decimal("3.34")
        assert allocations[1] == Decimal("3.33")
        assert allocations[2] == Decimal("3.33")

    def test_allocate_remainder_cents_output(self):
        # 100 cents split 50/50
        cents = allocate_remainder(100, [1.0, 1.0], as_decimal=False)
        assert cents == [50, 50]
        assert sum(cents) == 100

    def test_allocate_remainder_unbalanced_weights(self):
        # 100.00 USD split across weights [70, 20, 10]
        alloc = allocate_remainder(Decimal("100.00"), [70, 20, 10], as_decimal=True)
        assert alloc == [Decimal("70.00"), Decimal("20.00"), Decimal("10.00")]
        assert sum(alloc) == Decimal("100.00")

    def test_allocate_remainder_seven_way_split(self):
        # 100.00 USD split across 7 equal channels
        alloc = allocate_remainder("100.00", [1] * 7, as_decimal=True)
        assert len(alloc) == 7
        assert sum(alloc) == Decimal("100.00")
        # 10000 / 7 = 1428.5714... cents. 1428 * 7 = 9996. Remainder = 4 cents.
        # First 4 channels get 14.29, remaining 3 get 14.28
        assert alloc[:4] == [Decimal("14.29")] * 4
        assert alloc[4:] == [Decimal("14.28")] * 3

    def test_allocate_remainder_zero_weights_raises_value_error(self):
        with pytest.raises(ValueError, match="strictly positive"):
            allocate_remainder(100, [0, 0, 0])

    def test_allocate_remainder_negative_weight_raises_value_error(self):
        with pytest.raises(ValueError, match="non-negative"):
            allocate_remainder(100, [1, -0.5, 2])

    @given(
        total_cents=st.integers(min_value=0, max_value=10_000_000),
        weights=st.lists(st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False), min_size=1, max_size=20),
    )
    def test_hypothesis_penny_exact_conservation(self, total_cents, weights):
        allocations = allocate_remainder(total_cents, weights, as_decimal=False)
        assert len(allocations) == len(weights)
        assert sum(allocations) == total_cents
        assert all(a >= 0 for a in allocations)


class TestFinancialLedgerTrialBalanceAndMultiCurrency:
    def test_continuous_trial_balance_invariant(self):
        ledger = FinancialLedger()
        ledger.declare_account("Cash", "USD")
        ledger.declare_account("Revenue", "USD")

        # Post balanced transaction: Debit Cash 500, Credit Revenue 500
        ledger.post("tx-1", 1.0, [("Cash", "debit", "500.00"), ("Revenue", "credit", "500.00")])
        assert ledger.total_imbalance_cents("USD") == 0
        assert ledger.balance("Cash") == Decimal("500.00")
        assert ledger.balance("Revenue") == Decimal("-500.00")

    def test_unbalanced_transaction_rejected_immediately(self):
        ledger = FinancialLedger()
        ledger.declare_account("Cash", "USD")
        ledger.declare_account("Revenue", "USD")

        with pytest.raises(ValueError, match="Unbalanced ledger transaction"):
            ledger.post("bad-tx", 1.0, [("Cash", "debit", "100.00"), ("Revenue", "credit", "90.00")])

    def test_multi_currency_strict_isolation_without_clearing(self):
        ledger = FinancialLedger()
        ledger.declare_account("CashUSD", "USD")
        ledger.declare_account("CashEUR", "EUR")

        # Attempting direct cross-currency posting without FX clearing must fail per-currency trial balance
        with pytest.raises(ValueError, match="Unbalanced ledger transaction"):
            ledger.post("cross-curr-fail", 1.0, [("CashUSD", "debit", "100.00"), ("CashEUR", "credit", "90.00")])

    def test_multi_currency_fx_clearing_success(self):
        ledger = FinancialLedger()
        # Transfer 100 USD to 92 EUR via FXClearing
        ledger.post_fx_exchange(
            tx_id="fx-1",
            timestamp=1.0,
            from_account="CashUSD",
            to_account="CashEUR",
            from_amount="100.00",
            to_amount="92.00",
            from_currency="USD",
            to_currency="EUR",
        )

        assert ledger.balance("CashUSD") == Decimal("-100.00")
        assert ledger.balance("FXClearing_USD") == Decimal("100.00")
        assert ledger.balance("CashEUR") == Decimal("92.00")
        assert ledger.balance("FXClearing_EUR") == Decimal("-92.00")
        assert ledger.total_imbalance_cents("USD") == 0
        assert ledger.total_imbalance_cents("EUR") == 0


class TestAuditChainVerification:
    def test_unbroken_audit_chain_verifies(self):
        ledger = FinancialLedger()
        ledger.post("tx-1", 1.0, [("A", "debit", "10.00"), ("B", "credit", "10.00")])
        ledger.post("tx-2", 2.0, [("B", "debit", "5.00"), ("C", "credit", "5.00")])
        ledger.post("tx-3", 3.0, [("C", "debit", "2.50"), ("A", "credit", "2.50")])

        assert len(ledger.hash_chain) == 3
        assert ledger.verify_audit_chain() is True

    def test_tampering_breaks_audit_chain(self):
        ledger = FinancialLedger()
        ledger.post("tx-1", 1.0, [("A", "debit", "10.00"), ("B", "credit", "10.00")])
        ledger.post("tx-2", 2.0, [("B", "debit", "5.00"), ("C", "credit", "5.00")])

        # Tamper with internal transaction list (simulating silent mutation)
        corrupted_tx = Transaction(
            tx_id="tx-2",
            timestamp=2.0,
            postings=(
                Posting("B", "debit", 9999, "USD"),
                Posting("C", "credit", 9999, "USD"),
            ),
            prev_hash=ledger.transactions[1].prev_hash,
            entry_hash=ledger.transactions[1].entry_hash,
        )
        ledger._transactions[1] = corrupted_tx

        with pytest.raises(ValueError, match="Audit chain entry hash mismatch"):
            ledger.verify_audit_chain()

    def test_idempotent_postings(self):
        ledger = FinancialLedger()
        tx1 = ledger.post(
            "tx-1", 1.0, [("A", "debit", "10.00"), ("B", "credit", "10.00")], idempotency_key="key-abc"
        )
        # Duplicate post with same key
        tx2 = ledger.post(
            "tx-1", 1.0, [("A", "debit", "10.00"), ("B", "credit", "10.00")], idempotency_key="key-abc"
        )
        assert tx1 == tx2
        assert len(ledger.transactions) == 1
        assert len(ledger.hash_chain) == 1

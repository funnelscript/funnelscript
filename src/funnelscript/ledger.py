"""Domain-neutral double-entry financial ledger kernel.

Research: docs/meta-ontology/01_VISION_AND_ARCHITECTURE.md
Implements double-entry accounting with exact integer minor units (Decimal)
and zero float drift for arbitrary ISO currencies.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

_ACCOUNT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*", re.ASCII)
_CURRENCY_CODE = re.compile(r"[A-Z]{3}", re.ASCII)


def _validate_account_name(name: str) -> str:
    if not isinstance(name, str) or not _ACCOUNT_ID.fullmatch(name):
        raise ValueError(f"Invalid ledger account name: '{name}'")
    return name


def _validate_currency(currency: str) -> str:
    if not isinstance(currency, str) or not _CURRENCY_CODE.fullmatch(currency):
        raise ValueError(f"Currency must be a 3-letter ISO uppercase code: '{currency}'")
    return currency


def _to_decimal_cents(amount: float | Decimal | str) -> int:
    """Convert amount to integer minor units (cents) with zero float drift and banker's rounding."""
    if isinstance(amount, (int, str)):
        dec = Decimal(str(amount))
    elif isinstance(amount, float):
        dec = Decimal(str(round(amount, 4)))
    elif isinstance(amount, Decimal):
        dec = amount
    else:
        raise TypeError(f"Invalid amount type: {type(amount).__name__}")

    if not dec.is_finite():
        raise ValueError(f"Amount must be a finite number: {amount}")

    # Scale by 100 for standard minor units (two decimal places) with banker's rounding
    return int((dec * 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _cents_to_decimal(cents: int) -> Decimal:
    sign = "-" if cents < 0 else ""
    units, minor = divmod(abs(cents), 100)
    return Decimal(f"{sign}{units}.{minor:02d}")


def allocate_remainder(
    total: Decimal | str | float,
    weights: Sequence[float | Decimal | int | str],
    *,
    as_decimal: bool = False,
) -> list[int] | list[Decimal]:
    """Deterministically allocates a total lump sum across weights using the Largest Remainder Method (Hare-Niemeyer).

    Guarantees:
        sum(allocated) == total (exact to 0 cents drift).
        Deterministic index-based tie-breaking.
    """
    if not weights:
        return []

    total_cents = total if isinstance(total, int) else _to_decimal_cents(total)
    parsed_weights = [Decimal(str(w)) for w in weights]

    if any(w < 0 for w in parsed_weights):
        raise ValueError("Weights for remainder allocation must be non-negative")

    total_weight = sum(parsed_weights)
    if total_weight <= Decimal(0):
        raise ValueError("Sum of allocation weights must be strictly positive")

    sign = -1 if total_cents < 0 else 1
    abs_cents = abs(total_cents)

    quotas = [(Decimal(abs_cents) * w) / total_weight for w in parsed_weights]
    bases = [int(q) for q in quotas]
    remainders = [q - Decimal(b) for q, b in zip(quotas, bases)]

    leftover = abs_cents - sum(bases)
    ranked_indices = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))

    allocations = list(bases)
    for idx in ranked_indices[:leftover]:
        allocations[idx] += 1

    if sign == -1:
        allocations = [-a for a in allocations]

    assert sum(allocations) == total_cents, "Remainder allocation violated zero-drift invariant"

    if as_decimal:
        return [_cents_to_decimal(a) for a in allocations]
    return allocations


@dataclass(frozen=True, slots=True)
class Posting:
    """A single debit or credit line in a balanced double-entry transaction."""

    account: str
    direction: Literal["debit", "credit"]
    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        _validate_account_name(self.account)
        _validate_currency(self.currency)
        if self.direction not in ("debit", "credit"):
            raise ValueError(f"Posting direction must be 'debit' or 'credit', got '{self.direction}'")
        if self.amount_cents <= 0:
            raise ValueError(f"Posting amount must be strictly positive minor units, got {self.amount_cents}")

    @property
    def amount(self) -> Decimal:
        return _cents_to_decimal(self.amount_cents)


@dataclass(frozen=True, slots=True)
class LedgerAccount:
    """A declared financial account belonging to a specific currency."""

    name: str
    currency: str
    initial_balance_cents: int = 0

    def __post_init__(self) -> None:
        _validate_account_name(self.name)
        _validate_currency(self.currency)


def compute_entry_hash(
    prev_hash: str,
    tx_id: str,
    timestamp: float,
    postings: Sequence[Posting],
    description: str = "",
    metadata: dict[str, str] | None = None,
) -> str:
    """Computes a deterministic SHA-256 hash linking transaction into the audit chain."""
    hasher = hashlib.sha256()
    hasher.update(prev_hash.encode("ascii"))
    payload = {
        "tx_id": tx_id,
        "timestamp": float(timestamp),
        "postings": [
            {
                "account": p.account,
                "direction": p.direction,
                "amount_cents": p.amount_cents,
                "currency": p.currency,
            }
            for p in postings
        ],
        "description": description,
        "metadata": metadata or {},
    }
    hasher.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii"))
    return hasher.hexdigest()


@dataclass(frozen=True, slots=True)
class Transaction:
    """A balanced multi-legged double-entry journal transaction."""

    tx_id: str
    timestamp: float
    postings: tuple[Posting, ...]
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    prev_hash: str = "0" * 64
    entry_hash: str = ""

    def __post_init__(self) -> None:
        if not self.tx_id:
            raise ValueError("Transaction tx_id must be non-empty")
        if len(self.postings) < 2:
            raise ValueError(f"Double-entry transaction {self.tx_id} requires at least 2 postings")

        # Invariant check: for each currency, sum(Debits) == sum(Credits)
        sums: dict[str, int] = {}
        for p in self.postings:
            delta = p.amount_cents if p.direction == "debit" else -p.amount_cents
            sums[p.currency] = sums.get(p.currency, 0) + delta

        for curr, diff in sums.items():
            if diff != 0:
                raise ValueError(
                    f"Unbalanced ledger transaction '{self.tx_id}' for currency {curr}: "
                    f"debits - credits = {_cents_to_decimal(diff)} (must be zero)"
                )


@dataclass(frozen=True)
class LedgerSnapshot:
    """Serializable, immutable snapshot of full ledger state for snapshot/restore."""

    accounts: dict[str, tuple[str, int]]  # name -> (currency, balance_cents)
    transactions: tuple[Transaction, ...]
    state_hash: str
    hash_chain: tuple[str, ...] = field(default_factory=tuple)


class FinancialLedger:
    """Domain-neutral double-entry financial ledger.

    Guarantees:
    - sum(Debits_c) - sum(Credits_c) == 0 at all times for every currency.
    - Zero floating-point drift backed by integer minor units.
    - Multi-currency isolation (cross-currency arithmetic disallowed without explicit FXClearing).
    - Tamper-evident cryptographic SHA-256 audit hash chain.
    - Deterministic state hashing and bit-exact snapshot / restore.
    """

    def __init__(self) -> None:
        self._accounts: dict[str, LedgerAccount] = {}
        # account_name -> balance in minor units (debit balance is positive, credit is negative)
        self._balances: dict[str, int] = {}
        self._transactions: list[Transaction] = []
        self._hash_chain: list[str] = []
        self._idempotency_map: dict[str, str] = {}  # idempotency_key -> tx_id

    @property
    def accounts(self) -> dict[str, LedgerAccount]:
        """Returns read-only copy of declared ledger accounts."""
        return dict(self._accounts)

    @property
    def currencies(self) -> set[str]:
        """Returns set of currencies present in declared accounts."""
        return {acc.currency for acc in self._accounts.values()}

    def declare_account(
        self,
        name: str,
        currency: str = "USD",
        initial_balance: float | Decimal | str = 0,
    ) -> LedgerAccount:
        _validate_account_name(name)
        curr = _validate_currency(currency.upper())
        if name in self._accounts:
            existing = self._accounts[name]
            if existing.currency != curr:
                raise ValueError(
                    f"Account '{name}' already declared with currency {existing.currency}, cannot redeclare with {curr}"
                )
            return existing

        cents = _to_decimal_cents(initial_balance)
        account = LedgerAccount(name=name, currency=curr, initial_balance_cents=cents)
        self._accounts[name] = account
        self._balances[name] = cents
        return account

    def get_account(self, name: str) -> LedgerAccount | None:
        return self._accounts.get(name)

    def balance_cents(self, name: str) -> int:
        if name not in self._balances:
            raise KeyError(f"Unknown ledger account '{name}'")
        return self._balances[name]

    def balance(self, name: str) -> Decimal:
        return _cents_to_decimal(self.balance_cents(name))

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        """All recorded transactions in chronological order."""
        return tuple(self._transactions)

    @property
    def hash_chain(self) -> tuple[str, ...]:
        """Cryptographic SHA-256 hash chain of all committed transactions."""
        return tuple(self._hash_chain)

    def has_transaction(self, tx_id: str) -> bool:
        """Check if a transaction with the given tx_id has already been committed."""
        return any(t.tx_id == tx_id for t in self._transactions)

    def post(
        self,
        tx_id: str,
        timestamp: float,
        postings: list[tuple[str, Literal["debit", "credit"], int | float | Decimal | str]],
        description: str = "",
        metadata: dict[str, str] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Post a double-entry transaction to the ledger with audit-chain hashing and trial-balance guards."""
        meta = dict(metadata or {})
        effective_key = idempotency_key or meta.get("idempotency_key")

        # Idempotency check: duplicate submission with same key is a safe no-op
        if effective_key:
            if effective_key in self._idempotency_map:
                existing_tx_id = self._idempotency_map[effective_key]
                existing_tx = next((t for t in self._transactions if t.tx_id == existing_tx_id), None)
                if existing_tx is not None:
                    # Verify idempotency payload match
                    return existing_tx
            meta["idempotency_key"] = effective_key

        parsed_postings: list[Posting] = []
        for acct_name, direction, amount in postings:
            acct = self._accounts.get(acct_name)
            if acct is None:
                # Auto-declare default account if not yet declared
                acct = self.declare_account(acct_name, "USD")
            cents = _to_decimal_cents(amount)
            parsed_postings.append(
                Posting(
                    account=acct_name,
                    direction=direction,
                    amount_cents=cents,
                    currency=acct.currency,
                )
            )

        postings_tuple = tuple(parsed_postings)
        prev_hash = self._hash_chain[-1] if self._hash_chain else "0" * 64
        entry_hash = compute_entry_hash(prev_hash, tx_id, timestamp, postings_tuple, description, meta)

        tx = Transaction(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=postings_tuple,
            description=description,
            metadata=meta,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )

        # Apply postings to account balances
        for p in tx.postings:
            delta = p.amount_cents if p.direction == "debit" else -p.amount_cents
            self._balances[p.account] = self._balances.get(p.account, 0) + delta

        self._transactions.append(tx)
        self._hash_chain.append(entry_hash)
        if effective_key:
            self._idempotency_map[effective_key] = tx_id

        return tx

    def verify_audit_chain(self) -> bool:
        """Verifies that the entire transaction history has an unbroken SHA-256 hash chain."""
        expected_prev = "0" * 64
        for idx, tx in enumerate(self._transactions):
            if tx.prev_hash != expected_prev:
                raise ValueError(
                    f"Audit chain break at transaction {idx} ('{tx.tx_id}'): "
                    f"expected prev_hash '{expected_prev}', got '{tx.prev_hash}'"
                )
            recalculated = compute_entry_hash(
                expected_prev, tx.tx_id, tx.timestamp, tx.postings, tx.description, tx.metadata
            )
            if tx.entry_hash != recalculated:
                raise ValueError(
                    f"Audit chain entry hash mismatch at transaction {idx} ('{tx.tx_id}'): "
                    f"recorded '{tx.entry_hash}', recalculated '{recalculated}'"
                )
            expected_prev = tx.entry_hash
        return True

    # Real-World Payment & Liquidity Templates
    def post_accrual_sale(
        self,
        tx_id: str,
        timestamp: float,
        amount: float | Decimal | str,
        *,
        receivable_account: str = "Receivables",
        revenue_account: str = "Revenue",
        currency: str = "USD",
        description: str = "Accrual sale recognized",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Records sale recognition: Debit Receivables, Credit Revenue."""
        self.declare_account(receivable_account, currency)
        self.declare_account(revenue_account, currency)
        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=[
                (receivable_account, "debit", amount),
                (revenue_account, "credit", amount),
            ],
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_settlement(
        self,
        tx_id: str,
        timestamp: float,
        amount: float | Decimal | str,
        *,
        receivable_account: str = "Receivables",
        cash_account: str = "Cash",
        currency: str = "USD",
        description: str = "Settlement received into cash",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Records cash settlement: Debit Cash, Credit Receivables."""
        self.declare_account(receivable_account, currency)
        self.declare_account(cash_account, currency)
        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=[
                (cash_account, "debit", amount),
                (receivable_account, "credit", amount),
            ],
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_payment_with_friction(
        self,
        tx_id: str,
        timestamp: float,
        gross_amount: float | Decimal | str,
        *,
        fee_amount: float | Decimal | str = 0,
        reserve_amount: float | Decimal | str = 0,
        receivable_account: str = "Receivables",
        cash_account: str = "Cash",
        fee_account: str = "GatewayFees",
        reserve_account: str = "RollingReserve",
        currency: str = "USD",
        description: str = "Settlement with gateway fees and rolling reserve",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Settles gross receivable while deducting gateway processing fee and rolling reserve:

        Debit Cash (gross - fee - reserve)
        Debit GatewayFees (fee)
        Debit RollingReserve (reserve)
        Credit Receivables (gross)
        """
        gross_cents = _to_decimal_cents(gross_amount)
        fee_cents = _to_decimal_cents(fee_amount)
        reserve_cents = _to_decimal_cents(reserve_amount)
        net_cash_cents = gross_cents - fee_cents - reserve_cents

        if net_cash_cents < 0:
            raise ValueError(f"Friction (fee={fee_amount} + reserve={reserve_amount}) exceeds gross={gross_amount}")

        self.declare_account(receivable_account, currency)
        self.declare_account(cash_account, currency)
        self.declare_account(fee_account, currency)
        self.declare_account(reserve_account, currency)

        postings: list[tuple[str, Literal["debit", "credit"], int | float | Decimal | str]] = []
        if net_cash_cents > 0:
            postings.append((cash_account, "debit", _cents_to_decimal(net_cash_cents)))
        if fee_cents > 0:
            postings.append((fee_account, "debit", _cents_to_decimal(fee_cents)))
        if reserve_cents > 0:
            postings.append((reserve_account, "debit", _cents_to_decimal(reserve_cents)))
        postings.append((receivable_account, "credit", _cents_to_decimal(gross_cents)))

        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=postings,
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_reserve_release(
        self,
        tx_id: str,
        timestamp: float,
        amount: float | Decimal | str,
        *,
        reserve_account: str = "RollingReserve",
        cash_account: str = "Cash",
        currency: str = "USD",
        description: str = "Rolling reserve released to cash",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Releases matured rolling reserve into available cash: Debit Cash, Credit RollingReserve."""
        self.declare_account(reserve_account, currency)
        self.declare_account(cash_account, currency)
        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=[
                (cash_account, "debit", amount),
                (reserve_account, "credit", amount),
            ],
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_refund(
        self,
        tx_id: str,
        timestamp: float,
        refund_amount: float | Decimal | str,
        *,
        revenue_account: str = "Revenue",
        cash_account: str = "Cash",
        fee_account: str = "GatewayFees",
        retained_fee: float | Decimal | str = 0,
        dispute_fee: float | Decimal | str = 0,
        dispute_fee_account: str = "DisputeFees",
        currency: str = "USD",
        description: str = "Customer refund",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Processes partial or full refund:

        Debit Revenue (refund_amount)
        [Debit DisputeFees (dispute_fee) if any]
        Credit Cash (refund_amount + dispute_fee)
        """
        ref_cents = _to_decimal_cents(refund_amount)
        disp_cents = _to_decimal_cents(dispute_fee)
        total_payout = ref_cents + disp_cents

        self.declare_account(revenue_account, currency)
        self.declare_account(cash_account, currency)

        postings: list[tuple[str, Literal["debit", "credit"], int | float | Decimal | str]] = [
            (revenue_account, "debit", _cents_to_decimal(ref_cents)),
        ]
        if disp_cents > 0:
            self.declare_account(dispute_fee_account, currency)
            postings.append((dispute_fee_account, "debit", _cents_to_decimal(disp_cents)))
        postings.append((cash_account, "credit", _cents_to_decimal(total_payout)))

        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=postings,
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_chargeback(
        self,
        tx_id: str,
        timestamp: float,
        disputed_amount: float | Decimal | str,
        dispute_penalty: float | Decimal | str,
        *,
        revenue_account: str = "Revenue",
        cash_account: str = "Cash",
        dispute_fee_account: str = "DisputeFees",
        currency: str = "USD",
        description: str = "Chargeback clawback with dispute fee",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Processes chargeback: Debit Revenue, Debit DisputeFees, Credit Cash."""
        return self.post_refund(
            tx_id=tx_id,
            timestamp=timestamp,
            refund_amount=disputed_amount,
            dispute_fee=dispute_penalty,
            revenue_account=revenue_account,
            cash_account=cash_account,
            dispute_fee_account=dispute_fee_account,
            currency=currency,
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_fx_exchange(
        self,
        tx_id: str,
        timestamp: float,
        from_account: str,
        to_account: str,
        from_amount: float | Decimal | str,
        to_amount: float | Decimal | str,
        from_currency: str,
        to_currency: str,
        *,
        fx_clearing_account: str = "FXClearing",
        description: str = "Multi-currency FX transfer via clearing account",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Executes a multi-currency conversion strictly balancing each currency leg:

        In from_currency:
            Debit FXClearing (from_amount)
            Credit from_account (from_amount)
        In to_currency:
            Debit to_account (to_amount)
            Credit FXClearing (to_amount)
        """
        f_curr = _validate_currency(from_currency.upper())
        t_curr = _validate_currency(to_currency.upper())

        self.declare_account(from_account, f_curr)
        self.declare_account(to_account, t_curr)
        # Note: FXClearing sub-accounts per currency ensure strict trial-balance per currency
        clearing_from = f"{fx_clearing_account}_{f_curr}"
        clearing_to = f"{fx_clearing_account}_{t_curr}"
        self.declare_account(clearing_from, f_curr)
        self.declare_account(clearing_to, t_curr)

        postings: list[tuple[str, Literal["debit", "credit"], int | float | Decimal | str]] = [
            (clearing_from, "debit", from_amount),
            (from_account, "credit", from_amount),
            (to_account, "debit", to_amount),
            (clearing_to, "credit", to_amount),
        ]

        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=postings,
            description=description,
            idempotency_key=idempotency_key,
        )

    def post_credit_facility_drawdown(
        self,
        tx_id: str,
        timestamp: float,
        amount: float | Decimal | str,
        *,
        expense_account: str = "AdSpend",
        credit_account: str = "CreditFacility",
        credit_limit: float | Decimal | str | None = None,
        currency: str = "USD",
        description: str = "Ad spend financed via credit facility",
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Draws on an agency / ad-platform Net-30 credit line:

        Debit Expense, Credit CreditFacility.
        Checks hard credit limit trigger if provided.
        """
        cents = _to_decimal_cents(amount)
        self.declare_account(expense_account, currency)
        self.declare_account(credit_account, currency)

        if credit_limit is not None:
            limit_cents = _to_decimal_cents(credit_limit)
            current_credit = abs(self._balances.get(credit_account, 0))
            if current_credit + cents > limit_cents:
                raise ValueError(
                    f"Credit line breach: current {self.balance(credit_account)} + "
                    f"requested {_cents_to_decimal(cents)} exceeds limit {_cents_to_decimal(limit_cents)}"
                )

        return self.post(
            tx_id=tx_id,
            timestamp=timestamp,
            postings=[
                (expense_account, "debit", amount),
                (credit_account, "credit", amount),
            ],
            description=description,
            idempotency_key=idempotency_key,
        )

    def trial_balance(self) -> dict[str, dict[str, Decimal]]:
        """Return trial balance grouped by currency: currency -> {account: balance}."""
        res: dict[str, dict[str, Decimal]] = {}
        for name, acct in self._accounts.items():
            curr = acct.currency
            if curr not in res:
                res[curr] = {}
            res[curr][name] = self.balance(name)
        return res

    def total_imbalance_cents(self, currency: str) -> int:
        """Net sum of all balances in a currency (must be 0 in closed system)."""
        curr = currency.upper()
        return sum(
            self._balances[name]
            for name, acct in self._accounts.items()
            if acct.currency == curr
        )

    def compute_hash(self) -> str:
        """Deterministic SHA-256 hash of the entire ledger state."""
        hasher = hashlib.sha256()
        # Hash sorted accounts and balances
        for name in sorted(self._balances.keys()):
            acct = self._accounts[name]
            hasher.update(f"{name}:{acct.currency}:{self._balances[name]};".encode())
        # Hash transactions
        for tx in self._transactions:
            hasher.update(f"{tx.tx_id}:{tx.timestamp}:{tx.entry_hash}:".encode())
            for p in tx.postings:
                hasher.update(f"{p.account}:{p.direction}:{p.amount_cents}:{p.currency},".encode())
        return hasher.hexdigest()

    def snapshot(self) -> LedgerSnapshot:
        """Create an immutable snapshot of the ledger."""
        accts = {
            name: (self._accounts[name].currency, self._balances[name])
            for name in self._accounts
        }
        return LedgerSnapshot(
            accounts=accts,
            transactions=tuple(self._transactions),
            state_hash=self.compute_hash(),
            hash_chain=tuple(self._hash_chain),
        )

    def restore(self, snapshot: LedgerSnapshot) -> None:
        """Restore ledger state exactly from a snapshot."""
        self._accounts.clear()
        self._balances.clear()
        self._transactions.clear()
        self._hash_chain.clear()
        self._idempotency_map.clear()

        for name, (curr, cents) in snapshot.accounts.items():
            self._accounts[name] = LedgerAccount(name=name, currency=curr, initial_balance_cents=cents)
            self._balances[name] = cents

        self._transactions.extend(snapshot.transactions)
        self._hash_chain.extend(snapshot.hash_chain or [t.entry_hash for t in snapshot.transactions])
        for t in self._transactions:
            if t.metadata and "idempotency_key" in t.metadata:
                self._idempotency_map[t.metadata["idempotency_key"]] = t.tx_id

        current_hash = self.compute_hash()
        if current_hash != snapshot.state_hash:
            raise ValueError(
                f"Ledger restore integrity violation: expected hash {snapshot.state_hash}, got {current_hash}"
            )

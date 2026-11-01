"""Opt-in marketing financial reference ledger, not World or legacy runtime policy.

Research: funnelscript-research/spec/financial-ledger-metrics-v0.md (H-LEDGER1).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*", re.ASCII)
_CURRENCY = re.compile(r"[A-Z]{3}", re.ASCII)
_KINDS = frozenset({"sale", "settlement", "ad_spend", "other_cost", "writeoff"})
_CENT = Decimal("0.01")


def _identity(value: object, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a nonempty canonical ASCII identity")
    return value


def _money(value: object, label: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError(f"{label} must be a finite Decimal")
    exponent = value.as_tuple().exponent
    if value.adjusted() > 15 or not -2 <= exponent <= 15:
        raise ValueError(f"{label} exceeds supported fixed two-minor-unit precision/range")
    if positive and value <= 0:
        raise ValueError(f"{label} must be positive")
    return value


def _cents(amount: Decimal) -> int:
    parts = amount.as_tuple()
    digits = int("".join(str(digit) for digit in parts.digits))
    sign = -1 if parts.sign else 1
    return sign * digits * 10 ** (parts.exponent + 2)


def _decimal(cents: int) -> Decimal:
    prefix = "-" if cents < 0 else ""
    units, minor = divmod(abs(cents), 100)
    return Decimal(f"{prefix}{units}.{minor:02}")


@dataclass(frozen=True)
class LedgerEntry:
    trial_id: str
    tx_id: str
    kind: str
    day: int
    amount: Decimal
    currency: str
    source_tx_id: str | None = None

    def __post_init__(self) -> None:
        _identity(self.trial_id, "trial_id")
        _identity(self.tx_id, "tx_id")
        if self.kind not in _KINDS:
            raise ValueError("unknown ledger entry kind")
        if type(self.day) is not int or self.day < 0:
            raise ValueError("day must be a nonnegative integer")
        _money(self.amount, "amount", positive=True)
        if type(self.currency) is not str or _CURRENCY.fullmatch(self.currency) is None:
            raise ValueError("currency must be a three-letter uppercase code")
        if self.kind in ("settlement", "writeoff"):
            _identity(self.source_tx_id, "source_tx_id")
        elif self.source_tx_id is not None:
            raise ValueError("only settlement and writeoff may reference a sale")


@dataclass(frozen=True)
class LedgerSnapshot:
    trial_id: str
    currency: str
    horizon: int
    cash_initial: Decimal
    cash: Decimal
    min_cash: Decimal
    receivables: Decimal
    recognized_revenue: Decimal
    settled_receipts: Decimal
    paid_ad_spend: Decimal
    paid_other_costs: Decimal
    writeoffs: Decimal
    profit: Decimal
    open_receivables: tuple[tuple[str, Decimal], ...]
    checkpoints: tuple[tuple[int, str, Decimal], ...]


@dataclass(frozen=True)
class MarketingLedger:
    """An explicit ordered journal; no implicit settlements, events or credit rules."""

    trial_id: str
    currency: str
    cash_initial: Decimal
    horizon: int
    settlement_delay: int
    entries: tuple[LedgerEntry, ...]

    def __post_init__(self) -> None:
        _identity(self.trial_id, "trial_id")
        if type(self.currency) is not str or _CURRENCY.fullmatch(self.currency) is None:
            raise ValueError("currency must be a three-letter uppercase code")
        _money(self.cash_initial, "cash_initial")
        for name in ("horizon", "settlement_delay"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if type(self.entries) is not tuple or any(
            not isinstance(event, LedgerEntry) for event in self.entries
        ):
            raise TypeError("entries must be a tuple of LedgerEntry")

    def evaluate(self, *, until: int | None = None) -> LedgerSnapshot:
        if until is not None and (type(until) is not int or until < 0 or until > self.horizon):
            raise ValueError("until must be within the ledger horizon")
        cutoff = self.horizon if until is None else until
        seen: set[str] = set()
        sales: dict[str, tuple[int, int]] = {}
        cash = initial = _cents(self.cash_initial)
        minimum = cash
        revenue = settled = ads = costs = writeoffs = 0
        previous_day = 0
        checkpoints = [(0, "initial", _decimal(cash))]
        for entry in self.entries:
            if entry.trial_id != self.trial_id or entry.currency != self.currency:
                raise ValueError("ledger trial or currency mismatch")
            if entry.tx_id in seen:
                raise ValueError("duplicate transaction ID")
            if entry.day < previous_day:
                raise ValueError("journal events must be in nondecreasing day order")
            seen.add(entry.tx_id)
            previous_day = entry.day
            if entry.day > cutoff:
                continue
            cents = _cents(entry.amount)
            if entry.kind == "sale":
                sales[entry.tx_id] = (entry.day, cents)
                revenue += cents
            elif entry.kind in ("settlement", "writeoff"):
                day, available = self._receivable(sales, entry)
                if entry.day < day + self.settlement_delay and entry.kind == "settlement":
                    raise ValueError("settlement before minimum delay")
                if cents > available:
                    raise ValueError("settlement/writeoff exceeds outstanding receivable")
                sales[entry.source_tx_id] = (day, available - cents)
                if entry.kind == "settlement":
                    settled += cents
                    cash += cents
                else:
                    writeoffs += cents
            elif entry.kind == "ad_spend":
                ads += cents
                cash -= cents
            else:
                costs += cents
                cash -= cents
            minimum = min(minimum, cash)
            checkpoints.append((entry.day, entry.tx_id, _decimal(cash)))
        open_sales = tuple(sorted((key, _decimal(balance)) for key, (_, balance) in sales.items() if balance))
        return LedgerSnapshot(
            trial_id=self.trial_id, currency=self.currency, horizon=cutoff,
            cash_initial=_decimal(initial), cash=_decimal(cash), min_cash=_decimal(minimum),
            receivables=_decimal(sum(balance for _, balance in sales.values())),
            recognized_revenue=_decimal(revenue), settled_receipts=_decimal(settled),
            paid_ad_spend=_decimal(ads), paid_other_costs=_decimal(costs),
            writeoffs=_decimal(writeoffs),
            profit=_decimal(revenue - ads - costs - writeoffs),
            open_receivables=open_sales, checkpoints=tuple(checkpoints),
        )

    @staticmethod
    def _receivable(sales: dict[str, tuple[int, int]], entry: LedgerEntry) -> tuple[int, int]:
        if entry.source_tx_id not in sales:
            raise ValueError("settlement/writeoff must reference an existing sale")
        return sales[entry.source_tx_id]

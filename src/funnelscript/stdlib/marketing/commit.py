"""Opt-in single-writer financial commit coordinator with bounded filesystem semantics.

The receipt is a checksum of independently revalidated local evidence, not
authenticated financial authority or proof of stable-media persistence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from funnelscript.runtime.world_executor import PopulationResult
from .audit import (AUDIT_SCHEMA, _canonical, _keys, export_audit, read_audit_checkpoint,
                    restore_audit, write_audit_checkpoint)
from .ledger import _cents
from .provenance import DeclaredSalePolicy, ProvenancedTrial

RECEIPT_SCHEMA = "funnelscript-financial-commit-receipt-v1"
_RECEIPT_DOMAIN = b"funnelscript:financial-commit:v1\x00"
_STATE_DOMAIN = b"funnelscript:financial-state:v1\x00"
_MONEY_FIELDS = ("cash_initial", "cash", "receivables", "recognized_revenue",
                 "settled_receipts", "paid_ad_spend", "paid_other_costs", "writeoffs", "profit")


class CommitOutcomeUncertain(OSError):
    """Publication was attempted but successful durable acknowledgement is unsafe."""


@dataclass(frozen=True)
class FinancialCommitReceipt:
    schema: str
    trial_id: str
    audit_schema: str
    audit_sha256: str
    transaction_ids: tuple[str, ...]
    state_sha256: str
    commit_id: str

    def to_bytes(self) -> bytes:
        return _canonical(asdict(self))

    @classmethod
    def from_bytes(cls, data: bytes) -> FinancialCommitReceipt:
        if type(data) is not bytes:
            raise ValueError("receipt must be canonical bytes")
        try:
            raw = _keys(json.loads(data), set(cls.__dataclass_fields__))
            if raw["schema"] != RECEIPT_SCHEMA or type(raw["transaction_ids"]) is not list:
                raise ValueError("unsupported commit receipt schema")
            raw["transaction_ids"] = tuple(raw["transaction_ids"])
            receipt = cls(**raw)
            if receipt.to_bytes() != data:
                raise ValueError("noncanonical financial commit receipt")
            return receipt
        except (TypeError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid financial commit receipt") from error


def _receipt(data: bytes, linked: ProvenancedTrial) -> FinancialCommitReceipt:
    snapshot = linked.ledger.evaluate()
    amounts = {name + "_minor": _cents(getattr(snapshot, name)) for name in _MONEY_FIELDS}
    state = {"trial_id": linked.ledger.trial_id, "currency": linked.ledger.currency,
             "horizon": linked.ledger.horizon, **amounts}
    fields = {
        "schema": RECEIPT_SCHEMA,
        "trial_id": linked.ledger.trial_id,
        "audit_schema": AUDIT_SCHEMA,
        "audit_sha256": sha256(data).hexdigest(),
        "transaction_ids": tuple(entry.tx_id for entry in linked.ledger.entries),
        "state_sha256": sha256(_STATE_DOMAIN + _canonical(state)).hexdigest(),
    }
    commit_id = sha256(_RECEIPT_DOMAIN + _canonical(fields)).hexdigest()
    return FinancialCommitReceipt(**fields, commit_id=commit_id)


def recover_financial_checkpoint(
    path: str | os.PathLike, population: PopulationResult, policy: DeclaredSalePolicy,
    *, expected_receipt: FinancialCommitReceipt | None = None,
) -> tuple[ProvenancedTrial, FinancialCommitReceipt]:
    """Recover the actual checkpoint image, independently verifying World and ledger."""
    data = read_audit_checkpoint(path)
    linked = restore_audit(data, population, policy)
    receipt = _receipt(data, linked)
    if expected_receipt is not None and receipt != expected_receipt:
        raise ValueError("financial commit receipt mismatch or stale checkpoint")
    return linked, receipt


def verify_financial_receipt(
    path: str | os.PathLike, population: PopulationResult,
    policy: DeclaredSalePolicy, receipt: FinancialCommitReceipt,
) -> ProvenancedTrial:
    """Verify an externally retained receipt against current checkpoint evidence."""
    if not isinstance(receipt, FinancialCommitReceipt):
        raise ValueError("invalid financial commit receipt type")
    return recover_financial_checkpoint(
        path, population, policy, expected_receipt=receipt,
    )[0]


def _synchronize_existing(path: Path) -> None:
    """Re-establish file and directory synchronization before retry acknowledgement."""
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def commit_financial_checkpoint(
    path: str | os.PathLike, population: PopulationResult, policy: DeclaredSalePolicy,
    candidate: ProvenancedTrial, *, expected_receipt: FinancialCommitReceipt | None = None,
) -> FinancialCommitReceipt:
    """Commit a validated full audit; never acknowledge an ambiguous publication.

    The caller guarantees exclusive ownership of the path. For a changed
    checkpoint, supply the previously retained trusted receipt as an anchor.
    """
    data = export_audit(population, policy, candidate)
    proposed = _receipt(data, candidate)
    destination = Path(path)
    if destination.exists():
        previous, old_receipt = recover_financial_checkpoint(destination, population, policy)
        if expected_receipt is not None and old_receipt != expected_receipt:
            raise ValueError("previous receipt mismatch or stale checkpoint")
        if old_receipt == proposed:
            try:
                _synchronize_existing(destination)
                verify_financial_receipt(destination, population, policy, proposed)
            except (OSError, ValueError) as error:
                raise CommitOutcomeUncertain(
                    "idempotent checkpoint synchronization uncertain; recover persisted evidence"
                ) from error
            return old_receipt
        if expected_receipt is None:
            raise ValueError("changed financial checkpoint requires previous receipt")
        old_ledger, new_ledger = previous.ledger, candidate.ledger
        if (old_ledger.trial_id, old_ledger.currency, old_ledger.cash_initial,
                old_ledger.settlement_delay, old_ledger.horizon) != (
                new_ledger.trial_id, new_ledger.currency, new_ledger.cash_initial,
                new_ledger.settlement_delay, new_ledger.horizon):
            raise ValueError("changed financial trial configuration")
        if (previous.sales != candidate.sales or not set(previous.financial_actions).issubset(
                set(candidate.financial_actions))):
            raise ValueError("financial checkpoint cannot discard or rewrite committed actions")
    elif expected_receipt is not None:
        raise ValueError("expected previous checkpoint is absent")

    try:
        write_audit_checkpoint(destination, data)
        verify_financial_receipt(destination, population, policy, proposed)
    except (OSError, ValueError) as error:
        raise CommitOutcomeUncertain(
            "checkpoint publication or post-publication verification uncertain; recover persisted evidence"
        ) from error
    return proposed

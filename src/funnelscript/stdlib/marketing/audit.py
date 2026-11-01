"""Versioned, integrity-checked single-writer financial checkpoint (not authentication).

Research contract: funnelscript-research/spec/durable-financial-provenance-v1.md.
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Sequence

from funnelscript.runtime.world_executor import PopulationResult
from .ledger import LedgerEntry, _cents, _decimal
from .provenance import (
    DeclaredFinancialAction, DeclaredSalePolicy, EventProvenance, ProvenancedSale,
    ProvenancedTrial, PROVENANCE_VERSION, post_authorized_trial,
)

AUDIT_SCHEMA = "funnelscript-financial-audit-v1"
_DOMAIN = b"funnelscript:financial-audit:v1\x00"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _keys(value: object, expected: set[str]) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("invalid financial audit schema fields")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("financial audit integer field must be an exact integer")
    return value


def _entry_data(entry: LedgerEntry) -> dict:
    return {"trial_id": entry.trial_id, "tx_id": entry.tx_id, "kind": entry.kind,
            "day": entry.day, "amount_minor": _cents(entry.amount),
            "currency": entry.currency, "source_tx_id": entry.source_tx_id}


def _read_entry(raw: object) -> LedgerEntry:
    data = _keys(raw, {"trial_id", "tx_id", "kind", "day", "amount_minor",
                       "currency", "source_tx_id"})
    return LedgerEntry(data["trial_id"], data["tx_id"], data["kind"],
                       _integer(data["day"]), _decimal(_integer(data["amount_minor"])),
                       data["currency"], data["source_tx_id"])


def _payload(linked: ProvenancedTrial) -> dict:
    ledger = linked.ledger
    return {
        "trial_id": ledger.trial_id, "currency": ledger.currency,
        "provenance_version": PROVENANCE_VERSION,
        "cash_initial_minor": _cents(ledger.cash_initial), "horizon": ledger.horizon,
        "settlement_delay": ledger.settlement_delay,
        "sales": [{"ownership": "world_event", "entry": _entry_data(sale.entry),
                   "provenance": asdict(sale.provenance)} for sale in linked.sales],
        "actions": [{"ownership": "external_declaration", "entry": _entry_data(action.entry), "actor_id": action.actor_id,
                     "authorization_id": action.authorization_id}
                    for action in linked.financial_actions],
        "entries": [_entry_data(entry) for entry in ledger.entries],
    }


def _pack(payload: dict) -> bytes:
    digest = sha256(_DOMAIN + _canonical(payload)).hexdigest()
    return _canonical({"schema": AUDIT_SCHEMA, "payload": payload, "sha256": digest})


def _unpack(data: bytes, expected_sha256: str | None = None) -> dict:
    if type(data) is not bytes:
        raise ValueError("financial audit must be canonical UTF-8 bytes")
    if expected_sha256 is not None:
        if type(expected_sha256) is not str or not hmac.compare_digest(
                sha256(data).hexdigest(), expected_sha256):
            raise ValueError("external financial audit anchor mismatch")
    try:
        obj = json.loads(data)
        obj = _keys(obj, {"schema", "payload", "sha256"})
        if obj["schema"] != AUDIT_SCHEMA:
            raise ValueError("unsupported financial audit schema")
        digest = sha256(_DOMAIN + _canonical(obj["payload"])).hexdigest()
        if type(obj["sha256"]) is not str or not hmac.compare_digest(digest, obj["sha256"]):
            raise ValueError("financial audit integrity mismatch")
        if _canonical(obj) != data:
            raise ValueError("noncanonical financial audit representation")
        return _keys(obj["payload"], {"trial_id", "currency", "cash_initial_minor",
                                     "horizon", "settlement_delay", "provenance_version",
                                     "sales", "actions", "entries"})
    except (UnicodeError, json.JSONDecodeError, TypeError, OverflowError) as error:
        raise ValueError("invalid serialized financial audit") from error


def export_audit(population: PopulationResult, policy: DeclaredSalePolicy,
                 linked: ProvenancedTrial) -> bytes:
    """Revalidate all source witnesses against the actual World before exporting."""
    if not isinstance(linked, ProvenancedTrial):
        raise TypeError("export requires a provenanced trial")
    ledger = linked.ledger
    verified = post_authorized_trial(
        population, linked.sales, policy, actions=linked.financial_actions,
        cash_initial=ledger.cash_initial, settlement_delay=ledger.settlement_delay,
        horizon=ledger.horizon,
    )
    if verified != linked:
        raise ValueError("financial audit does not match verified World-to-ledger posting")
    return _pack(_payload(verified))


def restore_audit(data: bytes, population: PopulationResult, policy: DeclaredSalePolicy,
                  *, expected_sha256: str | None = None) -> ProvenancedTrial:
    """Restore only if the supplied World and policy independently revalidate the journal."""
    payload = _unpack(data, expected_sha256)
    if payload["provenance_version"] != PROVENANCE_VERSION:
        raise ValueError("unsupported source provenance version")
    if type(payload["sales"]) is not list or type(payload["actions"]) is not list:
        raise ValueError("invalid financial audit sales/actions collection")
    if type(payload["entries"]) is not list:
        raise ValueError("invalid financial audit entry collection")
    sales = []
    for raw in payload["sales"]:
        item = _keys(raw, {"ownership", "entry", "provenance"})
        if item["ownership"] != "world_event":
            raise ValueError("invalid World-event financial operation ownership")
        provenance = _keys(item["provenance"], set(EventProvenance.__dataclass_fields__))
        sales.append(ProvenancedSale(EventProvenance(**provenance), _read_entry(item["entry"])))
    actions = []
    for raw in payload["actions"]:
        item = _keys(raw, {"ownership", "entry", "actor_id", "authorization_id"})
        if item["ownership"] != "external_declaration":
            raise ValueError("invalid external financial operation ownership")
        actions.append(DeclaredFinancialAction(
            _read_entry(item["entry"]), item["actor_id"], item["authorization_id"]))
    restored = post_authorized_trial(
        population, tuple(sales), policy, actions=tuple(actions),
        cash_initial=_decimal(_integer(payload["cash_initial_minor"])),
        settlement_delay=_integer(payload["settlement_delay"]),
        horizon=_integer(payload["horizon"]),
    )
    if _payload(restored) != payload or export_audit(population, policy, restored) != data:
        raise ValueError("recovered financial audit does not match source or ledger")
    return restored


def replay_audit(data: bytes, population: PopulationResult, policy: DeclaredSalePolicy,
                 *, actions: Sequence[DeclaredFinancialAction],
                 expected_sha256: str | None = None) -> ProvenancedTrial:
    """Carry forward all previously committed identities before adding new deliveries."""
    committed = restore_audit(data, population, policy, expected_sha256=expected_sha256)
    if not isinstance(actions, Sequence):
        raise TypeError("replayed actions must be a sequence")
    ledger = committed.ledger
    return post_authorized_trial(
        population, committed.sales, policy,
        actions=(*committed.financial_actions, *actions),
        cash_initial=ledger.cash_initial, settlement_delay=ledger.settlement_delay,
        horizon=ledger.horizon,
    )


def write_audit_checkpoint(path: str | os.PathLike, data: bytes) -> None:
    """Publish an integrity-checked checkpoint using single-writer atomic replacement."""
    _unpack(data)
    destination = Path(path)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".audit-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            os.unlink(temporary)


def read_audit_checkpoint(path: str | os.PathLike) -> bytes:
    """Read one fully committed image and check its canonical integrity."""
    data = Path(path).read_bytes()
    _unpack(data)
    return data

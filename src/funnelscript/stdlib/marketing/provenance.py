"""Opt-in executed-event sale provenance bound to the existing marketing ledger.

Research: funnelscript-research/spec/transaction-provenance-v0.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import math
from collections.abc import Sequence

from funnelscript.runtime.world_executor import PopulationResult, WorldEventStep
from .ledger import LedgerEntry, MarketingLedger, _identity, _money


PROVENANCE_VERSION = "world-event-sale-v1"
_ORDER = {"ad_spend": 0, "other_cost": 0, "sale": 1, "settlement": 2, "writeoff": 3}


@dataclass(frozen=True)
class DeclaredSalePolicy:
    event_name: str
    state_field: str
    from_state: str
    to_state: str
    amount: Decimal
    currency: str
    attribution_label: str

    def __post_init__(self) -> None:
        for name in ("state_field", "from_state", "to_state", "attribution_label"):
            _identity(getattr(self, name), name)
        if type(self.event_name) is not str or self.event_name.count(".") != 1:
            raise ValueError("event_name must be an owner-qualified World event")
        for part in self.event_name.split("."):
            _identity(part, "event_name component")
        if self.from_state == self.to_state:
            raise ValueError("sale requires a declared state change")
        _money(self.amount, "sale amount", positive=True)
        LedgerEntry("check", "check", "sale", 0, self.amount, self.currency)


@dataclass(frozen=True)
class EventProvenance:
    trial_id: str
    agent_id: str
    event_owner: str
    event_name: str
    event_time: int
    occurrence_index: int
    event_digest: str
    from_state: str
    to_state: str
    operation: str
    transaction_id: str
    attribution_label: str


@dataclass(frozen=True)
class ProvenancedSale:
    provenance: EventProvenance
    entry: LedgerEntry


@dataclass(frozen=True)
class DeclaredFinancialAction:
    """An author-asserted external authorization, never a World event witness."""

    entry: LedgerEntry
    actor_id: str
    authorization_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.entry, LedgerEntry):
            raise TypeError("financial action requires a LedgerEntry")
        if self.entry.kind == "sale":
            raise ValueError("World event sales cannot use external authorization")
        _identity(self.actor_id, "actor_id")
        _identity(self.authorization_id, "authorization_id")


@dataclass(frozen=True)
class ProvenancedTrial:
    sales: tuple[ProvenancedSale, ...]
    ledger: MarketingLedger
    financial_actions: tuple[DeclaredFinancialAction, ...] = ()


def _validate_trace(population: PopulationResult) -> None:
    if set(population.steps) != set(population.results):
        raise ValueError("missing complete event trace for population")
    for aid, run in population.results.items():
        steps = population.steps[aid]
        if len(steps) != len(run.processed):
            raise ValueError("missing processed event trace evidence")
        previous: WorldEventStep | None = None
        for i, (step, event) in enumerate(zip(steps, run.processed)):
            if not isinstance(step, WorldEventStep) or step.occurrence_index != i or step.event != event:
                raise ValueError("inconsistent event trace occurrence")
            if step.owner != event.name.split(".", 1)[0]:
                raise ValueError("inconsistent event owner")
            if previous is not None and step.before != previous.after:
                raise ValueError("discontinuous agent state trace")
            previous = step
        if steps and steps[-1].after != run.state[steps[-1].owner]:
            raise ValueError("event trace does not match final agent state")


def _event_identity(step: WorldEventStep, trial_id: str, aid: str, policy: DeclaredSalePolicy) -> tuple[str, str]:
    event = step.event
    if not math.isfinite(event.time) or event.time < 0 or not float(event.time).is_integer():
        raise ValueError("financially relevant event time must be an integer simulation day")
    source = [int(event.time), event.name, event.priority, event.payload]
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    identity = [PROVENANCE_VERSION, trial_id, aid, step.occurrence_index, digest,
                "sale", policy.attribution_label]
    key = json.dumps(identity, separators=(",", ":"))
    return digest, "sale-v1-" + hashlib.sha256(key.encode("utf-8")).hexdigest()


def recognize_sales(
    population: PopulationResult, policy: DeclaredSalePolicy,
) -> tuple[ProvenancedSale, ...]:
    """Recognize only explicit World state transitions observed in an opt-in trace."""
    if not isinstance(population, PopulationResult) or not isinstance(policy, DeclaredSalePolicy):
        raise TypeError("population and declared sale policy are required")
    _validate_trace(population)
    sales: list[ProvenancedSale] = []
    for aid in sorted(population.results):
        for step in population.steps[aid]:
            if step.event.name != policy.event_name or not step.guard_matched:
                continue
            if (step.before.get(policy.state_field) != policy.from_state
                    or step.after.get(policy.state_field) != policy.to_state):
                continue
            digest, tx_id = _event_identity(step, population.trial_id, aid, policy)
            day = int(step.event.time)
            origin = EventProvenance(
                population.trial_id, aid, step.owner, step.event.name, day,
                step.occurrence_index, digest, policy.from_state, policy.to_state,
                "sale", tx_id, policy.attribution_label,
            )
            entry = LedgerEntry(
                population.trial_id, tx_id, "sale", day, policy.amount, policy.currency,
            )
            sales.append(ProvenancedSale(origin, entry))
    return tuple(sales)


def post_provenanced_trial(
    population: PopulationResult, sales: Sequence[ProvenancedSale],
    policy: DeclaredSalePolicy, *, external_entries: Sequence[LedgerEntry],
    cash_initial: Decimal, settlement_delay: int, horizon: int,
) -> ProvenancedTrial:
    """Validate complete source evidence and apply deduplicated sales exactly once."""
    expected = {sale.entry.tx_id: sale for sale in recognize_sales(population, policy)}
    seen: dict[str, ProvenancedSale] = {}
    for sale in sales:
        if not isinstance(sale, ProvenancedSale):
            raise TypeError("event-derived postings must have provenance")
        tx_id = sale.entry.tx_id
        if tx_id in seen:
            if seen[tx_id] != sale:
                raise ValueError("conflicting duplicate transaction identity")
            continue
        if expected.get(tx_id) != sale:
            raise ValueError("invalid or mismatched source event provenance")
        seen[tx_id] = sale
    if set(seen) != set(expected):
        raise ValueError("missing event-derived transactions or source events")
    if not isinstance(external_entries, Sequence):
        raise TypeError("external journal must be replayable")
    if any(not isinstance(item, LedgerEntry) for item in external_entries):
        raise TypeError("external journal requires LedgerEntry")
    if any(entry.kind == "sale" for entry in external_entries):
        raise ValueError("sales must be linked to source event provenance")
    entries = tuple(sorted(
        tuple(sale.entry for sale in seen.values()) + tuple(external_entries),
        key=lambda e: (e.day, _ORDER[e.kind], e.tx_id),
    ))
    if any(entry.day > horizon for entry in entries):
        raise ValueError("financial entry beyond declared horizon")
    ledger = MarketingLedger(population.trial_id, policy.currency, cash_initial,
                             horizon, settlement_delay, entries)
    ledger.evaluate()
    return ProvenancedTrial(tuple(sorted(seen.values(), key=lambda s: s.entry.tx_id)), ledger)


def post_authorized_trial(
    population: PopulationResult, sales: Sequence[ProvenancedSale],
    policy: DeclaredSalePolicy, *, actions: Sequence[DeclaredFinancialAction],
    cash_initial: Decimal, settlement_delay: int, horizon: int,
) -> ProvenancedTrial:
    """Post a trial with complete *declared* provenance for every non-sale entry.

    Authorization here is an author assertion, not externally authenticated evidence.
    Identical delivery retries are idempotent within this supplied input batch.
    """
    if not isinstance(actions, Sequence):
        raise TypeError("actions must be a replayable sequence")
    by_tx: dict[str, DeclaredFinancialAction] = {}
    by_authorization: dict[str, str] = {}
    for action in actions:
        if not isinstance(action, DeclaredFinancialAction):
            raise TypeError("external financial entries require declared authorization")
        tx_id = action.entry.tx_id
        previous = by_tx.get(tx_id)
        if previous is not None:
            if previous != action:
                raise ValueError("conflicting duplicate financial transaction identity")
            continue
        if action.authorization_id in by_authorization:
            raise ValueError("authorization identity reused for distinct transactions")
        by_authorization[action.authorization_id] = tx_id
        by_tx[tx_id] = action
    ordered = tuple(sorted(
        by_tx.values(), key=lambda a: (a.entry.day, _ORDER[a.entry.kind], a.entry.tx_id),
    ))
    linked = post_provenanced_trial(
        population, sales, policy,
        external_entries=tuple(action.entry for action in ordered),
        cash_initial=cash_initial, settlement_delay=settlement_delay, horizon=horizon,
    )
    return ProvenancedTrial(linked.sales, linked.ledger, ordered)

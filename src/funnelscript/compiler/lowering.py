"""Lowering pass for FunnelScript Meta-Ontology & Core Traits.

Research: docs/meta-ontology/01_VISION_AND_ARCHITECTURE.md & 02_IMPLEMENTATION_ROADMAP.md
Compiles high-level Entity declarations with Traits, 5 Kernel Primitives,
and lifecycle handlers down to flat, deterministic DEVS event-machine rules
and double-entry FinancialLedger postings with zero runtime dynamic reflection.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from funnelscript.compiler.world_ast import (
    AgentDefinition,
    BinaryExpression,
    DelayBranchDefinition,
    EntityDefinition,
    EventDefinition,
    EventEmissionDefinition,
    EventFieldDefinition,
    EventRuleDefinition,
    PayloadFieldExpression,
    PostStatementDefinition,
    ReferenceExpression,
    StateDefinition,
    StateExpression,
    StateTransitionDefinition,
    TraitDefinition,
    WorldAST,
    WorldTypeChecker,
)
from funnelscript.core.event_machine import Event, EventMachine, RunResult, Transition
from funnelscript.ledger import FinancialLedger, LedgerSnapshot
from funnelscript.runtime.world_executor import (
    WorldEventStep,
    WorldExecutor,
    WorldState,
)

_CURRENCY_EXTRACT = re.compile(r"Currency<([A-Z]{3})>", re.ASCII)
_POOL_EXTRACT = re.compile(r"Pool<([^>]+)>", re.ASCII)
_FLOW_EXTRACT = re.compile(r"Flow<([^>]+)>", re.ASCII)
_LEDGER_EXTRACT = re.compile(r"LedgerAccount<([A-Z]{3})>", re.ASCII)


@dataclass(frozen=True)
class LoweredLifecyclePosting:
    """Compiled record of a double-entry posting tied to an event rule."""

    event_name: str
    owner: str
    operation: str
    account: str
    amount_expr: StateExpression


@dataclass(frozen=True)
class LoweredSnapshot:
    """Full deterministic state snapshot across DEVS world state and financial ledger."""

    time: float
    world_state: WorldState
    ledger_snapshot: LedgerSnapshot
    pending_events: tuple[Event, ...]
    tx_counter: int
    state_hash: str


class LoweredWorld:
    """A fully lowered world ready for zero-reflection deterministic execution."""

    def __init__(
        self,
        world: WorldAST,
        ledger: FinancialLedger,
        postings: tuple[LoweredLifecyclePosting, ...],
    ) -> None:
        self.world = world
        self.ledger = ledger
        self.postings = postings
        self._executor = WorldExecutor(self.world)
        self._tx_counter: int = 0
        self._postings_by_event: dict[str, list[LoweredLifecyclePosting]] = {}
        for p in self.postings:
            self._postings_by_event.setdefault(p.event_name, []).append(p)

    @property
    def executor(self) -> WorldExecutor:
        return self._executor

    def initial_state(self) -> WorldState:
        return self._executor.initial_state()

    def run(
        self,
        events: Sequence[Event],
        *,
        seed: int = 0,
        until: float | None = None,
        max_events: int = 100_000,
        trace: list[WorldEventStep] | None = None,
        initial_state: WorldState | None = None,
    ) -> RunResult[WorldState]:
        """Execute lowered DEVS rules with synchronized double-entry ledger postings."""
        if trace is not None and (type(trace) is not list or trace):
            raise ValueError("trace sink must be a fresh empty list")

        start_state = initial_state if initial_state is not None else self.initial_state()

        def step_wrapper(state: WorldState, event: Event, rng: Any) -> Transition[WorldState]:
            trans = self._executor._step(state, event, rng)

            # Apply any registered double-entry ledger postings for this event
            postings = self._postings_by_event.get(event.name)
            if postings and trans.state != state:
                tx_lines = []
                snapshot = trans.state[postings[0].owner]
                payload = getattr(event, "payload", None) or {}
                for p in postings:
                    amount = WorldExecutor._evaluate(p.amount_expr, snapshot, payload, rng)
                    tx_lines.append((p.account, p.operation, amount))

                # Group by currency-balanced transactions or post
                if len(tx_lines) >= 2:
                    self._tx_counter += 1
                    tx_id = f"tx_{event.name}_{self._tx_counter}_{int(event.time * 1000)}"
                    self.ledger.post(
                        tx_id=tx_id,
                        timestamp=event.time,
                        postings=tx_lines,
                        description=f"Automated posting for {event.name}",
                    )

            if trace is not None:
                handler = self._executor.handlers.get(event.name)
                if handler is not None:
                    owner, rule = handler
                    trace.append(
                        WorldEventStep(
                            len(trace),
                            deepcopy(event),
                            owner,
                            self._executor._guard_matches(rule.guard, state[owner]),
                            deepcopy(state[owner]),
                            deepcopy(trans.state[owner]),
                        )
                    )
            return trans

        machine = EventMachine(step_wrapper)
        return machine.run(
            start_state,
            events,
            seed=seed,
            until=until,
            max_events=max_events,
        )

    def snapshot(self, current_time: float, state: WorldState, pending: Sequence[Event] = ()) -> LoweredSnapshot:
        """Create a bit-exact snapshot of both DEVS state and Ledger state."""
        ledger_snap = self.ledger.snapshot()
        hasher = hashlib.sha256()
        # Hash state deterministically
        for entity_name in sorted(state.keys()):
            for k, v in sorted(state[entity_name].items()):
                hasher.update(f"{entity_name}.{k}={v};".encode())
        hasher.update(ledger_snap.state_hash.encode("utf-8"))

        return LoweredSnapshot(
            time=current_time,
            world_state=deepcopy(state),
            ledger_snapshot=ledger_snap,
            pending_events=tuple(deepcopy(list(pending))),
            tx_counter=self._tx_counter,
            state_hash=hasher.hexdigest(),
        )

    def restore(self, snapshot: LoweredSnapshot) -> WorldState:
        """Restore both DEVS state and Ledger state exactly."""
        self.ledger.restore(snapshot.ledger_snapshot)
        self._tx_counter = snapshot.tx_counter
        return deepcopy(snapshot.world_state)


class LoweringPass:
    """Statically lowers meta-ontology entities and traits to raw DEVS primitives."""

    @classmethod
    def lower(cls, world: WorldAST) -> LoweredWorld:
        """Transform a high-level WorldAST into a pure, lowered LoweredWorld."""
        ledger = FinancialLedger()
        lowered_declarations: list[EntityDefinition | AgentDefinition] = []
        lifecycle_postings: list[LoweredLifecyclePosting] = []

        # Sort declarations deterministically to ensure PYTHONHASHSEED independence
        sorted_declarations = sorted(world.declarations, key=lambda d: d.name)

        for decl in sorted_declarations:
            # TraitDeclarations are erased entirely at runtime
            if isinstance(decl, TraitDefinition):
                continue

            lowered_decl, postings = cls._lower_entity(decl, ledger)
            lowered_declarations.append(lowered_decl)
            lifecycle_postings.extend(postings)

        lowered_ast = WorldAST(
            name=world.name,
            declarations=lowered_declarations,
            span=world.span,
        )
        WorldTypeChecker.check(lowered_ast)

        return LoweredWorld(
            world=lowered_ast,
            ledger=ledger,
            postings=tuple(lifecycle_postings),
        )

    @classmethod
    def _lower_entity(
        cls,
        entity: EntityDefinition,
        ledger: FinancialLedger,
    ) -> tuple[EntityDefinition | AgentDefinition, list[LoweredLifecyclePosting]]:
        states: list[StateDefinition] = list(entity.states)
        events: dict[str, EventDefinition] = {e.name: e for e in entity.events}
        rules: list[EventRuleDefinition] = list(entity.rules)
        postings: list[LoweredLifecyclePosting] = []

        existing_state_names = {s.name for s in states}

        # 1. Lower Primitive Fields (Pool, Flow, LedgerAccount, CapacityGuard, Metric, Attribute)
        sorted_primitives = sorted(entity.primitives, key=lambda p: p.name)
        for prim in sorted_primitives:
            name = prim.name
            kind = prim.primitive_kind
            type_spec = prim.type_spec

            if kind == "pool":
                # Pool lowers to an integer stock quantity Q(t) >= 0
                init_val = int(prim.initial_value or 0)
                if name not in existing_state_names:
                    states.append(StateDefinition(name=name, type_name="int", value=init_val, span=prim.span))
                    existing_state_names.add(name)

            elif kind == "flow":
                # Flow lowers to a transition rate or counter
                init_val = int(prim.initial_value or 0)
                if name not in existing_state_names:
                    states.append(StateDefinition(name=name, type_name="int", value=init_val, span=prim.span))
                    existing_state_names.add(name)

            elif kind == "ledger":
                # LedgerAccount lowers to an account in FinancialLedger and an integer balance state
                match = _LEDGER_EXTRACT.match(type_spec)
                currency = match.group(1) if match else "USD"
                ledger.declare_account(f"{entity.name}.{name}", currency=currency)
                ledger.declare_account(name, currency=currency)
                if name not in existing_state_names:
                    states.append(StateDefinition(name=name, type_name="int", value=0, span=prim.span))
                    existing_state_names.add(name)

            elif kind == "capacity":
                # CapacityGuard lowers to active load and capacity ceiling states
                max_cap = int(prim.capacity_max or 1000)
                active_name = f"{name}_active"
                max_name = f"{name}_max"
                if active_name not in existing_state_names:
                    states.append(StateDefinition(name=active_name, type_name="int", value=0, span=prim.span))
                    existing_state_names.add(active_name)
                if max_name not in existing_state_names:
                    states.append(StateDefinition(name=max_name, type_name="int", value=max_cap, span=prim.span))
                    existing_state_names.add(max_name)

            elif kind in ("metric", "attribute"):
                # Attributes and metrics lower to typed scalar states
                val = prim.initial_value
                if val is None:
                    # Provide default by type
                    if "Currency" in type_spec or "int" in type_spec or "Duration" in type_spec:
                        val = 0
                        type_name = "int"
                    elif "Prob" in type_spec or "float" in type_spec or "Rate" in type_spec:
                        val = 0.0
                        type_name = "float"
                    elif "bool" in type_spec:
                        val = False
                        type_name = "bool"
                    else:
                        val = ""
                        type_name = "string"
                else:
                    if isinstance(val, bool):
                        type_name = "bool"
                    elif isinstance(val, int):
                        type_name = "int"
                    elif isinstance(val, float):
                        type_name = "float"
                    else:
                        type_name = "string"

                if name not in existing_state_names:
                    states.append(StateDefinition(name=name, type_name=type_name, value=val, span=prim.span))
                    existing_state_names.add(name)

        # 2. Lower Lifecycle Handlers (on_<event> -> { post ...; delay(...) -> branch(...); })
        sorted_handlers = sorted(entity.handlers, key=lambda h: h.event)
        for handler in sorted_handlers:
            handler_event = handler.event
            clean_event_name = handler_event.removeprefix("on_")
            event_candidates = [clean_event_name, clean_event_name.capitalize(), handler_event]
            matched_event = next((c for c in event_candidates if c in events), None)
            if matched_event is None:
                matched_event = clean_event_name.capitalize() if "_" not in clean_event_name else handler_event

            if matched_event not in events:
                # Find all payload fields referenced in handler actions
                payload_fields: set[str] = set()

                def _collect_payload_fields(node: Any, sink: set[str]) -> None:
                    if isinstance(node, PayloadFieldExpression):
                        sink.add(node.name)
                    elif isinstance(node, BaseModel):
                        for field_name in node.__class__.model_fields:
                            _collect_payload_fields(getattr(node, field_name), sink)
                    elif isinstance(node, (list, tuple)):
                        for item in node:
                            _collect_payload_fields(item, sink)

                _collect_payload_fields(handler.actions, payload_fields)
                events[matched_event] = EventDefinition(
                    name=matched_event,
                    fields=[
                        EventFieldDefinition(name=fname, type_name="int", span=handler.span)
                        for fname in sorted(payload_fields)
                    ],
                    span=handler.span,
                )

            transitions: list[StateTransitionDefinition] = []
            emissions: list[EventEmissionDefinition] = []

            for action in handler.actions:
                if isinstance(action, StateTransitionDefinition):
                    transitions.append(action)

                elif isinstance(action, EventEmissionDefinition):
                    emissions.append(action)

                elif isinstance(action, PostStatementDefinition):
                    for p in action.postings:
                        postings.append(
                            LoweredLifecyclePosting(
                                event_name=f"{entity.name}.{matched_event}",
                                owner=entity.name,
                                operation=p.operation,
                                account=p.account,
                                amount_expr=p.amount_expr,
                            )
                        )
                        # Mirror double-entry in the entity's state variables if declared
                        if p.account in existing_state_names:
                            op = "+" if p.operation == "debit" else "-"
                            transitions.append(
                                StateTransitionDefinition(
                                    target=p.account,
                                    expr=BinaryExpression(
                                        operator=op,
                                        left=ReferenceExpression(name=p.account),
                                        right=p.amount_expr,
                                    ),
                                    span=p.span,
                                )
                            )

                elif isinstance(action, DelayBranchDefinition):
                    # Lower delay(...) -> branch(prob) { true => emit ...; false => emit ...; }
                    # We lower to scheduled emissions with the specified delay
                    for arm in action.arms:
                        em = arm.emission
                        emissions.append(em)

            rule_name = f"Rule_{entity.name}_{matched_event}"
            rules.append(
                EventRuleDefinition(
                    name=rule_name,
                    event=matched_event,
                    guard=None,
                    transitions=transitions,
                    emissions=emissions,
                    span=handler.span,
                )
            )

        # Sort states, events, rules canonically for bit-exact determinism
        sorted_states = sorted(states, key=lambda s: s.name)
        sorted_events = sorted(events.values(), key=lambda e: e.name)
        sorted_rules = sorted(rules, key=lambda r: r.name)

        if entity.kind == "agent":
            lowered = AgentDefinition(
                name=entity.name,
                states=sorted_states,
                events=sorted_events,
                rules=sorted_rules,
                span=entity.span,
            )
        else:
            lowered = EntityDefinition(
                name=entity.name,
                states=sorted_states,
                events=sorted_events,
                rules=sorted_rules,
                span=entity.span,
            )

        return lowered, postings

# Experimental Language Reference: Typed World Rules and Emitted Events

**Status:** Executable, intentionally minimal. Research authority: `funnelscript-research/spec/rule-transitions-v0.md` (H-R1 to H-R4; DEC-027), `funnelscript-research/spec/event-emission-v0.md` (H-E1 to H-E4; DEC-028), `funnelscript-research/spec/world-guards-v0.md` (H-G1 to H-G4; DEC-029), and `funnelscript-research/spec/typed-event-payloads-v0.md` (H-P1 to H-P4; DEC-030). This describes the current implementation, not an autonomous market simulator.

## Source grammar

```ebnf
WorldFile           ::= "world" Identifier "{" WorldDeclaration* "}" ;
WorldDeclaration    ::= ("entity" | "agent") Identifier "{" WorldMember* "}" ;
WorldMember         ::= StateField | EventDeclaration | RuleDeclaration ;
StateField          ::= "state" Identifier ":" PrimitiveType "=" StateLiteral ";" ;
EventDeclaration    ::= "event" Identifier "(" EventFieldList? ")" ";" ;
EventFieldList      ::= Identifier ":" PrimitiveType ("," Identifier ":" PrimitiveType)* ;
RuleDeclaration     ::= "rule" Identifier "on" "event" Identifier GuardClause? "{" RuleStatement* "}" ;
GuardClause         ::= "when" "(" Identifier GuardOp StateLiteral ")" ;
GuardOp             ::= "==" | "!=" | "<" | "<=" | ">" | ">=" ;
RuleStatement       ::= TransitionStatement | EmitStatement ;
TransitionStatement ::= "transition" Identifier "=" StateExpression ";" ;
EmitStatement       ::= "emit" Identifier ("(" EventArgList? ")")? "after" SignedNumber ";" ;
EventArgList        ::= Identifier "=" StateExpression ("," Identifier "=" StateExpression)* ;
StateExpression     ::= StateLiteral | PayloadReference | Identifier ( ("+" | "-") (StateLiteral | PayloadReference) )? ;
PayloadReference    ::= "payload" "." Identifier ;
PrimitiveType       ::= "int" | "float" | "bool" | "string" ;
```

The complete lexical grammar lives in `funnelscript-research/spec/grammar.ebnf`. `world`, `entity`, `agent`, `state`, `rule`, `on`, `event`, and `transition` are contextual words, not global reserved tokens. This preserves legacy strategy identifiers.

## Execute a minimal World

`examples/counter_world.fnl` contains `Counter.count`, `Counter.active`, and two rules. From the repository root:

```bash
uv run main.py check examples/counter_world.fnl
uv run main.py run-world examples/counter_world.fnl \
  --event Counter.Pulse@0 --event Counter.Pulse@1 --seed 42
```

Expected JSON values: `world = "CounterDemo"`, `state.Counter.count = 2`, `state.Counter.active = true`, and `processed_events = 2`. The event format is `Owner.Event@Time`; timestamps must be finite and nonnegative. The `--event` option is repeatable, and `--max-events` bounds processing. Input event order need not be chronological; the event kernel schedules events by time, priority, and stable insertion order.

## Type and execution rules

- Each declaration name is unique within a World. Fields have unique names and exactly typed primitive initializers; `bool` is not an `int`.
- Optional source `event EventName(field: type, ...)` declarations define a same-owner record schema. Event declaration names and field names must be unique. An undeclared, legacy handler accepts only empty payloads.
- `payload.field` can be read in a rule transition, as a value or the right operand in existing numeric `state +/- payload.field` expressions. The field must exist in the current input event schema and match the assigned type without coercion.
- Within each entity or agent, rule names and listened-to event names must be unique.
- Each rule may assign a state field at most once, and only fields of its own declaration.
- A rule may optionally declare a typed `when (field OP literal)` guard. The field must belong to the rule owner, and its primitive type must exactly match the literal. Numeric fields support all six comparison operators; booleans and strings support only `==` and `!=`.
- Guards inspect the pre-event snapshot. A false guard consumes the input event but performs **no transitions and no source emissions**; the next rule can still process separately scheduled events. Guards do not call functions, sample probability, or invoke external effects.
- Expressions accept primitive literals, same-owner state references and typed `payload.field` references. Numeric state references may add/subtract a numeric literal or payload field of exactly matching numeric type. No implicit int-to-float conversion, string concatenation, function calls, or cross-owner access.
- **Simultaneous assignments:** all right-hand expressions in a rule read the pre-event snapshot. For `a=1,b=2`, `transition a=b; transition b=a;` produces `a=2,b=1`, not `a=2,b=2`.
- Previous states remain unmodified. The executor makes a deep copy of checked World definitions at construction, so subsequent mutations to the caller's AST cannot bypass type checking. Runtime returns the next state, processed event list, inert effect-intent list, and pending events.
- Unknown event handlers fail explicitly. Source `emit Event after Delay;` or `emit Event(field = expr) after Delay;` schedules a local handler. Forward references are valid; target event arguments must match the declared schema exactly, and expressions read the pre-event snapshot. `max_events` bounds zero-delay recursion. Emitted events inherit their parent event priority, including zero-delay emissions. The executor does not emit external effects or reach providers.
- Incoming and generated payloads are validated as exact plain primitive records before handlers run or future events enter the calendar; missing/extra fields, non-string keys, wrong types and non-finite float values fail explicitly. A false guard does not bypass validation.

## Source-generated causal chains

A real source example is `examples/event_chain_world.fnl`:

```bash
uv run main.py check examples/event_chain_world.fnl
uv run main.py run-world examples/event_chain_world.fnl --event Worker.Start@1
```

It schedules `Worker.Step` at t=3 and `Worker.Stop` at t=6, returning `processed_events=3`, `progress=1`, and `active=false`. Each event is processed through the same stable event calendar; `run-world` still needs an initial externally supplied event. Emission is restricted to the same owner; typed payloads are supported under DEC-030, but stochastic delays and cross-owner effects remain out of scope. A typed rule guard can conditionally suppress emission.

## Conditional World rules

`examples/guarded_world.fnl` demonstrates a bounded self-emission chain:

```funnelscript
rule Advance on event Tick when (value < 3) {
  transition value = value + 1;
  emit Tick after 1;
}
```

```bash
uv run main.py run-world examples/guarded_world.fnl --event Counter.Tick@0 --max-events 5
```

The first three events mutate `value` and schedule follow-ups; the fourth event finds the guard false and schedules nothing. The resulting value is 3 and there are no pending events. This does not mean recursion is generally terminating: an always-true self-emitting rule still requires an event limit.

## Typed event records

`examples/payload_world.fnl` declares `Credit(amount: int)` and demonstrates external and internally generated typed messages:

```funnelscript
event Credit(amount: int);
rule Receive on event Credit {
  transition balance = balance + payload.amount;
}
rule Seed on event Start {
  emit Credit(amount = quota) after 2;
  transition quota = 0;
}
```

```bash
uv run main.py run-world examples/payload_world.fnl --event Wallet.Start@3
uv run main.py run-world examples/payload_world.fnl \
  --event '{"name":"Wallet.Credit","time":0,"payload":{"amount":8}}'
```

The first run processes a `Start` at t=3 and a `Credit` at t=5, with `balance=10` from the pre-event quota. The second reads an external JSON payload with `balance=8`. Both finish with zero pending events. Old `Owner.Event@Time` input remains valid.

## Scope and safety boundaries

This World interpreter is distinct from the older marketing-specific `simulate` command, which deliberately rejects World files. World rules alone do **not** model consumer psychology, economics, uncertainty, PyMC Marketing, OmniTwin, or the business consequences of tactics. Those belong in optional, empirical model layers and future standard libraries. Simulation Mode, Shadow Mode and Live Execution Mode require separate effect and safety contracts before integration.

## Verification

```bash
uv run pytest -v tests/test_world_rules.py tests/test_world_emissions.py tests/test_world_guards.py tests/test_world_payloads.py
uv run pytest -v
```

The tests exercise type rejection, state snapshot semantics, calendar order and replay, CLI boundaries, and compatibility with existing strategy tests. Passing tests establish interpreter correctness for this subset, not predictive validity.

# Experimental Language Reference: Typed World Rules and Emitted Events

**Status:** Executable, intentionally minimal. Research authority: `funnelscript-research/spec/rule-transitions-v0.md` (H-R1 to H-R4; DEC-027), `funnelscript-research/spec/event-emission-v0.md` (H-E1 to H-E4; DEC-028), `funnelscript-research/spec/world-guards-v0.md` (H-G1 to H-G4; DEC-029), and `funnelscript-research/spec/typed-event-payloads-v0.md` (H-P1 to H-P4; DEC-030), and `funnelscript-research/spec/stochastic-operators-v0.md` (H-S1 to H-S4; DEC-031). This describes the current implementation, not an autonomous market simulator.

## Source grammar

```ebnf
WorldFile           ::= "world" Identifier "{" WorldDeclaration* "}" ;
WorldDeclaration    ::= ("entity" | "agent") Identifier "{" WorldMember* "}"
                     | "import" StringLiteral ("as" Identifier | "{" NamedImport ("," NamedImport)* "}") ";" ;
NamedImport          ::= Identifier ("as" Identifier)? ;
WorldMember         ::= StateField | EventDeclaration | RuleDeclaration ;
StateField          ::= "state" Identifier ":" PrimitiveType "=" StateLiteral ";" ;
EventDeclaration    ::= "event" Identifier "(" EventFieldList? ")" ";" ;
EventFieldList      ::= Identifier ":" PrimitiveType ("," Identifier ":" PrimitiveType)* ;
RuleDeclaration     ::= "rule" Identifier "on" "event" Identifier GuardClause? "{" RuleStatement* "}" ;
GuardClause         ::= "when" "(" Identifier GuardOp StateLiteral ")" ;
GuardOp             ::= "==" | "!=" | "<" | "<=" | ">" | ">=" ;
RuleStatement       ::= TransitionStatement | EmitStatement ;
TransitionStatement ::= "transition" Identifier "=" TransitionExpression ";" ;
TransitionExpression ::= StateExpression ;
SampleExpression     ::= "sample" ("bernoulli" "(" SampleArgument ")"
                       | "uniform" "(" SampleArgument "," SampleArgument ")") ;
SampleArgument       ::= SignedNumber | PayloadReference | Identifier ;
EmitStatement       ::= "emit" Identifier ("(" EventArgList? ")")? "after" SignedNumber ";" ;
EventArgList        ::= Identifier "=" StateExpression ("," Identifier "=" StateExpression)* ;
StateExpression     ::= AdditiveExpression ;
AdditiveExpression   ::= MultiplicativeExpression (("+" | "-") MultiplicativeExpression)* ;
MultiplicativeExpression ::= PrimaryExpression (("*" | "/") PrimaryExpression)* ;
PrimaryExpression    ::= StateLiteral | PayloadReference | Identifier | "(" StateExpression ")" | SampleExpression ;
PayloadReference    ::= "payload" "." Identifier ;
PrimitiveType       ::= "int" | "float" | "bool" | "string" ;
```

The complete lexical grammar lives in `funnelscript-research/spec/grammar.ebnf`. `world`, `entity`, `agent`, `state`, `rule`, `on`, `event`, `transition`, `import`, and `as` are contextual words, not global reserved tokens. This preserves legacy strategy identifiers.

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
- `payload.field` can be read in a rule transition or as any numeric operand in a typed composable arithmetic expression. The field must exist in the current input event schema and match the assigned type without coercion.
- Within each entity or agent, rule names and listened-to event names must be unique.
- Each rule may assign a state field at most once, and only fields of its own declaration.
- A rule may optionally declare a typed `when (field OP literal)` guard. The field must belong to the rule owner, and its primitive type must exactly match the literal. Numeric fields support all six comparison operators; booleans and strings support only `==` and `!=`.
- Guards inspect the pre-event snapshot. A false guard consumes the input event but performs **no transitions and no source emissions**; the next rule can still process separately scheduled events. Guards do not call functions, sample probability, or invoke external effects.
- Ordinary expressions accept primitive literals, same-owner state references, typed payload references and bounded binary trees. Standard precedence is multiplication/division before addition/subtraction; both levels are left-associative, and parentheses override precedence. Arithmetic operands require matching exact numeric types with no implicit cast. Addition, subtraction and multiplication preserve the operand type; division yields `float`. A literal zero divisor is rejected statically; dynamic zero, non-finite float operands/results and conversion overflow fail with controlled execution diagnostics. Parse complexity is bounded to 24 expression levels and 256 tokens. `//` retains its line-comment meaning. No arbitrary function calls, cross-owner reads or Python execution.

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

It schedules `Worker.Step` at t=3 and `Worker.Stop` at t=6, returning `processed_events=3`, `progress=1`, and `active=false`. Each event is processed through the same stable event calendar; `run-world` still needs an initial externally supplied event. Emission is restricted to the same owner; typed payloads are supported under DEC-030 and stochastic transition expressions under DEC-031, but stochastic delays and cross-owner effects remain out of scope. A typed rule guard can conditionally suppress emission.

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

## Reproducible stochastic transitions (experimental)

`examples/stochastic_world.fnl` demonstrates two source-level probability operators. They are only valid in transition assignment expressions:

```funnelscript
rule Respond on event Impression {
  transition converted = sample bernoulli(payload.conversion_probability);
  transition engagement_score = sample uniform(0.0, 1.0);
}
```

```bash
uv run main.py check examples/stochastic_world.fnl
uv run main.py run-world examples/stochastic_world.fnl \
  --event '{"name":"Shopper.Impression","time":0,"payload":{"conversion_probability":0.25}}' \
  --seed 42
```

`sample bernoulli(p)` produces a bool; `sample uniform(low, high)` produces a float. Each argument must be exactly float: a literal, same-owner state reference, or schema-declared `payload.field`. A probability must be finite and within [0,1]; uniform bounds must be finite and ordered, with a finite representable span. Invalid static arguments fail compilation, while invalid dynamic values fail before the random draw. Source `int` does not implicitly promote to float.

Both operators consume precisely one `random.Random.random()` draw per active evaluation, including zero/one probabilities and equal uniform bounds. A false guard consumes none. Draw order follows transition declaration order; all input references still read the same pre-event snapshot. Repeating the same World, ordered events, seed, and runtime version returns an identical result. Distinct seeds are not guaranteed to yield distinct outcomes. `WorldExecutor.advance` requires a caller-supplied RNG if a sampled transition executes.

No sampling is permitted in guards, source emissions, initialization, delays or legacy strategy files. The mechanism represents **specified stochastic assumptions**, not verified empirical conversion likelihoods. See [Stochastic Operators v0](https://github.com/funnelscript/funnelscript-research/blob/main/spec/stochastic-operators-v0.md) and DEC-031.

## Source-imported World libraries (experimental)

World source may import a **single exported entity or agent** from another World file:

```funnelscript
world HolidayExperiment {
  import "std:marketing/lead_response.fnl" as Prospect;
}
```

This introduces `Prospect` as an ordinary agent, with `Prospect.Impression` as its external event. The imported rules still execute through the same neutral `WorldExecutor`; no marketing keyword or separate marketing runtime was added. The shipped module is `src/funnelscript/stdlib/marketing/lead_response.fnl`. The package wheel includes its source file.

```bash
uv run main.py check examples/marketing_lead_response.fnl
uv run main.py run-world examples/marketing_lead_response.fnl \
  --event '{"name":"Prospect.Impression","time":0,"payload":{"cpc":2.0,"conversion_probability":0.7,"order_value":100.0}}' \
  --seed 1
```

The reference case produces `spend=2.0`, `converted=true`, `revenue=100.0`, two processed events and no pending events. Changing only `--seed` to `2` produces `converted=false`, `revenue=0.0`. The `Lead` library models **a single exposure/journey per run**: repeated Impressions are ignored; it is not yet a population or repeated-campaign accounting engine.

Legacy one-export imports use `import "./custom.fnl" as Custom;` and still require exactly one exported declaration. Multi-declaration modules use explicit named selection such as `import "./bundle.fnl" { Counter as Balance, Visitor as Lead };`. Unselected module owners are not imported. Import resolution remains confined to the importing file's directory or the packaged `std:` namespace. Absolute paths, parent traversal, symlink escapes, cycles, unknown names and duplicate local bindings fail before execution. Direct parser calls without a file path cannot resolve imports.

`cpc` and `order_value` must be provided as finite floats, but **nonnegative monetary bounds are not yet enforced by the generic core**; they remain experiment assumptions. This demonstration is neither a calibrated conversion model nor a finance-valid forecast. See the [v0 Research Contract](https://github.com/funnelscript/funnelscript-research/blob/main/spec/marketing-stdlib-v0.md).

## Scope and safety boundaries

This World interpreter is distinct from the older marketing-specific `simulate` command, which deliberately rejects World files. World rules now support explicit pseudorandom draws, but do **not** model calibrated consumer psychology, economic constraints, empirical uncertainty, PyMC Marketing, OmniTwin, or the business consequences of tactics by default. The first source-defined marketing library is illustrative only; calibrated economic and behavioral models belong in separately validated libraries and adapters. Simulation Mode, Shadow Mode and Live Execution Mode require separate effect and safety contracts before integration.

## Verification

```bash
uv run pytest -v tests/test_world_rules.py tests/test_world_emissions.py tests/test_world_guards.py tests/test_world_payloads.py tests/test_world_stochastic.py tests/test_world_modules.py
uv run pytest -v
```

The tests exercise type rejection, state snapshot semantics, calendar order and replay, CLI boundaries, and compatibility with existing strategy tests. Passing tests establish interpreter correctness for this subset, not predictive validity.


## Reproducible event playbooks (Phase 007G)

The CLI accepts `run-world example.fnl --events-file example.json --seed 42`, with strict UTF-8 JSON `{"schema":"funnelscript-event-playbook-v1","events":[{"name":"Owner.Event","time":0,"payload":{}}]}`. It reuses the existing validated inline-event schema, event priority ordering and exact primitive payload typing. Duplicate JSON keys, unknown fields, negative/non-finite timestamps, wrong priorities, oversized files (over 1 MiB) and more than 10,000 records are rejected. Mixed `--events-file` and `--event` is not supported in this version. The example `examples/phase007g_world.fnl` with `examples/phase007g_events.json` exercises composable numeric expressions, two named imports and two events.

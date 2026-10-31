# FunnelScript CLI Reference Manual

The `funnelscript` command-line interface provides tools for verifying, simulating, and generating marketing strategies using declarative FunnelScript specifications.

---

## Command Overview

```bash
funnelscript [--help] <command> [options]
```

### Commands

| Command | Description | Standard Exit Codes |
| :--- | :--- | :--- |
| `check <file>` | Static semantic verification, Tarjan cycle detection, and invariant analysis | `0` (clean), `1` (defect), `2` (I/O error) |
| `compile <file>` | Alias for `check` | `0`, `1`, `2` |
| `run-world <file>` | Execute explicit events against typed World rules without external effects | `0` (pass), `1` (World or event error) |
| `simulate <file>` | Vectorized Monte Carlo simulation & liquidity stress-testing | `0` (pass), `1` (lint error), `2` (I/O error) |
| `init <name>` | Scaffold a production-ready, pre-validated campaign template | `0` (created) |
| `schema` | Print or export the official Draft 2020-12 JSON Schema | `0` |

---

## Detailed Command Documentation

### 1. `funnelscript check`

Runs static verification against the marketing strategy AST:
- **Graph Reachability:** Ensures all audiences and touchpoints connect to valid traffic flows.
- **Dead-End Detection:** Flags conversion surfaces with 0% conversion rate or no downstream recovery steps.
- **Tarjan's SCC Cycle Detection:** Prevents endless attribution feedback loops between channels.
- **Working Capital Ratio:** Alerts when settlement delay $\Delta_{\text{settle}}$ coupled with initial cash creates high insolvency exposure.

```bash
funnelscript check strategy.fnl.json
```

---

### 2. `funnelscript simulate`

Executes high-throughput agent-based discrete-event simulations over a multi-day timeline.

```bash
funnelscript simulate strategy.fnl.json [options]
```

#### Flags & Options:
* `--trials <int>`: Number of independent Monte Carlo iterations (default: `100`).
* `--agents <int>`: Total synthetic consumers simulated per trial (default: from strategy AST or `10000`).
* `--export-csv <path>`: Exports terminal trial outcomes (Spend, Impressions, Clicks, Conversions, Revenue, ROAS, CAC, Insolvency) to a CSV file.
* `--export-json <path>`: Exports the complete distribution report and risk metrics to JSON.
* `--json`: Suppresses Rich console styling and outputs pure JSON to standard output (ideal for CI/CD pipelines and scripting).

#### Example:
```bash
funnelscript simulate strategy.fnl.json \
  --trials 200 \
  --agents 50000 \
  --export-csv ./results/trials.csv \
  --export-json ./results/report.json
```

---

### 3. `funnelscript run-world` (experimental)

Executes typed, domain-neutral World rules against explicit input events on the existing `EventMachine` calendar. This is a pure in-memory interpreter, not the legacy marketing simulator and not Live Execution.

```bash
funnelscript check examples/counter_world.fnl
funnelscript run-world examples/counter_world.fnl \
  --event Counter.Pulse@0 --event Counter.Pulse@1 --seed 42
```

* `file`: `.fnl` source with a `world` declaration containing `entity` / `agent`, typed `state`, and `rule` definitions.
* `--event OWNER.EVENT@TIME` or JSON: Provide a qualified event and non-negative finite timestamp; can be repeated. For typed payloads, use a JSON record with `name`, `time`, and `payload`, e.g. `--event '{"name":"Wallet.Credit","time":0,"payload":{"amount":8}}'`. The order of repeated flags is preserved.
* `--seed <int>`: Seed for the World run's pseudorandom stream (default `0`). Repeating the same source, ordered events and seed replays the same decisions; other seeds may yield the same result by chance.
* `--max-events <int>`: Positive processing limit (default `100000`). It also bounds recursive zero-delay source emission.

Example with a source-level typed event payload:

```bash
funnelscript run-world examples/payload_world.fnl --event '{"name":"Wallet.Credit","time":0,"payload":{"amount":8}}'
```

An explicit event declaration such as `event Credit(amount: int);` establishes exact field and primitive type checks for both input JSON events and source-emitted arguments. Invalid payloads fail before executing the handler, including when its guard is false. Plain `OWNER.EVENT@TIME` remains available for no-payload events.

Example with seeded stochastic transition expressions:

```bash
funnelscript run-world examples/stochastic_world.fnl \
  --event '{"name":"Shopper.Impression","time":0,"payload":{"conversion_probability":0.25}}' \
  --seed 42
```

The run produces `Shopper.converted=false` and `Shopper.engagement_score=0.025010755222666936`. The `sample bernoulli(float)` and `sample uniform(float, float)` transition operators each consume one draw from the run's seeded pseudorandom stream; guards that do not match consume none. No built-in probability calibration or Live execution is implied.

Example with a typed, self-terminating event guard:

```bash
funnelscript run-world examples/guarded_world.fnl --event Counter.Tick@0 --max-events 5
```

Expected output: `Counter.value = 3`, `processed_events = 4`, and zero pending events. `when (field OP literal)` evaluates typed primitive state before an event's transitions and local emissions. If false, neither action runs, but the input event is counted.

Example using the packaged Marketing Standard Library:

```bash
funnelscript check examples/marketing_lead_response.fnl
funnelscript run-world examples/marketing_lead_response.fnl \
  --event '{"name":"Prospect.Impression","time":0,"payload":{"cpc":2.0,"conversion_probability":0.7,"order_value":100.0}}' \
  --seed 1
```

The source `import "std:marketing/lead_response.fnl" as Prospect;` introduces one reusable single-journey agent as `Prospect` without changing the core grammar's domain neutrality. Seed 1 produces revenue 100.0 and spend 2.0; seed 2 produces revenue 0.0 and spend 2.0. This is an assumption-driven demo, not a market forecast.

Example with a three-event causal chain:

```bash
funnelscript run-world examples/event_chain_world.fnl --event Worker.Start@1
```

Outputs JSON containing `world`, `state`, `processed_events`, and `pending_events`. A missing handler, type violation, invalid timestamp, non-World source, or event limit error returns a nonzero exit code with an explanatory stderr message. World rules may now generate additional **local** events using `emit Event after Delay;`, and these are included in `processed_events` and `pending_events`. Initial events still come from `--event`. No platform effects are executed. See [World Rules Language Reference](LANGUAGE_REFERENCE_WORLD_RULES.md).

---

### 4. `funnelscript init`

Scaffolds a clean starter template complete with entities, touchpoints, budget controls, and retargeting conditional branches.

```bash
funnelscript init "Holiday Campaign" --output ./holiday.fnl.json
```

---

### 5. `funnelscript schema`

Generates the canonical JSON Schema for IDE autocompletion, schema validation, and toolchain integration.

```bash
# Print to stdout
funnelscript schema

# Export to file
funnelscript schema --output spec/schema.json
```

---

## Exit Code Specification

| Code | Label | Cause |
| :---: | :--- | :--- |
| **0** | `SUCCESS` | Strategy compiled, checked, or simulated without invariant violations. |
| **1** | `VALIDATION_OR_RUNTIME_ERROR` | Syntax/invariant failures or, for `run-world`, invalid World input, unknown event, missing file, or processing-limit error. |
| **2** | `IO_ERROR` | Target file does not exist or cannot be read/written. |

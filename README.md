# FunnelScript

> **FunnelScript (experimental):** A domain-neutral language foundation for executable marketing-system models, with typed Worlds, seeded stochastic transitions, and a separate legacy marketing simulator.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)

FunnelScript is an evolving research language for expressing stateful event-driven systems and testing their assumptions in reproducible scenarios. Its World reference interpreter supports typed declarations, rules, event records, guards, local event scheduling and stochastic operators. A separate, earlier marketing-specific simulator remains available. Neither implementation has established out-of-sample market forecasting accuracy.

---

## Key Features

* **Funnel-as-Code (Declarative Syntax):** Write campaigns in high-level declarative syntax or structured JSON intermediate representations.
* **Static Analysis:** Checks World primitive types and rule contracts; the legacy marketing linter reports topology and budget diagnostics. These checks do not prove real-world economic outcomes.
* **Discrete-Event World Kernel:** Orders model-authored events, evaluates pre-event transitions, preserves typed payloads and provides seeded replay within the experimental interpreter.
* **Legacy Marketing Simulation:** Includes model-dependent Monte Carlo scenarios for insolvency and payout delay; outputs depend on supplied assumptions, not verified causal estimates.
* **Module Imports and First Marketing Library:** Reuse a typed `.fnl` World agent from the shipped `std:marketing/lead_response.fnl` source module or a local module, under a name chosen by the author. Calibration adapters remain future work.

---

## Installation

FunnelScript is built with Python 3.12+ and managed via [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/funnelscript/funnelscript.git
cd funnelscript
uv sync
```

### Install and try the versioned Experimental Preview

The `v0.2.0a1` preview is installable straight from its Git tag with `uvx`; it is **not** published to PyPI. Once the tag is available, you can run this outside a repository checkout:

```bash
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript --version
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript init-world first.fnl
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript check first.fnl
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript run-world first.fnl \
  --event '{"name":"Prospect.Impression","time":0,"payload":{"cpc":2.0,"conversion_probability":0.7,"order_value":100.0}}' \
  --seed 1
```

The generated World imports the bundled `std:marketing/lead_response.fnl` module and runs a reproducible **assumption-driven** single-lead journey. See the [complete 5-minute developer preview guide](docs/EXPERIMENTAL_PREVIEW.md) to extend it with a custom World module. This is not empirically validated market prediction or a Live execution mode.

---

## Legacy strategy simulator (separate execution path)

These JSON-based strategy commands belong to the earlier marketing engine. For a first experience with the domain-neutral language, use the source-based World preview above. Neither path predicts observed market outcomes from uncalibrated inputs.

### 1. Validate a Strategy File
Verify that all audiences, touchpoints, and flow paths satisfy domain invariants:

```bash
uv run main.py compile examples/black_friday_2026.json
```

### 2. Run Stochastic Monte Carlo Simulation
Execute $M=100$ trials across $50,000$ synthetic consumer agents:

```bash
uv run main.py simulate examples/black_friday_2026.json --trials 100 --agents 50000
```

---

## Legacy campaign syntax (illustrative `.fnl`, not the World preview)

```hcl
strategy ECommerce_Black_Friday_2026 {
  metadata {
    author = "Marketing Engineer";
    currency = "USD";
  }

  entities {
    budget main_budget {
      total = 25000;
      max_cpc = 1.20;
    }

    audience aud_01 {
      type = "cold";
      size = 500000;
      affinity = 0.55;
      price_sensitivity = 0.40;
      fomo = 0.70;
    }

    touchpoint tp_meta_ads {
      type = "paid_traffic";
      platform = "Meta";
      base_cpc = 0.45;
      creative_score = 0.85;
    }

    touchpoint tp_landing_page {
      type = "conversion_surface";
      conversion_rate = 0.045;
    }

    touchpoint tp_cart_email {
      type = "retargeting_channel";
      medium = "Email";
    }
  }

  flow {
    trigger TrafficDrive from aud_01 via tp_meta_ads to tp_landing_page;
  }

  simulate {
    agents = 50000;
    duration = 14days;
    trials = 100;
  }
}
```

---

## Experimental Language-Neutral Event Kernel

The first model-neutral foundation is available as a Python reference API. User-defined transitions own all world/agent state; the kernel only orders discrete events and records inert effect intents.

```python
from funnelscript.core import Event, EventMachine, Transition

def step(count, event, rng):
    return Transition(state=count + 1)

result = EventMachine(step).run(
    0, (Event(0.0, "first"), Event(2.0, "second")), seed=42
)
assert result.state == 2
```

The kernel is experimental and shared by the typed `world` interpreter. The older marketing-specific `strategy` compiler and simulator use a separate code path. Typed source entities and events now exist, but this API does not grant live effects or empirical market calibration. Its falsifiable contract is documented in [the research repository](https://github.com/funnelscript/funnelscript-research/blob/main/spec/event-kernel-v0.md).

---

## Experimental `world` Syntax and Primitive State Types

FunnelScript now parses a domain-neutral `world` declaration into a typed AST and checks primitive state fields independently of marketing-specific strategy models.

```funnelscript
world WarehouseDemo {
  entity Shelf {
    state quantity: int = 20;
  }

  agent Picker {
    state active: bool = true;
    state confidence: float = 0.75;
  }
}
```

Run `uv run main.py check examples/warehouse_world.fnl` for type validation. Agents are subtypes of entities in the AST. Domain-neutral `rule`/`transition` handlers now execute pure state updates in the event kernel; autonomous agent decisions, market calibration, and Live execution remain out of scope. Existing campaign `strategy` files continue to use their legacy compiler and simulator.

Research contracts: [World Declarations v0](https://github.com/funnelscript/funnelscript-research/blob/main/spec/world-declarations-v0.md) and [Rule Transitions v0](https://github.com/funnelscript/funnelscript-research/blob/main/spec/rule-transitions-v0.md).

### Run typed World rules

```funnelscript
world CounterDemo {
  entity Counter {
    state count: int = 0;
    rule Increment on event Pulse {
      transition count = count + 1;
    }
  }
}
```

```bash
uv run main.py check examples/counter_world.fnl
uv run main.py run-world examples/counter_world.fnl \
  --event Counter.Pulse@0 --event Counter.Pulse@1 --seed 42
```

The second command returns JSON with `Counter.count = 2`. Events are supplied explicitly as `Owner.Event@Time` and handled in timestamp order. Assignment expressions are deliberately restricted to primitive literals, same-owner state references, or numeric state plus/minus numeric literal of exactly the same type. Multiple assignments in one rule read the same pre-event state. No provider calls or predictions are produced. See [World rules reference](docs/LANGUAGE_REFERENCE_WORLD_RULES.md).

---

### Source-generated events

World rules can now schedule more local reactions without another CLI event. `emit Step after 2;` queues a handler on the same owner two abstract time units after the current event. This does not produce external effects or calibrated human behavior.

```bash
uv run main.py run-world examples/event_chain_world.fnl --event Worker.Start@1
```

The example processes `Start`, `Step`, and `Stop` using the same bounded event calendar; expected `processed_events` is `3`. See [Scheduled Event Research](https://github.com/funnelscript/funnelscript-research/blob/main/spec/event-emission-v0.md).

---

### Typed World guards (experimental)

Rules can inspect pre-event state and suppress both transitions and locally emitted events when a guard is false:

```funnelscript
rule Advance on event Tick when (value < 3) {
  transition value = value + 1;
  emit Tick after 1;
}
```

Try the complete bounded example:

```bash
uv run main.py check examples/guarded_world.fnl
uv run main.py run-world examples/guarded_world.fnl --event Counter.Tick@0 --max-events 5
```

The four processed events leave `Counter.value = 3` with no further pending events. Comparisons require matching primitive types; this establishes only deterministic execution behavior, not market-prediction accuracy. See [Typed World Guard Research](https://github.com/funnelscript/funnelscript-research/blob/main/spec/world-guards-v0.md).

---

### Typed World event payloads (experimental)

World authors can define exact event message shapes and read incoming values in rule transitions:

```funnelscript
event Credit(amount: int);
rule Receive on event Credit {
  transition balance = balance + payload.amount;
}
```

```bash
uv run main.py check examples/payload_world.fnl
uv run main.py run-world examples/payload_world.fnl --event Wallet.Start@3
uv run main.py run-world examples/payload_world.fnl \
  --event '{"name":"Wallet.Credit","time":0,"payload":{"amount":8}}'
```

The runtime validates payload field names, exact primitive types and finite float values before processing or scheduling. See the [Typed Event Payload Research Contract](https://github.com/funnelscript/funnelscript-research/blob/main/spec/typed-event-payloads-v0.md). These event-record checks are deterministic; separate World transition expressions now support seeded sampling. Neither constitutes empirically validated consumer simulation.

---

### Seeded stochastic World decisions (experimental)

```funnelscript
rule Respond on event Impression {
  transition converted = sample bernoulli(payload.conversion_probability);
  transition engagement_score = sample uniform(0.0, 1.0);
}
```

Run the complete [stochastic World example](examples/stochastic_world.fnl):

```bash
uv run main.py check examples/stochastic_world.fnl
uv run main.py run-world examples/stochastic_world.fnl \
  --event '{"name":"Shopper.Impression","time":0,"payload":{"conversion_probability":0.25}}' \
  --seed 42
```

With seed 42 and the provided event, the reference interpreter returns `converted=false` and `engagement_score=0.025010755222666936`. Repeating the same scenario and seed reproduces that output. `bernoulli` draws a bool, `uniform` draws a float, and both require exact float parameters. The probability must be in [0,1]; uniform bounds must be finite and ordered. These are **model-specified** probabilities, not estimated market response rates. See the [stochastic specification](https://github.com/funnelscript/funnelscript-research/blob/main/spec/stochastic-operators-v0.md).

---

### Import a Marketing Standard Library agent (experimental)

World projects can now import another `.fnl` module. The built-in Marketing library remains ordinary FunnelScript source, rather than a new set of marketing-specific compiler keywords:

```funnelscript
world HolidayExperiment {
  import "std:marketing/lead_response.fnl" as Prospect;
}
```

Try the [complete example](examples/marketing_lead_response.fnl):

```bash
uv run main.py check examples/marketing_lead_response.fnl
uv run main.py run-world examples/marketing_lead_response.fnl \
  --event '{"name":"Prospect.Impression","time":0,"payload":{"cpc":2.0,"conversion_probability":0.7,"order_value":100.0}}' \
  --seed 1
```

This single-lead journey spends a scenario-defined 2.0, samples a conversion, and schedules a typed Checkout. With seed 1 it reports `converted=true` and `revenue=100.0`; with seed 2 it reports `converted=false` and `revenue=0.0`. These inputs are user assumptions; the language does not infer market probabilities, enforce nonnegative money inputs in this module, or model a customer population yet. Local modules are supported with `import "./local.fnl" as Alias;` (one declaration exported per module in v0). See [Module Import and Marketing Standard Library Research](https://github.com/funnelscript/funnelscript-research/blob/main/spec/marketing-stdlib-v0.md).

---

## Documentation & Community

* **[Developer Agent Skills](agents/README.md):** 22 repository-bundled skills, discovery paths, validation commands and known upstream dependency limits.
* **[Experimental Developer Preview Guide](docs/EXPERIMENTAL_PREVIEW.md):** Versioned Git install, first World, custom local module and failure boundaries.
* **[Public Research Preview Readiness](docs/PUBLIC_PREVIEW_READINESS.md):** Evidence-based announcement gates and current limitations.
* **[Contributing Guide](CONTRIBUTING.md):** Setup, testing standards, and good-first-issue taxonomy.
* **[Open-Source Growth Playbook](docs/OPEN_SOURCE_GROWTH_PLAYBOOK.md):** Strategy for community scaling and contributor lifecycle.
* **[Package Manager Specification (`fpm`)](docs/fpm.md):** Modular libraries, manifests, lockfiles, and commercial incentives.
* **[Marketing Systems Engineering](docs/MARKETING_SYSTEMS_ENGINEERING.md):** Manifesto, mental models, and the MSE practitioner persona.
* **[The Shim Strategy](docs/SHIM_STRATEGY.md):** Specification-first adoption and the linter wedge.
* **[Architecture Decisions (DECISIONS.md)](docs/DECISIONS.md):** Canonical records of accepted architectural decisions.
* **[Engineering Debates (DEBATES.md)](docs/DEBATES.md):** Falsifiable trade-offs and operational boundary decisions.
* **[Out of the Box Ideas (OUT_OF_THE_BOX.md)](docs/OUT_OF_THE_BOX.md):** Frontier research tracking and speculative hypotheses.

---

## Running the Test Suite

```bash
uv run pytest -v
```

---

## Research & Foundations

For the theoretical paper, formal EBNF grammar, and mathematical proofs, see our sister repository:
👉 [funnelscript/funnelscript-research](https://github.com/funnelscript/funnelscript-research)

## License

MIT License.

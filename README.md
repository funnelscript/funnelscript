# FunnelScript

> **FunnelScript:** A Declarative Domain-Specific Language (DSL) and Stochastic Agent-Based Simulation Runtime for Marketing Systems Engineering.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)

FunnelScript replaces informal marketing spreadsheets and vague whiteboard diagrams with mathematically verified, executable state machines. It compiles campaign topologies into an Abstract Syntax Tree (AST), enforces economic conservation invariants at compile time, and runs multi-scale Monte Carlo agent-based simulations prior to capital deployment.

---

## Key Features

* **Funnel-as-Code (Declarative Syntax):** Write campaigns in high-level declarative syntax or structured JSON intermediate representations.
* **Compile-Time Static Type-Checking:** Guarantees audience mass balance, budget non-negativity, and unreachable node detection at $t=0$.
* **Multi-Scale Discrete-Event Engine:** Simulates click interactions in seconds, abandonment latency in hours, and revenue settlement across days without memory race conditions.
* **Cash Ruin Probability ($P(\text{Insolvency})$):** Identifies working-capital freezes caused by payment processor payout delays ($\Delta_{\text{settle}}$), even for strategies with theoretical high ROAS.
* **Discount Cannibalization Telemetry:** Detects margin erosion when loyal buyers intentionally abandon carts to harvest automated incentives.

---

## Installation

FunnelScript is built with Python 3.12+ and managed via [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/funnelscript/funnelscript.git
cd funnelscript
uv sync
```

---

## Quick Start

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

## Sample Syntax (`.fnl`)

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

The kernel is experimental and separate from the existing marketing-specific `.fnl` compiler and vectorized simulator. No generic entity syntax, effect handlers, live providers, or empirical calibration is implied by this API. Its falsifiable contract is documented in [the research repository](https://github.com/funnelscript/funnelscript-research/blob/main/spec/event-kernel-v0.md).

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

## Documentation & Community

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

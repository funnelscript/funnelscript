# The Shim Strategy: Specification-First Adoption & The Linter Wedge

> **Strategic proposal.** The installed CLI and World preview are documented separately; performance targets, integrations and future adoption strategies here are hypotheses, not shipped guarantees.

---

## 1. The Language Cold-Start Dilemma

Building an end-to-end programming language runtime is a massive, multi-year engineering undertaking. An autonomous agent-based marketing engine requires:
* AST lexers and parsers.
* Static semantic analysis and type checking.
* High-throughput SIMD vectorized simulation engines ($10^5$ agents/sec).
* Multi-timescale discrete-event calendars ($\tau$-scheduler).
* Statistical calibration bridges to Bayesian econometrics (PyMC-Marketing).
* Production provider adapters (Meta, Google, Klaviyo).

If the project waits until every execution layer, provider adapter, and distributed compute cluster is 100% complete before open-sourcing, two fatal failure modes occur:
1. **Echo-Chamber Development:** The core architecture hardcodes private assumptions that diverge from real-world practitioner needs.
2. **Adoption Inertia:** Potential contributors cannot evaluate the project's vision without an immediate, working entry point.

---

## 2. The Solution: The 4-Stage Shim Wedge

The "Shim Strategy" decouples **specification credibility** and **static risk verification** from **runtime execution complexity**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          The 4-Stage Shim Wedge                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     │                                 │                                 │
     ▼                                 ▼                                 ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│ Stage 1: Formal Spec    │ │ Stage 2: The Linter Shim│ │ Stage 3: Community Pull │
│ - EBNF Grammar          │ │ - funnelscript check    │ │ - Attracting Compiler   │
│ - AST Schemas           │ │ - Detects Disasters     │ │   & Runtime Talent      │
│ - Academic Whitepaper   │ │ - Sub-50ms CLI / CI     │ │ - Real User Demand      │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
                                                                 │
                                                                 ▼
                                                    ┌─────────────────────────┐
                                                    │ Stage 4: Multi-Target   │
                                                    │ Execution Runtimes      │
                                                    │ - Python SIMD           │
                                                    │ - Rust / WASM           │
                                                    │ - Julia LLVM Clusters   │
                                                    └─────────────────────────┘
```

### Stage 1: The Formal Specification (Academic Credibility)
Before releasing code, establish mathematical and syntactic foundations:
* Complete, unambiguous **EBNF Grammar** (`spec/grammar.ebnf`).
* Formally validated **AST Schemas** (`spec/schema.json`).
* Peer-reviewed research paper defining the stochastic customer automaton ($M$), discrete-event scheduling ($\tau$), and working capital ruin mechanics ($P(\text{Insolvency})$).
* **Outcome:** Establishes instant academic and engineering authority. FunnelScript is recognized as a scientific standard, not a toy script.

### Stage 2: The Linter as a Wedge (`funnelscript check`)
The fastest way to deliver tangible value is through static analysis. A lightweight, zero-dependency linter runs in $< 30\text{ms}$ and detects catastrophic strategic errors without requiring a simulation engine:
* **Audience Mass Balance Leaks:** Flags when transition probabilities fail to sum to $1.0$, identifying lost customers.
* **Cyclic Attribution Traps:** Identifies closed loops where marketing spend recirculates indefinitely without reaching conversion sinks.
* **Cash Starvation Cliffs:** Compares initial working capital against ad spend burn rates and gateway settlement latency ($\Delta_{\text{settle}}$), warning of imminent cash insolvency.
* **Unbounded Spend Gas:** Rejects loops or triggers lacking a static ceiling ($C_{\text{max}}$).

**The Operational Win:** Organizations can immediately install `funnelscript` via `uv tool` or `npx` and add `funnelscript check` to their Git pre-commit hooks and CI/CD pipelines. It saves money on Day 1 by preventing broken campaigns from reaching production.

### Stage 3: The Talent Gravitational Pull
When developers and marketing data scientists use `funnelscript check` to audit their strategies, they experience the clarity of the declarative syntax.

Once the language has active users, compiler engineers, Rustaceans, and simulation researchers are drawn to contribute:
* They are not asked to invent a language from scratch; the EBNF grammar, AST types, and test suites already exist.
* They are invited to solve well-defined, exciting systems problems: optimizing SIMD kernels, building WebAssembly runners for browsers, or authoring platform connectors.

### Stage 4: Pluggable Multi-Backend Runtime
With community momentum, the runtime evolves into multiple interchangeable execution targets:
1. **Python SIMD (Reference Implementation):** High developer ergonomics, seamless integration with PyMC-Marketing and NumPy data science pipelines.
2. **Rust / WebAssembly Backend:** Ultra-fast, zero-dependency in-browser simulation running directly inside documentation pages and web dashboards.
3. **Julia / Mojo LLVM Cluster Backend:** Scaled to billions of agents for national macroeconomic consumer simulations.

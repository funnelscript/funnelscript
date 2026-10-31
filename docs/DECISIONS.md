# DECISIONS.md: Architecture Decision Records & Canonical Ledger

> Immutable log of foundational engineering, mathematical, and architectural decisions governing the FunnelScript language, compiler, runtime, and research ecosystem.

---

## Decision Index

| ID | Title | Date | Status | Primary Driver |
| :---: | :--- | :---: | :---: | :--- |
| **DEC-001** | [Core-Outwards 5-Phase Implementation Strategy](#dec-001-core-outwards-5-phase-implementation-strategy) | 2026-10-31 | **Accepted** | Inside-Out engineering discipline; mathematical core before UI |
| **DEC-002** | [Hypothesis-First & Research-Gated Engineering](#dec-002-hypothesis-first--research-gated-engineering) | 2026-10-31 | **Accepted** | Preventing speculative implementation; scientific falsifiability |
| **DEC-003** | [Parsimonious Calibrated Micro-Foundations over LLM Personas](#dec-003-parsimonious-calibrated-micro-foundations-over-llm-personas) | 2026-10-31 | **Accepted** | Identifiability barrier & SIMD throughput scaling ($10^5$ agents) |
| **DEC-004** | [Downside Catastrophe Stress-Testing over Point-Forecasts](#dec-004-downside-catastrophe-stress-testing-over-point-forecasts) | 2026-10-31 | **Accepted** | Aleatoric market volatility; insolvency cliff detection |
| **DEC-005** | [Decoupled Statistical Calibration Contract with PyMC Marketing](#dec-005-decoupled-statistical-calibration-contract-with-pymc-marketing) | 2026-10-31 | **Accepted** | Complementarity: Macro Bayesian MMM vs. Micro Forward ABM |
| **DEC-006** | [Two-Tier Hybrid Agent Architecture (Population vs. Cognitive)](#dec-006-two-tier-hybrid-agent-architecture-population-vs-cognitive) | 2026-10-31 | **Accepted** | Computational scaling ($10^5$ SIMD agents + $10^2$ OmniTwin agents) |
| **DEC-007** | [Epistemic Decoupling: World Truth vs. Agent Belief](#dec-007-epistemic-decoupling-world-truth-vs-agent-belief) | 2026-10-31 | **Accepted** | Modeling human cognitive bias, misinformation, and imperfect perception |
| **DEC-008** | [The 4-Layer Stack: DSL Kernel vs. First-Party Standard Library](#dec-008-the-4-layer-stack-dsl-kernel-vs-first-party-standard-library) | 2026-10-31 | **Accepted** | FunnelScript is a Programming Language, not a simulation tool |
| **DEC-009** | [Decoupling Economic Invariants from Compiler Axioms](#dec-009-decoupling-economic-invariants-from-compiler-axioms) | 2026-10-31 | **Accepted** | Expressive user-defined `constraint` blocks (BNPL, Debt, Churn) |
| **DEC-010** | [The Ontological Subtyping Principle: Agent ⊂ Entity](#dec-010-the-ontological-subtyping-principle-agent--entity) | 2026-10-31 | **Accepted** | Passive state containers vs. autonomous decision actors |
| **DEC-011** | [The Living Intellectual Trilogy Mandate](#dec-011-the-living-intellectual-trilogy-mandate) | 2026-10-31 | **Accepted** | Mandatory synchronization of Debates, Decisions, and Out-of-the-Box ledgers |
| **DEC-012** | [FCM-001: Event-Driven Stochastic State Machine Computational Model](#dec-012-fcm-001-event-driven-stochastic-state-machine-computational-model) | 2026-10-31 | **Accepted** | Zeigler's DEVS formalism; multi-timescale simulation scaling |
| **DEC-013** | [FCM-002: Dual-Mode Execution Architecture & Koka-Style Effect System](#dec-013-fcm-002-dual-mode-execution-architecture--koka-style-effect-system) | 2026-10-31 | **Accepted** | Separation of pure strategy logic from real-world side-effects |
| **DEC-014** | [Shadow Execution Mode for Risk-Free Live Observation](#dec-014-shadow-execution-mode-for-risk-free-live-observation) | 2026-10-31 | **Accepted** | Real-world webhook evaluation with zero mutations |
| **DEC-015** | [Idempotency Keys and Compensating Actions for Irreversible Live Operations](#dec-015-idempotency-keys-and-compensating-actions-for-irreversible-live-operations) | 2026-10-31 | **Accepted** | At-most-once execution & compensating sagas for marketing effects |
| **DEC-016** | [The Terraform-Julia-Solidity Architectural Triad](#dec-016-the-terraform-julia-solidity-architectural-triad) | 2026-10-31 | **Accepted** | Unifying Declarative IaC, High-Performance ABM, and Financial Safety |
| **DEC-017** | [The Provider Contract Abstraction & Plan-vs-Apply Lifecycle](#dec-017-the-provider-contract-abstraction--plan-vs-apply-lifecycle) | 2026-10-31 | **Accepted** | Decoupling external platforms via pluggable providers and speculative DAG diffs |
| **DEC-018** | [Static Financial Invariants & Budget Gas Ceilings](#dec-018-static-financial-invariants--budget-gas-ceilings) | 2026-10-31 | **Accepted** | Smart-contract-inspired compile-time budget verification and runtime spend halts |
| **DEC-019** | [Domain-Neutral Event Kernel v0 and Inert Effect Intents](#dec-019-domain-neutral-event-kernel-v0-and-inert-effect-intents) | 2026-10-31 | **Accepted** | Executable substrate for DEC-008/012/013 without domain coupling |
| **DEC-020** | [Dual Distribution Model (Zero-Install NPX/Bunx & Isolated Python Tooling)](#dec-020-dual-distribution-model-zero-install-npxbunx--isolated-python-tooling) | 2026-10-31 | **Accepted** | Frictionless DX across marketing technologists (Node) and ML engineers (Python) |
| **DEC-021** | [IDE Ecosystem Integration via Language Server Protocol (LSP)](#dec-021-ide-ecosystem-integration-via-language-server-protocol-lsp) | 2026-10-31 | **Accepted** | Real-time in-editor AST linting and red squiggly error detection in VS Code/Cursor |
| **DEC-022** | [Contextual World Declarations and Strict Primitive State Typing](#dec-022-contextual-world-declarations-and-strict-primitive-state-typing) | 2026-10-31 | **Accepted** | Additive language syntax and typed AST without marketing schema dependency |
| **DEC-023** | [Formal 4-Pillar Documentation Architecture (Docs as Code)](#dec-023-formal-4-pillar-documentation-architecture-docs-as-code) | 2026-10-31 | **Accepted** | Knowledge scaffolding across tutorials, specs, Bayesian data, and anti-patterns |
| **DEC-024** | [The Modular Library, Framework, and Package Manager Ecosystem (fpm)](#dec-024-the-modular-library-framework-and-package-manager-ecosystem-fpm) | 2026-10-31 | **Accepted** | Strategy reusability, business frameworks, industry benchmarks, and fpm registry |
| **DEC-025** | [Specification-First Open-Source Adoption & Shim Strategy](#dec-025-specification-first-open-source-adoption--shim-strategy) | 2026-10-31 | **Accepted** | Credibility-first open source, formal spec release, and linter-as-wedge adoption |
| **DEC-026** | [Community Contribution Architecture (CONTRIBUTING.md & Issue Standard)](#dec-026-community-contribution-architecture-contributingmd--issue-standard) | 2026-10-31 | **Accepted** | Low-friction onboarding, architectural boundaries, RFC governance, and triage taxonomy |
| **DEC-027** | [Contextual World Rules and Snapshot-Atomic Transitions](#dec-027-contextual-world-rules-and-snapshot-atomic-transitions) | 2026-10-31 | **Accepted** | Pure source-level handlers and simultaneous state transitions via EventMachine |
| **DEC-028** | [Source-Scheduled Local Events Through the Existing Event Calendar](#dec-028-source-scheduled-local-events-through-the-existing-event-calendar) | 2026-10-31 | **Accepted** | Type-checked `emit` and bounded deterministic event scheduling |
| **DEC-029** | [Type-Checked Pre-Event Guards for World Rules](#dec-029-type-checked-pre-event-guards-for-world-rules) | 2026-10-31 | **Accepted** | Deterministic conditional execution of typed World rules |
| **DEC-030** | [Exact-Typed Local Event Records at Both Calendar Boundaries](#dec-030-exact-typed-local-event-records-at-both-calendar-boundaries) | 2026-10-31 | **Accepted** | Static message schemas, strict ingress and pre-enqueue checking |

---

## Detailed Architecture Decision Records

### DEC-001: Core-Outwards 5-Phase Implementation Strategy
* **Status:** Accepted
* **Context:** A complete marketing programming ecosystem requires an agent cognitive model, an AST parser, a static type linter, a high-throughput runtime simulation engine, developer tooling, and visual web interfaces.
* **Decision:** Enforce a strict inside-out development sequence:
  $$\text{Agent Mind (P1)} \longrightarrow \text{AST \& Linter (P2)} \longrightarrow \text{Vectorized Runtime (P3)} \longrightarrow \text{CLI Suite (P4)} \longrightarrow \text{Web Dashboard (P5)}$$
* **Rationale:** Premature authoring of visual interfaces or surface-level syntactic wrappers masks foundational mathematical or algorithmic flaws. The core engine must be green before outward layers are constructed.
* **Consequences:** All five phases executed with 100% verification (29 Python tests green, 66M agent-days/sec throughput, Bun test green, Vite build clean).

---

### DEC-002: Hypothesis-First & Research-Gated Engineering
* **Status:** Accepted
* **Context:** AI coding agents frequently generate ungrounded code, speculative interfaces, or tautological mocks without rigorous verification.
* **Decision:** Institute an ironclad constitutional directive in `AGENTS.md`: No agent may generate, modify, or commit code without first articulating:
  1. The Research Anchor (prior art citation).
  2. The Falsifiable Hypothesis ($H$).
  3. The Mathematical Invariant (formal equation or boundary condition).
* **Rationale:** Engineering discipline demands that every code alteration is a testable experiment designed to falsify a precise hypothesis.
* **Consequences:** Code commits map 1:1 to verified scientific hypotheses ($H_{3.1}$ through $H_{5.2}$).

---

### DEC-003: Parsimonious Calibrated Micro-Foundations over LLM Personas
* **Status:** Accepted
* **Context:** Debate between instantiating $100,000$ consumers as prompt-engineered LLM personas vs. closed-form numeric vectors.
* **Decision:** Standardize agent micro-foundations on 10–15 orthogonal, mathematically bounded variables ($\alpha, \beta, \gamma, \kappa, w, s$) executed via vectorized SIMD array broadcasting (NumPy 2.x). Reserve LLMs strictly for qualitative copy analysis in offline calibration passes.
* **Rationale:** LLM-per-agent architectures suffer from parameter unidentifiability, extreme latency ($> 10\text{ hours/trial}$), non-reproducibility, and financial hallucination. Numeric micro-foundations execute at $66,000,000\text{ agent-days/second}$.
* **Consequences:** Scalable Monte Carlo simulations with guaranteed deterministic random seeds.

---

### DEC-004: Downside Catastrophe Stress-Testing over Point-Forecasts
* **Status:** Accepted
* **Context:** Marketing platforms often sell deterministic forecasting ("This funnel will make \$150k"). Real markets are open stochastic systems with aleatoric variance.
* **Decision:** FunnelScript will never output scalar deterministic predictions. All outputs are multi-trial probability distributions ($P_{10}, P_{50}, P_{90}, \text{Mean}$) accompanied by Value-at-Risk ($\text{VaR}_{95}$), Expected Shortfall ($\text{CVaR}_{95}$), and Cash Ruin Probability ($P(\text{Insolvency})$).
* **Rationale:** Capital preservation precedes profit optimization. Identifying payment clearance starvation cliffs ($\Delta_{\text{settle}}$) saves businesses from bankruptcy before deployment.
* **Consequences:** Telemetry engine explicitly models clearance lag and halts ad spend upon operational reserve depletion.

---

### DEC-005: Decoupled Statistical Calibration Contract with PyMC Marketing
* **Status:** Accepted
* **Context:** The discovery of `imMamdouhaboammar/pymc-marketing-mcp` (66 Bayesian capabilities) raised the question of whether to merge MMM and FunnelScript into a single codebase.
* **Decision:** Keep both projects completely decoupled. Interface exclusively through a versioned JSON schema: `calibration_manifest.json`.
* **Rationale:** PyMC Marketing solves the retrospective macro problem (*"What does historical data prove about channel elasticity and posterior uncertainty?"*). FunnelScript solves the prospective micro problem (*"What happens if we deploy this novel multi-step dynamic strategy tomorrow?"*). Tight coupling would compromise the agility and CI suites of both codebases.
* **Consequences:** FunnelScript consumes posterior adstock decay ($\lambda$), saturation limits ($K$), and decision gate flags (`diagnose_mmm`) directly from PyMC exports.

---

### DEC-006: Two-Tier Hybrid Agent Architecture (Population vs. Cognitive)
* **Status:** Accepted
* **Context:** Evaluating the role of `imMamdouhaboammar/OmniTwin` (Cognitive Continuity Engine with hierarchical memory, allostasis, and state reducers).
* **Decision:** Adopt a two-tier hybrid architecture:
  * **Tier 1 (Population Agents, $N = 10^5 - 10^6$):** Fast, numeric SIMD state machines for statistical significance and financial distribution metrics.
  * **Tier 2 (Cognitive Sentinel Agents, $N = 10^1 - 10^2$):** Selected focal personas equipped with hierarchical memory and state reduction (via OmniTwin adapters) to qualitatively test message framing, brand sentiment drift, and narrative resonance.
* **Rationale:** Harmonizes macro-statistical rigor with micro-qualitative plausibility without computational blowup.
* **Consequences:** Zero slowdown for the core vectorized simulation engine.

---

### DEC-007: Epistemic Decoupling: World Truth vs. Agent Belief
* **Status:** Accepted
* **Context:** OmniTwin employs a *"No ID, No Claim"* constraint to prevent AI hallucinations. In market simulation, consumers frequently hold false beliefs, miscalculate discounts, or act on unverified rumors.
* **Decision:** Decouple the Physical World State from the Agent's Epistemic Belief State:
  $$\text{AgentBelief}_i(t) \neq \text{WorldTruth}(t)$$
* **Rationale:** Forcing synthetic consumers to possess perfect information destroys the realism of human market dynamics (bounded rationality, asymmetrical information, social contagion).
* **Consequences:** Agents can transition states based on subjective, distorted valuations of products and promotions.

---

### DEC-008: The 4-Layer Stack: DSL Kernel vs. First-Party Standard Library
* **Status:** Accepted
* **Context:** Determining whether terms like `audience`, `touchpoint`, `campaign`, and `conversion` should be hardcoded compiler keywords.
* **Decision:** Formalize FunnelScript as a 4-tier stack:
  1. **Layer 01 (Language Core):** Minimal computational primitives (`entity`, `agent`, `state`, `event`, `transition`, `rule`, `probability`, `constraint`).
  2. **Layer 02 (Execution Runtime):** Discrete-event simulation scheduler.
  3. **Layer 03 (Official Standard Library):** `std::marketing` defining `Audience`, `Touchpoint`, and `Campaign` using public language primitives with zero secret compiler privileges.
  4. **Layer 04 (Community Ecosystem):** Sector-specific and regional market packages.
* **Rationale:** Establishes FunnelScript as an extensible, general programming language (analogous to SQL or Julia) rather than a rigid, single-purpose software application.
* **Consequences:** Third-party developers have first-class capabilities to create alternative domain libraries (e.g. B2B procurement models, influencer ecosystems).

---

### DEC-009: Decoupling Economic Invariants from Compiler Axioms
* **Status:** Accepted
* **Context:** Hardcoding population mass conservation ($\sum N = N_{\text{total}}$), strict zero-credit wallet limits ($P \le w$), and liquid cash halts into the compiler prevents modeling open markets, BNPL, or revolving debt facilities.
* **Decision:** Remove model-specific assumptions from the core grammar. Provide generic, expressive constraint declarations:
  ```ebnf
  ConstraintDeclaration ::= "constraint" Identifier "{" Expression "}"
  ```
* **Rationale:** The compiler checks syntax, types, and topological validity. Economic models define their own boundary invariants via explicit constraint declarations.
* **Consequences:** Full expressive versatility across diverse business structures and geographies.

---

### DEC-010: The Ontological Subtyping Principle: Agent ⊂ Entity
* **Status:** Accepted
* **Context:** Defining the primary actors and state containers of a FunnelScript program.
* **Decision:** Formalize that all Agents are Entities, but not all Entities are Agents:
  $$\text{Agent} \subset \text{Entity}$$
  * **Entity:** A passive or externally mutated state container (e.g. `Budget`, `Inventory`, `AdUnitSlot`).
  * **Agent:** An Entity possessing bounded rationality, internal decision rules, and autonomous initiation (e.g. `Consumer`, `Competitor`, `Bidder`).
* **Rationale:** Eliminates conceptual ambiguity in the language type system and simplifies runtime event dispatch.
* **Consequences:** Clear inheritance hierarchy in AST node models and runtime state management.

---

### DEC-011: The Living Intellectual Trilogy Mandate
* **Status:** Accepted
* **Context:** Engineering knowledge, architectural trade-offs, and visionary ideas are frequently lost across development sessions or isolated in transient chat logs.
* **Decision:** Mandate the continuous, simultaneous maintenance of the **Living Intellectual Trilogy** across all sessions:
  1. [`DEBATES.md`](DEBATES.md): Active philosophical conflicts, trade-offs, and dialectical synthesis.
  2. [`DECISIONS.md`](DECISIONS.md): Immutable canonical log of accepted architectural records.
  3. [`OUT_OF_THE_BOX.md`](OUT_OF_THE_BOX.md): Speculative, frontier, non-linear ideas revolving around the core vision.
* **Rationale:** Ensures durable institutional memory, complete traceability, and constant alignment between code and vision.
* **Consequences:** Enforced as a mandatory rule in `AGENTS.md`.

---

### DEC-012: FCM-001 — Event-Driven Stochastic State Machine Computational Model
* **Status:** Accepted
* **Context:** Fixed daily or step-wise tick loops cannot model intraday multi-timescale events (e.g. ad auctions at $t=10^{-3}\text{s}$, sessions at $t=10^1\text{min}$, cart recovery at $t=2\text{h}$, settlement clearing at $t=3\text{d}$) without prohibitive computational overhead.
* **Decision:** Establish Zeigler’s Discrete Event Systems Specification (DEVS) as the foundational execution model of FunnelScript:
  $$W_{t^+} = \mathcal{T}(W_t, e_t, \theta, \xi_t)$$
  * The runtime driver maintains a min-heap priority calendar $\mathcal{Q}$ of discrete events ordered by $(\tau_e, \pi_e)$.
  * Continuous background phenomena (e.g. adstock carryover, brand decay) are computed lazily via analytic step functions upon event arrival.
  * Deterministic pseudo-random seeds guarantee bit-for-bit replayability.
* **Rationale:** Eliminates millions of empty loop iterations while providing exact temporal resolution for asynchronous marketing interventions.
* **Consequences:** Vectorized cohort batching handles $10^5$ synthetic agents with microsecond event dispatch efficiency.

---

### DEC-013: FCM-002 — Dual-Mode Execution Architecture & Koka-Style Effect System
* **Status:** Accepted
* **Context:** Unifying offline simulation and live production deployment within one language without polluting simulation loops with network I/O or risking accidental live ad spend.
* **Decision:** Decouple tactical strategy logic from side-effect execution via an **Algebraic Effect System**:
  * Compiled FunnelScript rules yield pure, immutable **`EffectIntent`** values (e.g. `AdjustBudgetIntent`, `DispatchMessageIntent`, `HaltSpendIntent`).
  * Effects are executed exclusively by interchangeable, pluggable handlers:
    1. `SimulatedEffectHandler`: Updates in-memory vector arrays with zero network I/O.
    2. `ShadowEffectHandler`: Passively monitors real webhook traffic without emitting external mutations.
    3. `LiveEffectHandler`: Validates safety ceilings, computes HMAC signatures, and calls external provider APIs (Meta, Klaviyo, Shopify).
* **Rationale:** Pure strategies remain 100% testable and side-effect free in simulation, while the identical compiled AST can be safely deployed to live production.
* **Consequences:** The compiler never links against HTTP clients or API credentials; all side-effects are sandboxed at runtime.

---

### DEC-014: Shadow Execution Mode for Risk-Free Live Observation
* **Status:** Accepted
* **Context:** Deploying an algorithmic marketing strategy directly to live execution carries severe financial risk if synthetic consumer assumptions diverge from real consumer behavior.
* **Decision:** Introduce a first-class **Shadow Execution Mode**:
  * The runtime ingests real-world event webhooks from live platforms (Shopify orders, Meta spend reports, Stripe webhooks).
  * The strategy state machine evaluates rules in real time, recording all intended actions and computing predicted metrics.
  * Outbound network mutations are intercepted and suppressed; divergence metrics ($\Delta_{\text{actual vs predicted}}$) are logged to telemetry.
* **Rationale:** Provides an empirical burn-in observation period to validate strategy behavior and detect modeling drift before committing real marketing capital.
* **Consequences:** Establishes a zero-risk bridge between offline simulation and live capital deployment.

---

### DEC-015: Idempotency Keys and Compensating Actions for Irreversible Live Operations
* **Status:** Accepted
* **Context:** Unlike relational databases where transactions can be rolled back via `ROLLBACK`, external marketing actions (sent emails, SMS messages, published ad sets) cannot be un-executed. Network retries can also trigger duplicate billing.
* **Decision:**
  * Mandate deterministic SHA-256 idempotency keys for all live mutations:
    $$\text{Key} = \text{SHA256}(\text{strategy\_id} \parallel \text{event\_id} \parallel \tau_e)$$
  * Require explicit **Compensating Actions** (Saga pattern) for irreversible side effects when a campaign is paused, canceled, or fails mid-execution (e.g. deactivating a leaked discount code or dispatching correction notifications).
* **Rationale:** Guarantees at-most-once execution semantics and predictable failure recovery across distributed third-party marketing APIs.
* **Consequences:** `LiveEffectHandler` verifies idempotency state before dispatching any provider API mutation.

---

### DEC-016: The Terraform-Julia-Solidity Architectural Triad
* **Status:** Accepted
* **Context:** Marketing systems require a unique fusion of declarative infrastructure topology, stochastic agent simulation, and high-stakes financial risk management.
* **Decision:** Formally ground FunnelScript upon three architectural pillars:
  1. **Terraform (IaC):** Declarative Marketing as Code, resource DAG dependencies, and `plan` vs `apply` execution lifecycle.
  2. **Julia / Agents.jl (ABM):** High-performance numerical simulation, vectorized SIMD array processing, and discrete-event scheduling.
  3. **Solidity / Move (Smart Contracts):** Static invariant analysis, bounded budget gas consumption, and financial anti-drain protection.
* **Rationale:** Eliminates arbitrary ad-hoc designs by borrowing proven paradigms from cloud infrastructure, computational physics, and financial cryptosystems.
* **Consequences:** Architectural consensus established; all future compiler and runtime features must trace back to this triad.

---

### DEC-017: The Provider Contract Abstraction & Plan-vs-Apply Lifecycle
* **Status:** Accepted
* **Context:** Coupling the compiler grammar to specific ad platforms (Meta, Google, TikTok, Klaviyo, Shopify) would create brittle lock-in and violate world-model neutrality.
* **Decision:**
  * Define generic `provider` and `resource` contracts in the core EBNF grammar (Layer 01).
  * Enforce a two-phase operational lifecycle:
    * `funnelscript plan`: Validates syntax, builds the resource DAG, calculates estimated daily burn rates, and runs Monte Carlo simulation risk checks.
    * `funnelscript apply`: Dispatches validated mutations to external platform providers with cryptographic idempotency.
* **Rationale:** Allows identical FunnelScript source code to run hermetically in simulation (`SimulatedProvider`) or manage multi-million dollar live production campaigns (`LiveProvider`).
* **Consequences:** Provider plugins can be developed independently by the community without altering compiler internals.

---

### DEC-018: Static Financial Invariants & Budget Gas Ceilings
* **Status:** Accepted
* **Context:** In automated execution, algorithmic optimization loops or logic flaws can continuously trigger ad spends or bidding wars, causing catastrophic balance depletion.
* **Decision:**
  * Require static upper bounds on capital draw ($C_{\text{max}}$) for all recurring actions, loops, and dynamic triggers.
  * The compiler AST linter rejects any strategy containing unconstrained spending expressions or unbounded retry loops.
  * The runtime driver maintains an immutable daily "budget gas" ceiling ($C_{\text{daily\_cap}}$); when consumed, execution halts unconditionally.
* **Rationale:** Protects enterprise treasuries with the mathematical certainty of smart-contract execution environments.
* **Consequences:** Prevents automated ad-account drain catastrophes before deployment.


---

### DEC-019: Domain-Neutral Event Kernel v0 and Inert Effect Intents
* **Status:** Accepted as the first bounded implementation slice of DEC-008, DEC-012, and DEC-013.
* **Research Anchor:** Zeigler's discrete-event system specification; Leijen's separation of algebraic effect interfaces from handlers; Python's documented stable priority-queue pattern. See `spec/event-kernel-v0.md`.
* **Falsifiable Hypotheses:** H-K1 stable chronological event ordering; H-K2 seeded replay for pure deterministic reducers; H-K3 finite-time and progress bounds; H-K4 domain-neutral model state and inert external effect descriptions.
* **Mathematical Invariants:** A processed event's `(time, priority, ordinal)` tuple cannot decrease. Newly scheduled events obey `time(new) >= time(current)`; equal-time scheduling cannot decrease priority. The run terminates or raises at a caller-controlled `max_events` bound.
* **Decision:** Introduce a minimal Python reference event kernel taking an opaque user-defined state and reducer and returning a new state, processed/pending events, and effect-intent values. Keep legacy campaign-specific AST/linter and vectorized runtime intact pending a separate migration decision.
* **Safety Boundary:** Emission of inert effect descriptions is not enforcement of pure Python callbacks, static capability checking, or safe live execution. No provider handler or live API mutation is implemented in this phase.
* **Consequences:** An executable domain-neutral semantic contract and regression checks are available independently of marketing-specific concepts. This does not establish predictive validity or a full DEVS/Koka implementation.

---

### DEC-020: Dual Distribution Model (Zero-Install NPX/Bunx & Isolated Python Tooling)
* **Status:** Accepted
* **Context:** Language adoption hinges upon developer onboarding friction. Marketing technologists and web engineers predominantly operate within JavaScript/Node runtimes, while quantitative researchers and SREs operate in Python environments.
* **Decision:** Distribute FunnelScript through two parallel canonical packaging channels:
  1. **Python Distribution:** `funnelscript-cli` on PyPI installed via `uv tool install funnelscript-cli` or `pipx install funnelscript-cli`, providing hermetic virtual environment isolation on host operating systems.
  2. **JavaScript Distribution:** `@funnelscript/cli` on npm, enabling instantaneous zero-install execution via `npx funnelscript` or `bunx funnelscript`.
* **Rationale:** Removes installation barriers entirely. A growth engineer can validate a campaign file in seconds without managing Python environments, while an ML pipeline can cleanly pin virtual dependencies.
* **Consequences:** Cross-registry packaging pipelines must synchronize version releases between PyPI and npm.

---

### DEC-021: IDE Ecosystem Integration via Language Server Protocol (LSP)
* **Status:** Accepted
* **Context:** Developers should not have to manually run terminal commands to discover logic bugs, unreachable campaign nodes, or audience mass balance leaks. Building a bespoke standalone IDE introduces high maintenance and adoption resistance.
* **Decision:**
  * Implement an open Language Server Protocol (LSP) background daemon in Python (`funnelscript-lsp`) communicating via JSON-RPC.
  * Package an official client extension for VS Code and Cursor (`.vsix`).
  * As the developer writes code, the LSP executes the incremental parser and `FunnelLinter`, rendering real-time inline diagnostics (red squiggly lines for mass leaks, yellow squigglies for liquidity warnings, code completions, and hover documentation).
* **Rationale:** Meets developers where they already work. Catches marketing logic errors before files are saved or simulations are executed.
* **Consequences:** Strategy authoring achieves enterprise-grade IDE ergonomics identical to Rust Analyzer or Terraform HCL language tools.


---

### DEC-022: Contextual World Declarations and Strict Primitive State Typing
* **Status:** Accepted as an additive compiler milestone implementing the already established DEC-008/010 language-core separation.
* **Research Anchor:** Cardelli and Wegner (1985) on subtyping; Pierce (2002) on type judgments; Pydantic v2 discriminated AST unions. See `spec/world-declarations-v0.md`.
* **Falsifiable Hypotheses:** H-W1 neutral parsing; H-W2 exact primitive type/uniqueness checking; H-W3 agent-to-entity AST subtyping; H-W4 backward compatibility and blocked unsupported world simulation.
* **Mathematical Invariants:** Distinct declaration names per world; distinct state names per declaration; `literal_type(value) = declared_type`; `AgentDefinition <: EntityDefinition`.
* **Decision:** Support a top-level `world Name { entity ... agent ... }` source form with explicit `state name: type = literal;` fields. Treat the four new declaration words as contextual keywords, retaining their legacy identifier status. Use strict `int`, `float`, `bool`, `string` literal typing without coercion in v0.
* **Compatibility Boundary:** Keep legacy `strategy` AST and marketing simulator unchanged. A world can be statically checked, but simulation is explicitly unsupported until world transitions and runtime construction exist.
* **Consequences:** A real, testable syntax-to-AST and type-checking route exists without inventing prebuilt market Worlds. Declaring an agent without behavior is not evidence of autonomy, and static typing is not evidence of predictive accuracy.

---

### DEC-023: Formal 4-Pillar Documentation Architecture (Docs as Code)
* **Status:** Accepted
* **Context:** A programming language cannot scale or establish developer adoption without authoritative, structured documentation bridging mathematical modeling and practical growth engineering.
* **Decision:** Standardize the FunnelScript documentation ecosystem (`docs.funnelscript.org`) into four canonical knowledge pillars:
  1. **The Getting Started Guide:** Net-new onboarding, CLI installation (`uv tool`, `pipx`, `npx`), IDE setup, and initial campaign compilation.
  2. **The Language Reference:** Strict syntactic and semantic specifications of all language blocks, types, and temporal keywords.
  3. **The Bayesian & Simulation Guide:** Mathematical documentation of PyMC-Marketing posterior calibration, adstock decay ($\lambda$), Hill half-saturation ($K$), and Monte Carlo risk interpretation.
  4. **The Marketing Anti-Patterns Handbook:** Compiler diagnostic manual displaying side-by-side "Bad Code vs. Good Code" comparisons for attribution cycles, audience mass leaks, and liquidity cliffs.
* **Rationale:** Structures knowledge by distinct user intent and expertise levels while integrating automated docstring generation via modern SSG platforms (Mintlify / Fumadocs / MkDocs Material).
* **Consequences:** Documentation is maintained as versioned markdown files directly within the repository under continuous CI verification.

---

### DEC-024: The Modular Library, Framework, and Package Manager Ecosystem (fpm)
* **Status:** Accepted
* **Context:** Requiring developers to author recurring marketing flows (e.g. SaaS trial-to-paid, abandoned cart recovery, multi-channel attribution) from scratch impairs adoption and development velocity.
* **Decision:** Establish a multi-tiered package and code-sharing architecture for FunnelScript:
  1. **Libraries (`libs`):** Modular, plug-and-play components (`fs/channels/meta`, `fs/audiences/saas`) providing pre-modeled kinetics and calibrated psychographic vectors.
  2. **Frameworks (`frameworks`):** Holistic business-model templates (`GrowthEngine`, `OmniChannel`) enforcing end-to-end structural invariants via Inversion of Control.
  3. **Package Manager (`fpm`):** The FunnelScript Package Manager managing dependency resolution, semantic versioning, and distribution of verified open-source and commercial strategy libraries.
  4. **Built-in Industry Benchmarks:** Standardized baseline parameter libraries (`fs/benchmarks/ecommerce/fashion`) enabling Day-1 simulation for organizations lacking proprietary PyMC historical data.
* **Rationale:** Transforms FunnelScript from a syntax compiler into a global, extensible open-source marketing ecosystem with reusable, composable strategy primitives.
* **Consequences:** The compiler must support module import resolution (`import "path" as Alias`), dependency lockfiles (`funnelscript.lock`), and decentralized registry publishing.

---

### DEC-025: Specification-First Open-Source Adoption & Shim Strategy
* **Status:** Accepted
* **Context:** Building an end-to-end multi-tier agent-based compiler and simulation runtime is a massive, multi-year engineering undertaking. Postponing open-source release until full execution runtimes, distributed agent grids, and live provider integrations are finalized stalls adoption and isolates the core team from community feedback.
* **Decision:** Adopt a two-stage "Specification-First" and "Linter Shim" wedge strategy:
  1. Standardize and release the formal **Language Specification** (EBNF grammar, AST schemas, operational semantics) and foundational research papers publicly first.
  2. Ship the lightweight static analysis engine / linter (`funnelscript check`) as a zero-dependency CLI.
  3. The linter delivers immediate, risk-mitigation value on Day 1 by catching structural marketing flaws (audience mass leaks, attribution cycles, unbounded loops) without requiring any simulation runtime.
  4. Provide clear compilation and runtime extension hooks for community contributors, compiler engineers, and simulation researchers to implement runtime backends (Python, Rust, WASM, Julia).
* **Rationale:** Establishes credibility, academic rigor, and immediate practical utility with minimal surface area, converting early adopters from passive observers into active co-creators.
* **Consequences:** The formal language specification and static verification contracts become the foundational source of truth; runtime implementations can evolve in parallel without fracturing the language standard.

---

### DEC-026: Community Contribution Architecture (CONTRIBUTING.md & Issue Standard)
* **Status:** Accepted
* **Context:** An open-source movement requires an accessible, low-friction contribution pipeline that clearly segregates compiler internals, standard libraries, documentation, and external provider adapters.
* **Decision:**
  1. Author a comprehensive `CONTRIBUTING.md` defining development environment setup (`uv`, `bun`), testing commands (`uv run pytest`, `bun test`), code style invariants (100% English, type annotations, zero unverified mocks), and architectural boundaries.
  2. Establish an explicit issue taxonomy with labeled entry points: `good-first-issue` (standard library channels, CLI enhancements), `compiler` (lexer, parser, AST transforms), `runtime` (simulation performance, discrete-event scheduling), and `rfc` (grammar proposals, language extensions).
  3. Mandate RFC (Request for Comments) process for any modification to language grammar, type system, or core invariants.
* **Rationale:** Reduces contributor cognitive load, provides psychological safety, and enforces production-grade engineering standards across all community contributions.
* **Consequences:** Enables scalable community growth while preserving the mathematical and architectural integrity of the core kernel.


---

### DEC-027: Contextual World Rules and Snapshot-Atomic Transitions

* **Status:** Accepted (experimental v0 reference interpreter)
* **Context:** DEC-019 introduced the domain-neutral event kernel and DEC-022 introduced typed World declarations, but language-authored Worlds were static declarations without operational semantics. Marketers and library authors need a precise, testable state-transition substrate before stochastic or external effect models are added.
* **Decision:**
  1. Extend World declarations with contextual `rule NAME on event NAME { transition FIELD = EXPR; }` blocks and typed expression/transition AST nodes.
  2. Define exact primitive types and restricted expressions (literal, same-owner field reference, numeric reference +/- matching numeric literal); forbid implicit coercion.
  3. Evaluate all assignment right-hand sides against the same pre-event state, apply a copy-on-write update, and reject ambiguous duplicate handlers/targets.
  4. Address input events as `Owner.Event`; execute through the existing `EventMachine` with explicit input timestamps and seeded deterministic replay.
  5. Expose a pure `run-world` CLI and reserve source-level event emission, stochastic decisions, economic models, Live/Shadow effect handlers, and external calibration for separately verified extensions.
* **Research and falsification:** `spec/rule-transitions-v0.md` states H-R1 to H-R4 and mathematical invariants; `evals/world-rules-v0.md` ties tests to counterexamples.
* **Rationale:** Source-level rules become executable without embedding audience/campaign assumptions or creating a second scheduler. Snapshot atomicity makes transition order semantics unambiguous.
* **Consequences:** The core remains domain neutral. Runtime tests establish interpreter correctness only, not simulation fidelity or predictive market accuracy.


---

### DEC-028: Source-Scheduled Local Events Through the Existing Event Calendar

* **Status:** Accepted (experimental v0 contract)
* **Context:** DEC-027 made World rule transitions executable, but source code could not cause subsequent reactions. The event kernel (DEC-019) already schedules reducer-emitted events with deterministic ties and explicit event-count limits.
* **Decision:**
  1. Introduce a contextual World-rule statement: `emit EventName after Delay;`, where `Delay` is a finite nonnegative integer or floating-point literal in abstract World time units.
  2. Require a statically defined matching handler on the same entity/agent. Permit forward references and recursive local events, but reject unknown handlers and invalid delays before execution.
  3. Lower emitted events to `Transition.events` on the existing `EventMachine`; do not add a second scheduler, busy-loop, effect provider, or hidden automatic startup event.
  4. Preserve pre-event snapshot assignments, source order among same-time emissions, and the parent event priority (including zero-delay cases). The event processing cap halts recursive zero-delay cycles; finite horizons leave scheduled events pending.
  5. Defer cross-owner emissions, payloads, conditional triggers, probability distributions, cancellation, persistent delivery, and all Live/Shadow actions to separate typed and capability-gated contracts.
* **Research and falsification:** `spec/event-emission-v0.md` specifies H-E1 through H-E4 and temporal invariants; `evals/event-emission-v0.md` provides RED/GREEN and regression evidence.
* **Rationale:** Causal sequences become expressible in the language using the same discrete-event semantics already tested, while compiler and runtime remain business-domain neutral.
* **Consequences:** Worlds can now schedule local events after an externally supplied trigger. They remain neither autonomous digital twins nor validated predictive market models.


---

### DEC-029: Type-Checked Pre-Event Guards for World Rules

* **Status:** Accepted (experimental deterministic World language subset)
* **Context:** DEC-027 defines snapshot-atomic assignments and DEC-028 permits local source emissions. Without declarative conditions, recursive event chains can only stop at event caps or external input boundaries.
* **Decision:**
  1. Support an optional `when (field OP literal)` immediately after a World rule's `on event EventName` clause. Compile it into a typed guard AST node, not a runtime string expression.
  2. Resolve `field` exclusively on the owning entity or agent and require exact primitive type equality with the literal. Support `==` and `!=` on all primitive types; allow `<`, `<=`, `>` and `>=` only for numeric fields.
  3. Evaluate the predicate once against the pre-event snapshot before all rule statements. A false guard consumes the incoming event but yields the original state with no new events and no external effects.
  4. Keep expressions deliberately restricted: no boolean conjunctions, arbitrary function calls, probabilistic draws, cross-owner reads or side effects. These need separately specified semantics and tests.
* **Research and falsification:** `spec/world-guards-v0.md` defines H-G1 through H-G4 and safety invariants; `evals/world-guards-v0.md` maps 20 focused tests and the regression suite to observable counterexamples.
* **Rationale:** Conditional decision mechanics become expressible while compiler and runtime retain a small domain-neutral, predictable semantic surface.
* **Limit:** Passing a guard test does not validate causal attribution, synthetic agent psychology or calibrated marketing forecasts.


---

### DEC-030: Exact-Typed Local Event Records at Both Calendar Boundaries

* **Status:** Accepted (experimental World-language subset)
* **Context:** DEC-019's domain-neutral Event object already holds an opaque model-owned payload, while DEC-027 to DEC-029 source rules lacked static knowledge of event data. Mutable or unstructured payloads could reach source handlers with no type contract.
* **Decision:**
  1. Add contextual source `event Name(field: PrimitiveType, ...);` declarations per entity/agent. Validate unique event and field names and restrict to the existing exact `int`, `float`, `bool`, `string` types.
  2. Allow `payload.field` in current handler transition expressions, and optional named arguments in same-owner `emit Name(field = Expr) after Delay;`. Resolve event fields and argument types statically, with no implicit numeric promotion.
  3. Preserve legacy no-payload handlers and source emission statements. Undeclared events have an implicit empty record; structured input to those handlers must fail instead of bypassing type checks.
  4. Validate source interpreter message shape, string keys, exact primitives, and finite floats before any handler runs **and** before generated messages enter the existing event calendar. Guards cannot bypass validation. Keep the general Python EventMachine opaque and independent of World schemas.
  5. Extend the existing repeatable `run-world --event` input to accept a JSON event record while preserving `OWNER.EVENT@TIME` compatibility and source-specified order. No new evaluator, network effects, or scheduler is introduced.
* **Research and falsification:** `spec/typed-event-payloads-v0.md` defines H-P1 to H-P4 and exact-record invariants. `evals/typed-event-payloads-v0.md` records RED/GREEN evidence, 37 focused tests, 158 total passing Python tests, CLI smoke checks and package build.
* **Rationale:** Static message contracts prevent accidental cross-field, wrong-type and nonfinite data propagation while letting communities define arbitrary domain event vocabularies.
* **Limits:** No composite records, polymorphism, stochastic decision semantics, cross-owner delivery, persistent queues, empirical market fidelity or Live capability authorization is implied.

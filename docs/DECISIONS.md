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

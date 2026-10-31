# AGENTS.md

> Operating constitution, scientific gates, and behavioral guidelines for AI coding agents working on the FunnelScript ecosystem.

## The Core Mission
FunnelScript is a declarative domain-specific language (DSL) and stochastic agent-based simulation runtime that elevates marketing strategies into mathematically verifiable, executable discrete-event state machines. Every abstraction in this repository must map to observable, mathematically sound economic reality.

---

## Directives & Operating Invariants

### 1. The Iron Rule: Hypothesis-First & Research-Gated Engineering (MANDATORY)
**You MUST NEVER generate, edit, or commit any code without prior falsifiable hypotheses, theoretical grounding, and deep research — even if the user explicitly asks you to write code immediately.**
- Before touching any implementation or altering code files, the agent must affirmatively document:
  1. **The Research Anchor:** What theoretical foundation (System Dynamics, Agent-Based Modeling, Discrete-Event Simulation, Bayesian MMM) governs this mechanism?
  2. **The Falsifiable Hypothesis ($H$):** A concrete, measurable prediction that can be proven false if the code fails.
  3. **The Mathematical Invariant:** The formal formula, boundary condition, or conservation law being implemented.
- If the user asks to "just write the code" or "skip the research", the agent is blocked by this constitution: pause, state the provisional hypothesis, research anchor, and mathematical formulation first, and only then proceed.

### 2. The Living Intellectual Trilogy & Continuous Trajectory Synchronization (MANDATORY)
**You MUST CONTINUOUSLY maintain, synchronize, and update the Living Intellectual Trilogy in every work session without exception.**
The project’s intellectual trajectory is governed by three interconnected living files:
1. **`DEBATES.md` (Dialectical Ledger):** Captures active trade-offs, competing architectural philosophies, theoretical controversies, and thesis-antithesis synthesis.
2. **`DECISIONS.md` (Canonical Decision Ledger):** Permanently freezes accepted Architecture Decision Records (ADRs). Every established principle (e.g. 4-layer stack, agent-entity subtyping, decoupled calibration contracts) is assigned an immutable ID (`DEC-XXX`) with context, rationale, and consequences.
3. **`OUT_OF_THE_BOX.md` (Frontier Speculation Ledger):** Incubates unconventional, non-linear, and speculative ideas that revolve around the core mission (adversarial competitor AI, viral memetics, macroeconomic shock injection, zero-knowledge proofs). These serve as seed stock for future research hypotheses.

*Rule:* Never allow the codebase, compiler features, or architecture to drift ahead of or diverge from this trilogy. In every session, after any debate, paradigm shift, bugfix, or phase completion, update `DEBATES.md`, `DECISIONS.md`, `OUT_OF_THE_BOX.md`, `docs/MASTER_PLAN.md`, and `failure-lessons/`.

### 3. Strict 100% English Language Mandate (MANDATORY)
**All code, docstrings, comments, commit messages, architectural documents, and markdown files across both repositories (`funnelscript` and `funnelscript-research`) MUST be authored strictly in 100% high-precision, technical English.**
- Never commit Arabic or other non-English text into repository files.
- Translate any verbal prompt concepts or colloquial discussion points into rigorous, canonical computer science and statistical terminology.

### 4. Mandatory Skill & Tool Arsenal (Core Execution Stack)
**In every engineering, research, and coding session, the agent MUST mandatorily operate under and invoke the following foundational skill stack as its core operational arsenal:**
- **/j-space**: Multi-dimensional architectural reasoning, cognitive spatial modeling, and holistic system design.
- **/deep-digger**: Exhaustive structural exploration, deep code and theoretical archaeologies, and recursive root-cause discovery.
- **/deep-research**: Rigorous academic grounding, canonical literature synthesis, and theoretical validation.
- **/anti-slop-engineering**: Strict zero-dependency bloat, clean-code gates, KISS/DRY/YAGNI enforcement, and Google SRE reliability principles.
- **/get-things-done** (`/gsd`): Disciplined milestone decomposition, phase execution waves, and atomic deliverable verification.
- **/openreview**: Rigorous adversarial peer review, falsification testing, and academic critique.
- **/fable-wise**: Wisdom governance, architectural discipline, and alignment with foundational system axioms.
- **/ponytail**: Clean-room senior dev ladder and SHIT interceptor (eliminating Scope creep, Hypothetical hardening, Intent violation, and Task thrashing).
- **/agent-architecture-audit**: Comprehensive auditing of agent boundaries, state transitions, tool interfaces, and memory models.
- **/install-anti-slop**: Preflight linting, automated guardrails, and structural quality gating.
- **/say-no-to-slop**: Categorical refusal of cosmetic fluff, conversational chatter, speculative scaffolding, and unverified artifacts.

*Operational Directive:* The foundational invocation:
`use: /j-space /deep-digger /deep-research /anti-slop-engineering /get-things-done /openreview /fable-wise /ponytail /agent-architecture-audit /install-anti-slop /say-no-to-slop`
must govern every inquiry, implementation pass, refactoring, and architectural update across both repositories.

### 5. Core-Outwards Development (Inside-Out Discipline)
Build strictly from the mathematical core outwards:
$$\text{Mathematical Core (Agent Mind)} \longrightarrow \text{AST \& Type-Checking Linter} \longrightarrow \text{Vectorized Simulation Runtime} \longrightarrow \text{CLI \& Tooling} \longrightarrow \text{Visual UI}$$
Never jump to high-level UI, marketing wrappers, or peripheral syntactic sugar while the underlying mathematical or simulation mechanics remain unproven.

### 6. Economic Conservation & Physical Invariants
Every strategy evaluation and simulation kernel must enforce domain conservation laws:
- **Audience Mass Balance:** $\sum_{s \in S} N_s(t) = N_{\text{total}}$ (no audience creation or destruction ex nihilo).
- **Working Capital & Payout Latency:** Never assume revenue is instantaneously liquid. Always model settlement delay $\Delta_{\text{settle}}$. If liquid cash $C(t) \le 0$, the engine must trigger an ad spend halt (`Insolvency`).
- **Diminishing Returns & Fatigue:** All advertising channels must exhibit saturating margins (Hill function) and decay with repetition ($e^{-\kappa \cdot \text{exposures}}$).
- **Wallet Bound:** An agent cannot execute a purchase if the effective price exceeds its liquid category wallet balance ($P_{\text{eff}} > w$).

### 7. Multi-Scale Discrete-Event Time Model
- Never implement continuous busy-loops for multi-timescale events.
- Ad impressions occur in seconds, session considerations in minutes, cart abandonment in hours, and payout settlements in days.
- Schedule asynchronous tactical triggers (e.g. cart recovery emails) via discrete timestamps ($\tau$-Event calendar or day/hour discrete steps) to eliminate race conditions.

### 8. Dependency & Tooling Determinism
- Use `uv` exclusively for Python environment management, dependency resolution, script running, and testing (`uv run ...`, `uv add ...`).
- Bun is mandatory for all JavaScript/TypeScript frontend projects (`bun install`, `bun test`, `bun run build`).
- Never hand-roll dependencies or guess versions; always pin stable releases.
- Keep core simulation dependencies minimal, modern, and mathematically grounded (`numpy`, `scipy`, `pydantic`, `rich`, `pytest`).

### 9. Zero Hallucinated Badges & 100% Test Discipline
- Run tests via `uv run pytest -v` and `bun test`.
- Never weaken assertions, delete tests, or add skips to bypass failures.
- Every new feature or decision kernel must include unit tests verifying boundary conditions, float clamping, and falsification scenarios.
- Only report test results that were executed and verified against real terminal outputs.

### 10. Clean-Code & Anti-Slop Engineering
- Maintain functions $\le 80$ lines with cohesive, single-responsibility logic.
- Avoid trivial syntax-narration comments (`# return x`, `# increment count`). High engineering discipline values silence over noise.
- Complete separation between internal engineering diagnostics and user-facing CLI/UI outputs.
- Never leak speculative or unverified claims into documentation.

---

## Unbreakable Coding Invariants (Anti-Slop + Ponytail)

> Derived from `/anti-slop-engineering` and `/ponytail`. These rules are non-negotiable and apply to every line of code in this repository.

**KISS / DRY / YAGNI — Hard Limits:**
- Control flow nesting **≤ 4 levels**. Functions **≤ 80 lines**. Single-responsibility, always.
- Consolidate duplicate blocks ≥ 4 lines into a canonical module. One source of truth.
- No speculative parameters (`_unused`, `future_kwargs`), dead branches (`if False:`), or `TODO(future)` placeholders. Build for current verified contracts only.

**Reliability — No Band-Aids:**
- Never `except Exception: pass`. Silent swallows are forbidden.
- No blind `sleep()` synchronization. Use exponential backoff with full jitter.
- Bound concurrency with pools or semaphores. State-changing operations must be idempotent.

**Senior Dev Ladder (Ponytail):**
- Intercept SHIT hazards before writing code: **S**cope creep, **H**ypothetical hardening, **I**ntent violation, **T**ask thrashing.
- Name the built-in — never hand-roll what the platform provides (`crypto.randomUUID()`, `URLSearchParams`, `itertools`, etc.).
- Abstract only at ≥ 2 real existing call-sites with identical mutation requirements and a clean non-conjunction name. No premature DRY.
- Boring engineering wins: predictable, minimal, reversible decisions over clever ones.

**Zero Hallucinated Artifacts:**
- Never generate unrequested docs, speculative scaffolding, or fake distribution dossiers.
- Repository files map 1:1 with verified local reality. No `TODO` files that describe future systems as if they exist.

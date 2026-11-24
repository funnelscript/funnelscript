# FunnelScript: Phase 1 Execution & Engineering Rules

**Status:** Active (Mandatory Enforcement)  
**Scope:** Applies to all human contributors and AI coding agents operating across `funnelscript-main` and `funnelscript-research-main`.  
**Primary Objective:** Stop speculative expansion and validate FunnelScript on real-world marketing campaign data within 4 weeks.

---

## 1. Hard Freeze & Anti-Bloat Rules

To eliminate premature complexity and specification ossification, the following freeze is strictly enforced until all Phase 1 exit criteria are met:

* **NO New Specifications:** Do **not** create or expand files in `spec/`, `DEBATES.md`, `DECISIONS.md`, `OUT_OF_THE_BOX.md`, or `MASTER_PLAN.md`.
* **NO Formal Verification Work:** Do **not** modify or add theorems in `formal/` (`Kernel.lean`, `Theorems.lean`) until the core domain semantics survive empirical validation.
* **NO Frontend Feature Expansion:** Do **not** add new UI components, visual nodes, or styling features to `apps/web/`.
* **NO Brand or GTM Distractions:** Do **not** add assets to `assets/brand/` or update growth playbooks (`GROWTH_PLAYBOOK_DBT_TEARDOWN.md`, `OPEN_SOURCE_GROWTH_PLAYBOOK.md`).
* **Test Suite Focus:** Remove non-functional checks (such as `tests/test_brand_identity.py`) from the critical CI path. All test effort must focus exclusively on financial accuracy, simulation determinism, and parameter calibration.

---

## 2. Single Source of Truth (Runtime Unification)

Maintaining dual simulation engines in Python and TypeScript is strictly prohibited.

* **Deprecate TS Runtime:** Mark for deletion and remove all simulation and transpilation logic from `apps/web/src/lib/simulator.ts` and `apps/web/src/lib/transpiler.ts`.
* **Canonical Execution Core:** All parsing, linting, RNG seeding, event execution, and financial ledger accounting **MUST** run exclusively through `src/funnelscript/` (Python core).
* **Web UI Boundary:** `apps/web/` must act solely as a thin visual editor and telemetry viewer communicating with the Python engine via a local API bridge or WebAssembly (Pyodide).
* **Zero Semantic Drift:** No mathematical formula or stochastic rule may exist in TypeScript if it already exists in `src/funnelscript/runtime/`.

---

## 3. Research-to-Code Alignment Gate (Mandatory Decision)

No new research sections or runtime features may be written until the paradigm gap between `funnelscript-research-main` and `funnelscript-main` is permanently resolved by locking in **exactly one** of the following tracks:

* **Track A — Discrete-Event & Audited Financial Provenance (Recommended):**  
  Rewrite `paper/sciml_marketing_hydrodynamics.md` so the theoretical contribution directly describes the discrete event machine (`event_machine.py`), keyed RNG determinism, and double-entry financial provenance (`ledger.py`, `provenance.py`) already built in Python.
* **Track B — SciML Marketing Hydrodynamics:**  
  Implement the continuous partial/ordinary differential equations from `sciml_marketing_hydrodynamics.md` directly inside `src/funnelscript/runtime/engine.py`, and prove convergence between agent-based runs and the continuous conservation law.

**Traceability Rule:** Every mathematical claim or equation in `paper/` **MUST** reference an executable Python module and a passing verification test in `src/funnelscript/`. Unimplemented theoretical claims must be removed from the paper.

---

## 4. Real-World Data Ingestion & Calibration Rules

Synthetic, hand-written scenarios (e.g., `examples/black_friday_2026.fnls`) are no longer accepted as proof of product maturity.

* **Build Ingestion Adapters:** Implement a data ingestion module inside `src/funnelscript/stdlib/marketing/` capable of parsing standard CSV exports from real ad platforms (Meta Ads, Google Ads) and payment/CRM logs.
* **Automated Parameter Inference:** The ingestion pipeline must infer core empirical parameters—such as diminishing returns/saturation, drop-off rates, and conversion latency—directly from historical campaign metrics.
* **Code Generation:** The calibration step must output a valid, human-readable `.fnls` file representing the real campaign's baseline state, ready for scenario stress-testing.

---

## 5. Empirical Backtesting & Benchmark Mandate

FunnelScript must prove measurable superiority over static spreadsheets on real historical data.

* **Temporal Split Protocol:** Acquire at least 30 days of real campaign data. Use the first 50% (Weeks 1–2) strictly for parameter calibration, and hold out the second 50% (Weeks 3–4) for out-of-sample forecasting.
* **Target Metrics:** Evaluate out-of-sample prediction error for:
  1. Customer Acquisition Cost ($\text{CAC}$)
  2. Conversion Volume & Revenue
  3. Cash Runway & Liquidity Stress (`ledger.py`, `stress_liquidity_test.json`)
* **Baseline Comparison:** FunnelScript's forecast error (e.g., $\text{MAPE}$) **MUST** be benchmarked directly against:
  1. Actual ground-truth campaign outcomes.
  2. A standard linear spreadsheet projection.
* **Core Value Demonstration:** Prioritize modeling the non-linear interaction where static spreadsheets fail—specifically, **ad performance degradation under budget scaling combined with cash collection lag**.

---

## 6. Case Study Packaging & Phase 1 Exit Criteria

The Phase 1 freeze may only be lifted when the repository delivers a single, reproducible end-to-end case study documented in `README.md`:

1. **Input:** An anonymized real-world campaign CSV dataset.
2. **Script:** A concise ($\le 20$ lines) `.fnls` scenario script simulating a real executive decision (e.g., doubling daily ad spend).
3. **Output:** Automated financial telemetry showing predicted cash exhaustion dates (`CashRunwayChart`) alongside out-of-sample backtest accuracy metrics.

---

## 7. 4-Week Execution Schedule

| Week | Primary Deliverable | Hard Gate / Verification |
| :--- | :--- | :--- |
| **Week 1** | Freeze specs, delete TS simulator (`simulator.ts`, `transpiler.ts`), wire UI to Python core, and lock Research Track (A or B). | Web UI and CLI produce bit-identical simulation outputs; paper matches `engine.py`. |
| **Week 2** | Build real-data CSV importer & parameter calibration module in `src/funnelscript/stdlib/marketing/`. | Running CLI on a real Meta/Google CSV automatically generates a valid `.fnls` model. |
| **Week 3** | Run 50/50 temporal backtest on real agency campaign data and benchmark against a linear Excel baseline. | Recorded accuracy report comparing FunnelScript vs. Ground Truth vs. Spreadsheet. |
| **Week 4** | Package end-to-end case study in `README.md` and prune CI to financial/simulation integrity tests. | New user can reproduce the full CSV $\to$ `.fnls` $\to$ Cash Runway workflow in under 5 minutes. |

---

## 8. Directives for AI Coding Agents (`AGENTS.md` Addendum)

When assisting with this repository, AI agents **MUST** obey these constraints:

1. **Reject Scope Creep:** If prompted to add speculative DSL syntax, new Lean proofs, or long architectural debate documents during Phase 1, flag the violation against Section 1 and propose a minimal runtime-focused alternative.
2. **Enforce Python-Only Math:** Never write simulation math, RNG logic, or ledger calculations in TypeScript/JavaScript.
3. **Prefer Empirical Over Synthetic:** When writing new tests or examples, prefer data-driven CSV fixtures derived from realistic marketing schemas over arbitrary hardcoded constants.
4. **Keep Changes Minimal & Verifiable:** Every pull request or commit must tie directly to one of the four weekly deliverables in Section 7 and pass `pytest` on core runtime and ledger tests.
# FunnelScript Sub-Task Prompt: Build Flagship Package `ecommerce/d2c_scale`

You are the Senior Marketing Systems Engineer working on the **FunnelScript** repository.
Your sub-task is to design, implement, and verify the first production-grade `fpm` package: **`ecommerce/d2c_scale`**.

This package models a real-world Direct-to-Consumer (D2C) e-commerce operation running paid acquisition across both **Prepaid (Online)** and **Cash-on-Delivery (COD)** channels. Its primary purpose is to expose the exact failure mode spreadsheets miss: a campaign showing positive paper ROAS that still runs out of cash due to daily ad spend velocity, payment/courier settlement lags ($\Delta_{\text{settle}}$), rolling reserves, and Return-to-Origin (RTO) round-trip shipping losses.

---

## 1. Non-Negotiable Constraints

1. **Preserve Existing Documentation:** Do NOT modify, overwrite, or delete `AGENTS.md`, `EXECUTION_RULES.md`, or any roadmap `.md` files.
2. **Grammar & Compiler Fidelity First:** Before writing a single `.fnls` line, inspect:
   - `docs/fpm.md` (package layout, manifest format, import resolution rules)
   - `src/funnelscript/parser.py`, `src/funnelscript/compiler/world_ast.py`, and `src/funnelscript/compiler/linter.py`
   - `src/funnelscript/stdlib/marketing/` (`metrics.py`, `ledger.py`, `provenance.py`, `audit.py`, `commit.py`)
   - `tests/test_world_modules.py` and `tests/test_named_exports_007g.py` (exact supported module import/export syntax)
   - `examples/black_friday_2026.fnls` and `examples/stress_liquidity_test.json`
   - Do NOT invent unsupported `.fnls` syntax. Every `.fnls` file you produce MUST parse, lint, and execute cleanly through the real Python runtime (`src/funnelscript/`). If `fpm` namespace resolution is not yet wired for `import "ecommerce/d2c_scale"`, implement the minimal resolver hook in `src/funnelscript/compiler/` strictly following `docs/fpm.md` without breaking existing relative imports.
3. **Single Source of Truth:** All simulation logic runs strictly in the Python DEVS runtime (`src/funnelscript/runtime/`). Do NOT touch `apps/web/src/lib/simulator.ts`.
4. **Zero Hardcoded Business Constants:** Every rate, cost, delay, and curve parameter (Hill $K, S$, Adstock $\lambda$, COD share, confirmation rate, RTO rate, shipping cost, $\Delta_{\text{settle}}$, reserve holdback) MUST be exposed as typed, bounded parameters with explicit defaults.
5. **Strict Financial & Dimensional Discipline:**
   - All monetary movements must reconcile through the double-entry ledger (`ledger.py`) with zero float drift.
   - Respect dimensional unit consistency (Currency, Count, Rate, Duration, Ratio). Do not mix incompatible units.
   - Use deterministic keyed RNG only for stochastic fulfillment delays, confirmations, and RTO events.

---

## 2. Target Package Architecture

Create the package under the standard `fpm` package directory specified in `docs/fpm.md` (defaulting to `packages/ecommerce/d2c_scale/` if not otherwise defined) with the following modular structure:

1. **Package Manifest (`fpm.toml` or `manifest.json` per `docs/fpm.md`)**
   - Package ID: `ecommerce/d2c_scale`, version `0.1.0`.
   - Declares exported modules, required FunnelScript version, input parameter schema (with types, units, min/max bounds, and defaults), and standard output metrics.

2. **Acquisition Module (`acquisition.fnls`)**
   - Models multi-channel daily paid spend (e.g., Meta, TikTok, Google) with immediate daily cash outflow (or card billing threshold).
   - Applies **Adstock** carryover decay and **Hill** diminishing-returns saturation so scaling daily spend increases marginal CPA non-linearly.
   - Emits typed order-intent events into the fulfillment pipeline.

3. **Fulfillment & Logistics Module (`fulfillment.fnls`)**
   - Splits incoming orders into **Prepaid** vs. **COD** cohorts based on `cod_share_rate`.
   - **COD Path:**
     - Order confirmation step (`cod_confirmation_rate`); unconfirmed orders cancel before shipping (zero COGS/shipping loss, ad spend already sunk).
     - Courier transit delay drawn from a bounded discrete delay distribution (`delivery_delay_days`).
     - Delivery outcome: **Delivered** vs. **RTO (Return-to-Origin)** based on `cod_rto_rate`.
     - RTO orders incur **forward shipping + return shipping + packaging loss**, return inventory after `rto_restock_days`, and generate **zero revenue**.
   - **Prepaid Path:**
     - Immediate authorization, gateway fee deduction (`gateway_fee_rate`), shipping dispatch, and post-delivery refund risk (`prepaid_refund_rate`) within a refund window.

4. **Treasury & Settlement Module (`treasury.fnls`)**
   - Integrates directly with `ledger.py` and `provenance.py` to separate **Accrual Revenue (Booked GMV)** from **Settled Cash Balance**.
   - Models two distinct settlement lags ($\Delta_{\text{settle}}$):
     - **Payment Gateway Settlement:** Payout after `gateway_settle_days` minus `rolling_reserve_rate` held for `reserve_release_days`.
     - **COD Courier Remittance:** Cash collected by courier on delivery day, remitted to merchant bank account after `cod_remittance_days` minus `cod_fee_rate`.
   - Tracks daily **Cash Balance**, **Accounts Receivable (In-Transit Cash)**, **Minimum Cash Trough**, **Cash Runway Alert** (triggered when settled cash drops below `min_safety_cash`), **Paper ROAS**, **Net MER**, and **Contribution Margin after RTO**.

5. **Package Entry Point (`index.fnls`)**
   - Composes `acquisition.fnls`, `fulfillment.fnls`, and `treasury.fnls` cleanly and exposes the public world/module exports.

6. **Package Documentation (`README.md`)**
   - Concise parameter reference table (name, unit, default, valid range, business meaning).
   - Clear accounting flow showing where cash leaves vs. where cash lands.
   - Minimal 15-line usage snippet.

---

## 3. Concrete Stress-Test Example

Create `examples/d2c_scale_stress.fnls` (target: 15–30 lines):
- Imports `ecommerce/d2c_scale`.
- Configures a realistic MENA/global D2C brand (e.g., 65% COD share, 18% COD RTO rate, 7-day courier remittance lag, 3-day gateway lag, 35% COGS) attempting to **2x daily ad spend** ahead of a 30-day seasonal push starting with a constrained working-capital buffer.
- Must demonstrate clearly in the simulation telemetry:
  - Accrual ROAS remains positive (looks profitable on an ad-platform dashboard).
  - Settled Cash Balance breaches the safety floor mid-month due to the compounding effect of Hill CPA inflation + RTO shipping drag + COD remittance lag.

---

## 4. Verification & Test Suite

Create `tests/test_pkg_ecommerce_d2c_scale.py` covering:
1. **Parse & Lint Cleanliness:** All `.fnls` files inside `ecommerce/d2c_scale` and `examples/d2c_scale_stress.fnls` compile and pass `linter.py` with zero errors.
2. **Deterministic Replay:** Running `examples/d2c_scale_stress.fnls` twice with the same seed produces byte-for-byte identical telemetry and ledger hashes.
3. **Double-Entry Conservation:** Total debits equal total credits at every tick; `Starting Cash + Settled Inflows - Paid Outflows == Ending Settled Cash` with zero rounding drift, even under high RTO and refund rates.
4. **Monotonic Business Invariants (Sensitivity Checks):**
   - Increasing `cod_remittance_days` strictly lowers or equals the minimum cash trough without changing total accrual GMV.
   - Increasing `cod_rto_rate` strictly decreases net contribution margin and settled cash.
   - Setting `cod_share_rate = 0.0` eliminates courier remittance receivables completely.
5. **Parameter Bounds Validation:** Invalid parameters (e.g., `cod_rto_rate = 1.5`, negative lag days, negative COGS) are rejected cleanly with clear diagnostic messages.

---

## 5. Execution Protocol & Exit Gate

1. **Inspect First:** Read the files listed in Section 1.2 and output a short 5-bullet plan confirming exact `.fnls` syntax and `fpm` resolution mechanics before writing code.
2. **Implement:** Build the package, minimal `fpm` resolver hook (if needed), stress example, and test suite.
3. **Verify:** Run:
   - `pytest tests/test_pkg_ecommerce_d2c_scale.py`
   - Full regression suite (`pytest`)
   - Linter (`ruff check .`)
   - Execute `examples/d2c_scale_stress.fnls` via `funnelscript` CLI and print the key summary metrics (Paper ROAS, Realized Net Margin, Starting Cash, Min Cash Trough Day & Value, Ending Settled Cash, Ledger Audit Status).
4. **Report:** Output a concise completion summary listing created/modified files, test counts, and the CLI stress-test output. Stop and wait for review.
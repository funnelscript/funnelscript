# Product Marketing Context: FunnelScript

- **Document Version:** 1.0.0
- **Last Updated:** 2026-10-31
- **Repository:** [funnelscript](https://github.com/funnelscript/funnelscript)
- **Status:** Positioning and future GTM hypotheses; WASM Studio, cloud grids, commercial connectors and `fpm` distribution are not shipped capabilities in the experimental `v0.2.0a1` language preview.

---

## 1. Product Overview

- **One-Line Description:** The declarative domain-specific language (DSL) and discrete-event simulation runtime that elevates marketing strategies into mathematically verifiable, executable state machines.
- **Category:** Marketing-as-Code (MaC) / Marketing Systems Engineering (MSE) / Declarative Economic Simulation DSL.
- **Product Type:** Open-Source Developer Tool & Language Runtime (Python 3.12+, `uv`-managed CLI + `.fnl` Language Specification + WebAssembly/WASM Studio).
- **Core Value Proposition:** Eliminate uninspected ad capital loss by replacing fragile spreadsheets and ad-hoc Jupyter notebooks with static verification (`funnelscript check`) and stochastic Monte Carlo stress-testing (`funnelscript simulate`) before deploying capital.
- **Business & Distribution Model:** Open-source core engine (MIT License) with modular package manager (`fpm`), commercial enterprise connectors, and cloud simulation grids.

---

## 2. Target Audience & Ideal Customer Profile (ICP)

### Primary Persona: The Marketing Systems Engineer (MSE)
- **Job Titles:** Marketing Systems Engineer, Growth Data Scientist, Quantitative Media Director, Marketing Infrastructure Lead, Head of Marketing Operations.
- **Organization Type:** High-scale B2C/DTC e-commerce, high-growth B2B SaaS, performance agencies managing >$500k/month in ad spend, and venture capital growth teams.
- **Primary Pain Points:**
  1. *Spreadsheet Fragility:* High-stakes ad budgets ($100k–$10M) planned on untyped Google Sheets with broken formulas and zero version control.
  2. *Cash Ruin Blindspot:* Media buyers scale budgets without modeling merchant payout settlement delays ($\Delta_{\text{settle}}$), leading to sudden cash insolvency.
  3. *Attribution & Saturation Hallucinations:* Platform ad dashboards take credit for the same conversion multiple times; diminishing returns and ad fatigue ($\lambda$) are rarely modeled mathematically.
- **Jobs to Be Done (JTBD):**
  1. "Verify that our quarterly scaling plan will not exhaust our cash balance before merchant payouts settle."
  2. "Audit our campaign topology in CI/CD to ensure no audience mass leaks or infinite ad-spend loops exist."
  3. "Provide reproducible Monte Carlo scenario evidence to the CFO before budget authorization."

---

## 3. Positioning & Category Design

| Dimension | Legacy / Status Quo | FunnelScript (Marketing-as-Code) |
|---|---|---|
| **Paradigm** | Ad-hoc Spreadsheets & Black-box Dashboards | Declarative `.fnl` Strategy Files under Version Control (Git) |
| **Verification** | Post-hoc realization of loss (burning real money) | Pre-flight Static Type & Contract Verification (`funnelscript check`) |
| **Modeling** | Linear point-estimates ($5\times$ ROAS assumption) | Vectorized Stochastic Monte Carlo Simulation ($M=10,000$ trials) |
| **Safety** | Hope-based media buying | Hard Invariants: Audience Mass Conservation & Bounded Budget Gas |
| **Reusability** | Copy-pasting rows in Excel | Semantic module imports (`std:marketing/lead_response.fnl`, `fpm`) |

### The Elevator Pitch
> *"Engineers wouldn't deploy infrastructure without Terraform, and financial traders wouldn't execute algorithms without backtesting. Why are marketing teams still risking millions of dollars on fragile spreadsheets? FunnelScript is Marketing-as-Code: a declarative language and simulation engine that tests marketing assumptions in code before spending a single dollar in ad auctions."*

---

## 4. Scientific & Theoretical Grounding

1. **System Dynamics & Conservation Laws:** Audience conservation ($\sum P(s) = 1.0$), non-linear Hill saturation functions ($K$), and adstock exponential decay ($\lambda$).
2. **Bayesian Econometrics:** Media Mix Modeling (MMM) prior calibration and posterior parameterization.
3. **Discrete-Event Simulation (DES):** Multi-timescale state machines handling ad clicks (seconds), consideration (hours), and cash settlement (days) without race conditions.
4. **Static AST Analysis:** Compiles high-level marketing rules into intermediate representations, detecting circular attribution dependencies and unbounded recursion.

---

## 5. Brand Voice & Communication Rules

- **Voice Attributes:** Rigorous, mathematically precise, anti-slop, developer-first, sovereign.
- **Tone:** Academic computer science meets quantitative finance discipline.
- **Banned Language & AI Tells:**
  - ❌ *"Revolutionize your marketing with AI magic"*
  - ❌ *"Skyrocket your ROAS with push-button ease"*
  - ❌ *"It's not just a tool, it's a revolution"*
  - ❌ False marketing truisms or empty buzzwords ("game-changer", "effortless", "growth-hack").
- **Mandatory Canonical Phrases:**
  - ✅ *"Marketing-as-Code (MaC)"*
  - ✅ *"Marketing Systems Engineering (MSE)"*
  - ✅ *"Hypothesis-first simulation"*
  - ✅ *"Stochastic pre-flight verification"*
  - ✅ *"Cash insolvency risk $P(\text{Insolvency})$"*

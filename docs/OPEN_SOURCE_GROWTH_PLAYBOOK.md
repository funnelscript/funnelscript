# FunnelScript Open-Source Movement Playbook

> Strategic framework for scaling FunnelScript from a core research specification into a global open-source software movement.

---

## 1. Executive Thesis

Programming languages do not achieve widespread adoption through syntactic elegance alone. They succeed when they:
1. Provide a rigorous, uncompromised core specification.
2. Create clear economic and career incentives for external contributors.
3. Solve an immediate, high-stakes operational problem for a specific community.
4. Lower the barrier to initial contribution while preserving production engineering rigor.

FunnelScript adopts the open-source distribution playbooks pioneered by Terraform (declarative infrastructure standards), Julia (high-performance scientific computing), and Anti-Slop Engineering (spec-driven, zero-dependency gatekeeping).

---

## 2. The Four Strategic Pillars

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       The 4 Strategic Growth Pillars                        │
└─────────────────────────────────────────────────────────────────────────────┘
       │                          │                     │               │
       ▼                          ▼                     ▼               ▼
┌──────────────┐          ┌──────────────┐      ┌──────────────┐ ┌──────────────┐
│  Pillar 1:   │          │  Pillar 2:   │      │  Pillar 3:   │ │  Pillar 4:   │
│  Open-Source │          │  Commercial  │      │ Target MSE   │ │  The Shim    │
│  Foundation  │          │  Incentives  │      │ & Growth DS  │ │  Strategy    │
│  & Good First│          │  via `fpm`   │      │ Persona      │ │  (Spec-First)│
└──────────────┘          └──────────────┘      └──────────────┘ └──────────────┘
```

### Pillar 1: The Open-Source Movement Playbook
A project attracts top-tier open-source engineers when its engineering hygiene and contribution pathways are transparent and accessible:
* **Permissive Licensing:** Released under the MIT License to allow unrestricted adoption across enterprise marketing stacks and proprietary agency environments.
* **Architecture-First `CONTRIBUTING.md`:** Detailed contributor documentation mapping compiler subsystems (Lexer, Parser, Linter, Runtime, Web Studio) so developers can locate relevant code within 60 seconds.
* **Curated `good-first-issue` Taxonomy:** Decomposing real compiler requirements into bite-sized tasks:
  * Adding syntax highlighting definitions (TextMate grammar).
  * Authoring pre-calibrated touchpoint profiles (`Meta_Reels`, `Google_Search_PMax`).
  * Expanding unit test matrices for AST edge cases.
  * Adding CLI formatting and color output flags.

### Pillar 2: Mutual Commercial Incentives via `fpm`
Open-source ecosystems compound when third parties benefit financially from building on the platform:
* **Agency Distribution:** Performance marketing agencies package proprietary strategies into versioned `fpm` libraries (`@agency/b2b-pipeline-engine`), using public packages to demonstrate mathematical rigor and win enterprise retainers.
* **Provider Ecosystem:** Ad platforms, CRM vendors, and martech companies (TikTok, Klaviyo, HubSpot) author official connectors to ensure marketing budgets specified in `.fnl` flow directly into their APIs.
* **Connector Bounty Program:** Strategic developer grants and bounties awarded to community members who author certified platform providers that pass the FunnelScript provider conformance test suite.

### Pillar 3: Targeting the "Marketing Systems Engineer" Persona
Traditional marketing teams use intuition and fragile spreadsheets. Modern quantitative growth teams employ "Marketing Systems Engineers" and "Growth Data Scientists" who operate between business goals and ad-hoc Python scripts.
* **The Core Friction:** These practitioners are forced to write bespoke Monte Carlo loops and fragile econometric regressions from scratch for every campaign decision.
* **The FunnelScript Solution:** FunnelScript provides a declarative DSL that translates high-level marketing topology directly into formal mathematical constraints and stochastic simulations.
* **Organic Advocacy:** Because FunnelScript solves their daily operational friction, these practitioners become the primary advocates, authoring technical analyses on Medium, Substack, and Dev.to, and submitting PRs to expand the standard library.

### Pillar 4: The "Shim Strategy" (Specification-First & Linter Wedge)
Waiting to open-source FunnelScript until a massive, distributed multi-tier simulation grid is complete invites irrelevance. The project adopts the "Shim Strategy":
* **Step 1: Release Formal Specification & Linter First:** Publish the complete EBNF grammar, AST JSON schemas, academic whitepaper, and the lightweight zero-dependency linter (`funnelscript check`).
* **Step 2: Immediate Production Value:** Marketers can run `funnelscript check` in CI/CD on Day 1 to detect catastrophic bugs (attribution loops, audience mass leaks, cash starvation cliffs) in milliseconds before spending any ad capital.
* **Step 3: Attracting Compiler & Simulation Talent:** Demonstrating immediate practical utility and mathematical rigor attracts compiler engineers, Rustaceans, and simulation researchers who are inspired to build high-performance execution backends (Python SIMD, Julia, WebAssembly).

---

## 3. The Contributor Journey & Progression Funnel

Contributors advance through four transparent tiers:

| Tier | Role | Scope of Activity | Verification Gate |
| :---: | :--- | :--- | :--- |
| **L1** | **Ecosystem Contributor** | Documentation, typo fixes, `good-first-issue` tickets, community channels | Automated CI pass, 1 peer review |
| **L2** | **Channel & Provider Author** | Authors new touchpoint definitions, industry benchmarks, platform connectors | Provider test suite, calibration check |
| **L3** | **Compiler & Runtime Engineer** | Optimizes AST passes, vectorized simulation kernels, discrete-event scheduling | Falsification tests, benchmark regression check |
| **L4** | **Steering Committee** | Language grammar RFCs, invariant governance, release management | Consensus RFC approval, multi-sig commit |

---

## 4. Governance & The RFC Process

Modifications to the language syntax, type system, or mathematical invariants must follow the Request for Comments (RFC) process:

1. **RFC Proposal:** Author a structured markdown proposal in `docs/rfcs/` detailing motivation, grammar modifications, type judgments, and backwards compatibility.
2. **Community Review:** A 14-day public review period during which the community critiques edge cases and performance impacts.
3. **Core Invariant Gate:** An RFC is rejected if it violates:
   * **Audience Mass Conservation:** $\sum P(\text{state}) = 1.0$.
   * **Bounded Budget Gas:** Mandatory static upper bound $C_{\text{max}}$ on recurring spend loops.
   * **Deterministic Replay:** Identical random seed must produce identical simulation trajectories.

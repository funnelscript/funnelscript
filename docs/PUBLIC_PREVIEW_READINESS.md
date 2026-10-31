# FunnelScript Public Research Preview Readiness

Assessment date: 2026-10-31. This is a subjective engineering decision aid, **not** a statistically estimated probability of success or a forecast of real-market validity. Milestone assessed: a credible **public announcement as an experimental programming language**, not stable 1.0, production Live Execution, or calibrated market simulation.

## Observed technical evidence

- A distinct `world/entity/agent/state` grammar and exact primitive type checker.
- Language-defined rules, pre-event snapshot transitions, typed guards, typed local event records, event emission, finite event scheduling, and two seeded stochastic transition operators.
- `run-world` CLI accepts source files, repeatable external events, typed JSON records, seeds and processing limits; `import` compiles local and packaged one-owner World modules. The first Marketing Standard Library source ships at `std:marketing/lead_response.fnl`.
- TDD: 25 stochastic and 23 module-import regression tests; the complete Python suite passed 206 tests. Wheel/sdist build and isolated no-project wheel execution succeeded. The Bun UI test and TypeScript/Vite production build both passed in this verification run.
- Research specifications, hypotheses, decisions, falsification plans, and explicit scientific limitations are maintained in the sibling repository.

## Heuristic early-announcement readiness rubric

| Gate | Weight | Current indicative score | Evidence or missing item |
|---|---:|---:|---|
| Domain-neutral language core and formal semantics | 25 | 25 | Implemented parser, AST, checker, rules and grammar |
| Executable event-driven and stochastic substrate | 20 | 20 | Stable calendar, typed payloads, Bernoulli/Uniform seeded replay |
| Regression verification, packaging, release automation | 20 | 17 | 206 Python tests and successful isolated wheel smoke; no repository CI workflow/tagged research preview confirmed |
| Marketing standard-library and extension story | 20 | 9 | A reusable source-imported lead-response library exists; multi-owner module signatures, broader marketing abstractions and population orchestration do not |
| Clear documentation and onboarding | 15 | 11 | README, runnable World and module example, specs and working wheel exist; a focused tutorial and outside contributor feedback remain missing |
| **Total** | **100** | **82** | Indicative **~80–85%** towards an honest experimental announcement |

The scores are intentionally coarse and policy-dependent. A different release definition can materially change them. Production and predictive-validity readiness are **not** measured by this score.

## Shortest credible announcement gate

1. **Publish and teach the now executable lead-response example**, with its typed Impression, Bernoulli result, delayed Checkout and both seed outcomes. Make the one-exposure and missing economic-bound checks prominent.
2. **Stabilize the import and library contributor story** with a small how-to covering the current one-export restriction, plus a roadmap for signatures, distributions and typed economic constraints.
3. **Add repeatable CI and a versioned preview artifact**, then test the Quick Start with independent contributors and invite concrete issues.
4. **Publish as an experimental research preview** with prominent disclaimers: no causal market validity, no PyMC/OmniTwin calibration integration, no real data, no Live/Shadow capability authorization.

## User-supplied concerns re-evaluated

**Typed event payloads are not missing:** DEC-030 already implements source-declared event schemas, exact inbound/outbound validation and payload field expressions.

**The two execution paths are separate:** `main.py` is a thin CLI entrypoint. The older marketing simulator and the domain-neutral World interpreter coexist in separate modules with explicit CLI dispatch. The first source-level marketing library and one-owner import contract now exist; a general module signature/registry ecosystem and a migration plan for the legacy engine remain adoption debt. Deleting the legacy engine now would break valid existing users and is not a demonstrated stale-code hazard.

## Next decision

A research-announcement blog post can truthfully introduce FunnelScript today if labeled experimental. A **repeatable open-source developer preview** should wait for CI, a tagged artifact, an import-writing tutorial and outside installation feedback. Forecasting claims should wait for independent held-out empirical validation and explicit uncertainty calibration.

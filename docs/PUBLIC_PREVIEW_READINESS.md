# FunnelScript Public Research Preview Readiness

Assessment date: 2026-10-31. This is a subjective engineering decision aid, **not** a statistically estimated probability of success or a forecast of real-market validity. Milestone assessed: a credible **public announcement as an experimental programming language**, not stable 1.0, production Live Execution, or calibrated market simulation.

## Observed technical evidence

- A distinct `world/entity/agent/state` grammar and exact primitive type checker.
- Language-defined rules, pre-event snapshot transitions, typed guards, typed local event records, event emission, finite event scheduling, and two seeded stochastic transition operators.
- `run-world` CLI accepts source files, repeatable external events, typed JSON records, seeds and processing limits; a reproducible marketing-flavored example exists in `examples/stochastic_world.fnl`.
- TDD: 25 new stochastic tests; full Python suite 183 passing. Wheel/sdist built successfully. One Bun UI test and the frontend TypeScript/Vite build passed.
- Research specifications, hypotheses, decisions, falsification plans, and explicit scientific limitations are maintained in the sibling repository.

## Heuristic early-announcement readiness rubric

| Gate | Weight | Current indicative score | Evidence or missing item |
|---|---:|---:|---|
| Domain-neutral language core and formal semantics | 25 | 25 | Implemented parser, AST, checker, rules and grammar |
| Executable event-driven and stochastic substrate | 20 | 20 | Stable calendar, typed payloads, Bernoulli/Uniform seeded replay |
| Regression verification, packaging, release automation | 20 | 15 | 183 tests and builds; no repository CI workflow/tagged research preview confirmed |
| Marketing standard-library and extension story | 20 | 3 | Marketing legacy simulator exists, but the new World lacks formal import/library contracts and a reusable marketing package |
| Clear documentation and onboarding | 15 | 10 | README, examples and specs exist; a 5-minute end-to-end tutorial and external clean-machine install feedback are missing |
| **Total** | **100** | **73** | Indicative **~70–75%** towards an honest experimental announcement |

The scores are intentionally coarse and policy-dependent. A different release definition can materially change them. Production and predictive-validity readiness are **not** measured by this score.

## Shortest credible announcement gate

1. **Show one end-to-end marketing World demonstration** that expresses a small conversion tactic, its typed events, a sampled response and a replayable experiment; document it as an assumed probability, not a market prediction.
2. **Define a minimal marketing-library extension/import boundary or clearly label the current lack of reusable modules** so future contributors know which parts are core and which remain future work.
3. **Add repeatable CI/installation verification and a versioned preview artifact**, then test the Quick Start on a clean environment and invite external feedback.
4. **Publish as an experimental research preview** with prominent disclaimers: no causal market validity, no PyMC/OmniTwin calibration integration, no real data, no Live/Shadow capability authorization.

## User-supplied concerns re-evaluated

**Typed event payloads are not missing:** DEC-030 already implements source-declared event schemas, exact inbound/outbound validation and payload field expressions.

**The two execution paths are separate:** `main.py` is a thin CLI entrypoint. The older marketing simulator and the domain-neutral World interpreter coexist in separate modules with explicit CLI dispatch. The absence of a shared standard-library/import interface remains real adoption debt; deleting the legacy engine now would break valid existing users and is not a demonstrated stale-code hazard.

## Next decision

A research-announcement blog post can truthfully introduce FunnelScript today if labeled experimental. A **repeatable open-source developer preview with community extension promises** should wait for the three engineering gates above. Forecasting claims should wait for independent held-out empirical validation and explicit uncertainty calibration.

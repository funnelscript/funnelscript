# FunnelScript Public Research Preview Readiness

Assessment date: 2026-10-31. This is a subjective engineering decision aid, **not** a statistically estimated probability of success or a forecast of real-market validity. Milestone assessed: a credible **public announcement as an experimental programming language**, not stable 1.0, production Live Execution, or calibrated market simulation.

## Observed technical evidence

- A distinct `world/entity/agent/state` grammar and exact primitive type checker.
- Language-defined rules, pre-event snapshot transitions, typed guards, typed local event records, event emission, finite event scheduling, and two seeded stochastic transition operators.
- `run-world` CLI accepts source files, repeatable external events, typed JSON records, seeds and processing limits; `import` compiles local and packaged one-owner World modules. The first Marketing Standard Library source ships at `std:marketing/lead_response.fnl`.
- TDD: 25 stochastic, 23 World module and 8 experimental-preview regression tests; the complete Python suite passed 214 tests. The v0.2.0a1 wheel/sdist built; a clean-directory wheel install executed `--version`, `init-world`, `check` and `run-world`. Bun lockfile install, frontend test and production build passed. The pinned CI workflow is authored but its remote run is a separate release gate.
- Research specifications, hypotheses, decisions, falsification plans, and explicit scientific limitations are maintained in the sibling repository.

## Heuristic early-announcement readiness rubric

| Gate | Weight | Current indicative score | Evidence or missing item |
|---|---:|---:|---|
| Domain-neutral language core and formal semantics | 25 | 25 | Implemented parser, AST, checker, rules and grammar |
| Executable event-driven and stochastic substrate | 20 | 20 | Stable calendar, typed payloads, Bernoulli/Uniform seeded replay |
| Regression verification, packaging, release automation | 20 | 18 | 214 Python tests and isolated wheel smoke; pinned CI added, but remote run and public source tag are not verified yet |
| Marketing standard-library and extension story | 20 | 9 | A reusable source-imported lead-response library exists; multi-owner module signatures, broader marketing abstractions and population orchestration do not |
| Clear documentation and onboarding | 15 | 14 | Installed CLI scaffolds a World, reports its version, and the preview tutorial's local-module extension is tested; independent contributor feedback remains missing |
| **Total** | **100** | **86** | Provisional **~85–90%** toward an honest experimental announcement, pending external CI/tag proof |

The scores are intentionally coarse and policy-dependent. A different release definition can materially change them. Production and predictive-validity readiness are **not** measured by this score.

## Shortest credible announcement gate

1. **Keep the tested lead-response tutorial public and honest**, including typed Impression, seeded Bernoulli conversion, delayed Checkout, one-exposure scope and unvalidated financial bounds.
2. **Use the verified first-run and local-module workflow** as the contributor contract, while leaving signatures, economic refinements and registry packaging for later research.
3. **Independently verify the new GitHub CI on the exact candidate SHA**, publish and verify the candidate Git tag only after relevant checks pass, and invite outside contributors to test clean installation.
4. **Publish as an experimental research preview** with prominent disclaimers: no causal market validity, no PyMC/OmniTwin calibration integration, no real data, no Live/Shadow capability authorization.

## User-supplied concerns re-evaluated

**Typed event payloads are not missing:** DEC-030 already implements source-declared event schemas, exact inbound/outbound validation and payload field expressions.

**The two execution paths are separate:** `main.py` is a thin CLI entrypoint. The older marketing simulator and the domain-neutral World interpreter coexist in separate modules with explicit CLI dispatch. The first source-level marketing library and one-owner import contract now exist; a general module signature/registry ecosystem and a migration plan for the legacy engine remain adoption debt. Deleting the legacy engine now would break valid existing users and is not a demonstrated stale-code hazard.

## Next decision

A research-announcement blog post can truthfully introduce FunnelScript today if labeled experimental. The developer-preview implementation now has tested onboarding and local wheel installation. A **public tagged source preview** still requires remote CI proof, tag verification and independent Git install smoke. Feedback from outside contributors remains a subsequent adoption gate. Forecasting claims must wait for held-out empirical validation and explicit uncertainty calibration.

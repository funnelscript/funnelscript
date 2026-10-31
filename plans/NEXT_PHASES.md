# FunnelScript: Required Next Phases and Scientific Product Direction

Assessment: 2026-10-31. Applies to `funnelscript` and `funnelscript-research`. This is a decision and execution map based on observed local source/tests, not an announcement of implemented features.

## 1. What is actually built

**Public experimental interpreter (`v0.2.0a1`)**: domain-neutral event calendar, typed World declarations and rule transitions, typed guards and event payloads, local emission, seeded Bernoulli/Uniform, source imports, a one-owner Marketing Standard Library example and CLI starter/check/run-world. A separate older StrategyAST marketing Monte Carlo engine exists. A separate Web Studio graph editor and browser demonstration simulator exist.

**Not established**: population-level equivalence between World and legacy StrategyAST, causal identifiability, calibration to real campaigns, out-of-sample forecasting skill, shared simulation semantics across Python and browser, operational provider authorization, safe Live effects, `fpm` registry, PyPI distribution, or an autonomous self-improvement mechanism.

**Fresh assessment evidence**:
- Phase 001 RED baseline: application 218 passed, 1 failed; research 3 passed, 1 failed, both on the academic-paper registry link.
- Phase 001 GREEN: application `uv run pytest -q` **219 passed, 58 subtests passed**; research `python3 -m unittest discover -s tests -v` **5 passed**.
- `cd apps/web && bun test`: 1 passed, only simple graph roundtrip.
- `src/funnelscript/cli.py:60,217` broadly catches exceptions; `Event.__post_init__` already rejects non-finite/negative timestamps.
- `src/funnelscript/tokens.py` has no multiplication/division tokens; `parser.py:404-442` uses `_parse_rule_expression` and `WorldAST.BinaryExpression` permits only `+` and `-`.
- `apps/web/src/lib/simulator.ts:25-36,81-84,142` fixes AOV, selects the first audience, calls `Math.random`, and reports `agentsCount` without using it in mechanics.

Both repos have pre-existing staged/unstaged changes, including the now-verified skill-bundle repair. Preserve other concurrent maintainer work.

## 2. The three evidence levels

| Evidence level | Question | Current status | Required proof |
| --- | --- | --- | --- |
| Interpreter correctness | Does the language execute its declared semantics? | Substantial local coverage; phase 001 repository hygiene repaired | Parser/type/event contracts, deterministic and adversarial property tests, artifact checks |
| Simulation validity | Does the computational model conserve state, money and events under defined assumptions? | Partial, split across legacy engine and a one-lead World library | Population semantics, reference accounting, RNG substreams, invariant and differential oracles |
| External market validity | Do forecasts agree with held-out observations beyond naive baselines? | **Not demonstrated** | Legal/consented dataset, pre-registered validation, parameter identifiability, calibration and uncertainty tests |

Do not promote a result from level 1 or 2 into a level 3 claim. A fixed seed proves replay, not a realistic conversion rate. A high agent count proves neither causality nor prediction.

## 3. Phase gates and ordering

### Gate A: Repair the development baseline (now)

**Cards**: 001, 002, 003. Skill-bundle integrity repair (001) is complete in both repos with fresh passing suites. Next, execute 002 CLI boundary handling and 003 expression grammar/type-system work as independent TDD cards.

**Done means**: both full suites pass on the actual dirty-worktree baseline; new parser and CLI regression cases fail on the old behavior and pass on the implementation; no unrelated staged changes are overwritten. Baseline count is not a target: tests added later change the total.

**Stop if**: the repair requires deleting or resetting user work, or an unspecified exception/path behavior would change a documented interface.

### Gate B: Establish a language conformance oracle

**Card**: 006, dependent on 003.

Prove event ordering and replay, snapshot-atomic transitions, finite calendar budgets, typed payload acceptance/rejection, local-import confinement, and boundary arithmetic with table-driven/property-oriented tests. Formalize a small executable trace format that a future runtime can independently reproduce.

**Done means**: all acceptance cases and their deliberately invalid near-neighbors produce named results; no hidden marketing rule is added to the neutral compiler. The schema/EBNF, `spec/` and `evals/` match the observed interpreter.

**Do not mistake**: hundreds of passing unit tests for external model validity.

### Gate C: Design one reference population and metric contract

**Card**: 007, dependent on 006.

The legacy `SimulationEngine` and `WorldExecutor` have different abstractions. Before adding another engine, decide the reference path and define how a population of entities gets initial state, events, independent RNG streams, terminal accounting, sample weights and reproducible trial metrics. Use a two-segment, small-cohort pilot before 100,000-agent performance ambitions. Keep empirical behavior as injected assumptions, not compiler defaults.

Core invariants to test:
- Population partition: `sum(state_counts) = initialized_population` at each checkpoint, including terminal states.
- Monetary ledger: `cash_t = cash_0 - settled_spend + settled_inflows - explicit_costs`; receivables are not liquid cash.
- Purchase/wallet constraints only when a **marketing model explicitly declares** those constraints; do not impose them on every World.
- Fixed inputs/seed/engine version reproduce a trace; alternative seed changes a stochastic scenario without changing static model structure.
- Compare rates/ROAS/CAC/CVaR only when units, denominator, time horizon and zero-denominator behavior are specified.

**Done means**: a reproducible reference fixture with machine-checked state and metric traces, clear legacy compatibility, bounded runtime/memory measurements and no claims of measured market truth.

### Gate D: Bring the canvas onto an honest execution boundary

**Card**: 005 can begin immediately with honest labeling and deterministic demonstration mode; any **parity** claim depends on 007.

Near-term: explicitly identify a browser result as illustrative, or disable forecast-style risk statements when graph semantics are not consumed. Add a seeded driver if a repeatable demonstration is desired; show that changing graph edges/audience segments either changes supported modeled behavior or produces a clear unsupported-flow error. Avoid automatically promising exact Python parity.

Later: choose a single versioned simulation contract and golden fixtures for the browser. If a common authoritative engine is infeasible, keep the two modes visibly distinct. Do not hide the difference behind a visual DAG animation.

**Done means**: no simulated metric claims coverage of edges, audience cohorts, seed stability or agent population that the implementation does not actually use.

### Gate E: Empirical calibration and falsification

**Card**: 008, after 007 and the data-owner decision.

Use a permitted, de-identified historical dataset with explicit date, spend, exposure, conversion/revenue, margin, refunds, settlement timing and known interventions. Pre-register temporal holdout windows and naive baselines before fitting; avoid random leakage across time. Distinguish observational fit from causal lift. A PyMC-Marketing adapter is optional and versioned; it is a calibration source, not a required runtime dependency.

Evaluate proper predictive metrics, interval coverage, drift sensitivity and decision quality under downside scenarios. If meaningful variables are unidentifiable or holdout performance does not beat a documented baseline, state **not validated** and do not adjust copy to sound predictive.

**Done means**: reproducible experiment manifest, legal data provenance, benchmark comparison, diagnostics, falsifications and an explicit qualified/non-qualified market claim. Without real permitted data, only the evaluation harness and protocol can be completed.

### Gate F: Bounded, evidence-driven model improvement

**Card**: 004, dependent on 006, 007 and an actual 008 validation receipt.

First write and review a candidate-evaluation research contract: what is comparable, what is a hard invalidity, what objective is dimensionally meaningful, how common random numbers are managed, and who can see holdouts. Prototype with inert candidates only. No autonomous editing, promotion, deploy or `git worktree` mutation on the main workspace by this advisor.

**Done means**: a candidate that exploits missing settlement/denominator accounting loses to a correctly gated baseline; significance is established by independent runs, not a single attractive ROAS score. An append-only checksum detects accidental corruption but is not cryptographic immutability without trusted signing.

### Gate G: Non-mutating effects and observational Shadow mode

**Card**: 009, dependent on 006; may be explored in parallel with empirical validation, but only using mocks and expressly authorized read-only fixtures.

Preserve the existing inert `EffectIntent` model. Define capability gates and an explicit Simulation versus Shadow boundary; no provider token or network write belongs in a language test. A future Live mode needs separate approval, idempotency persistence, budget ceilings, rollback/compensating rules and security review. **Live is outside this plan.**

**Done means**: no effect can escape from untrusted World execution; unauthorized handlers fail closed; fake-provider tests cover replay, rejection and partial failure.

### Gate H: Independent developer adoption and the next experimental release

**Card**: 010, after the relevant language, CLI and truthful Web preview gates. This gate can ship language tooling **without** waiting for market calibration, provided claims remain experimental.

Recruit independent first-run feedback using clean checkout, documented Git-source install, two real World examples and traceable failures. Re-run locked CI and installed-wheel checks on the exact candidate before any future tagged preview. PyPI publishing, public API stability promises or GitHub Release creation require separate operator decisions.

**Done means**: reproducible installation and onboarding evidence from outside the maintainer's checkout, actionable issue list, truthful release notes and a release/no-release decision.

## 4. What to defer deliberately

- **`fpm` package registry and remote module fetching**: adds trust, signing and dependency-resolution problems before versioned local module semantics are settled.
- **LSP and IDE extensions**: useful once grammar diagnostics and semantic error spans are stable; not a substitute for source conformance.
- **OmniTwin/cognitive personas**: optional specialized research layer, not necessary for a first calibrated, parsimonious population model. Preserve DEC-003/006 separation.
- **Full WebAssembly or a second browser engine**: risks independent physics without a reference oracle.
- **Automatic ad execution and budget changes**: require an independent security/authorization program, not a simulation feature flag.
- **100,000-agent performance claims**: measure on pinned hardware, model, horizon and trials only after reference semantics are correct; never report a hypothetical throughput target as achieved.

## 5. Decisions the owner will eventually make

1. **Reference semantics** (Gate C): one canonical engine vs. a translation layer with explicit coverage. Recommended: a domain-neutral World reference and compatibility adapter, rather than silently deleting the legacy Strategy engine. This is a reversible architecture recommendation, not yet an accepted ADR.
2. **Permitted empirical dataset** (Gate E): its owner, consent/legal basis, aggregation/privacy policy and release rights. This is a blocking decision for external validity, not for the language preview.
3. **Market-facing claim threshold** (Gate E): which out-of-sample improvement and interval coverage are persuasive enough for a stated use case. Pre-register with the dataset owner, not after observing results.
4. **Provider access** (Gate G): whether and where a true Shadow data feed may run. Only the operator can approve access or Live activation.
5. **Publishing scope** (Gate H): stay Git-source preview or explicitly approve PyPI/package registry and release promises.

## 6. Operating standard and source anchors

Follow `AGENTS.md` in both repos, application `docs/MASTER_PLAN.md`, research `DECISIONS.md` (especially DEC-003 through DEC-010, DEC-019, DEC-027 through DEC-035), and the research `spec/marketing-stdlib-v0.md`/evaluation. Each change must have research anchor, falsifiable hypothesis and explicit invariant **before** code. Keep the compiler domain-neutral.

Selected primary external sources for the future research spikes:
- [PyMC-Marketing documentation](https://www.pymc-marketing.io/en/stable/) and [time-slice / calibration learning guide](https://www.pymc-marketing.io/en/stable/guide/mmm/mmm_learning_path.html) for observational calibration and holdout design.
- [NumPy random sampling documentation](https://numpy.org/doc/stable/reference/random/) for independent RNG streams and reproducibility boundaries.
- [Python Packaging Guide](https://packaging.python.org/en/latest/specifications/version-specifiers/) and [uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/) for repeatable prerelease verification.

These references define methods or tooling behavior, **not** evidence that FunnelScript is calibrated. Review their current versions before implementing against APIs.

## 7. Immediate 48-hour *work order*, not a promised calendar

1. **001 complete. Start 002 with a RED CLI-boundary test.** Preserve existing maintainer changes and isolate the expected error contract.
2. **Design CLI and parser regression examples** for 002/003, especially unexpected exception propagation, malformed/oversized JSON, EOF, typed arithmetic and division by zero.
3. **Mark Web Studio as illustrative until proven otherwise.** Write a failing graph-change test for the current ignored-flow behavior and specify what the display can honestly say.
4. **Create the 006 conformance corpus proposal** once 003's operator scope is accepted.
5. **Do not start autonomous evaluator implementation** until Gates C and E produce a usable model truth criterion.

This ordering responds to observed current risk. It does not assume availability of a real campaign dataset or authority to perform external marketing actions.

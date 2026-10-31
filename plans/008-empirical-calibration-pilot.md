# Plan 008: Run a Pre-Registered Empirical Calibration and Validation Pilot

> Executor: research and validation first. No raw campaign data or credentials may be committed. This plan does **not** claim that causal lift can be inferred from observational fit. Read AGENTS.md in both repositories and DEC-003 through DEC-007.
>
> Drift preflight: `git status --short -- spec/ evals/ tests/` in research and `git status --short -- tests/ src/funnelscript/` in application. The planning bases are research `abe561f` and application `41f00f1`, but dirty index/worktree state matters.

## Status

- **Priority:** P1 before forecasting claims, not before an experimental language preview
- **Effort:** L
- **Risk:** HIGH, because leakage, nonidentifiability or fabricated validation can mislead budget decisions
- **Depends on:** 007 verified; explicit authorized dataset and owner
- **Category:** direction / research / tests
- **Planned at:** `41f00f1` (app), `abe561f` (research), 2026-10-31
- **Status:** BLOCKED for final empirical acceptance until permitted real observations exist

## Why this matters

A simulator with seeded stochastic decisions can be internally reproducible yet forecast reality poorly. Marketing conversion, spend/cash and channel responses require identification and calibration against observations not reused for fitting. The first empirical milestone should be deliberately small, with explicit failure outcomes and a baseline that might outperform FunnelScript.

## Anchors and explicit assumptions

- Current implementation: `src/funnelscript/stdlib/marketing/lead_response.fnl` uses caller-supplied `conversion_probability`, `cpc` and `order_value`; `WorldExecutor` has no data fitting.
- Existing research: `spec/marketing-stdlib-v0.md`; `DEC-005` selects a decoupled PyMC-Marketing interface, **not** a mandatory runtime dependency.
- Official method references: [PyMC-Marketing](https://www.pymc-marketing.io/en/stable/), [MMM learning path](https://www.pymc-marketing.io/en/stable/guide/mmm/mmm_learning_path.html), [NumPy random](https://numpy.org/doc/stable/reference/random/).
- **H-VAL1:** on a chronologically held-out interval, a calibrated population scenario beats a pre-registered simple baseline on a primary proper metric. Falsifier: equal/worse holdout error or high sensitivity to plausible assumptions.
- **H-VAL2:** forecast intervals achieve pre-registered empirical coverage without extreme width. Falsifier: coverage outside the tolerance defined **before** evaluation.
- **H-VAL3:** a model cannot promote a strategy by omitting delayed settlement, refunds, fatigue or costs; explicit stress cases reveal hidden downside. Falsifier: a smaller but unrealistically favorable objective wins the evaluation.
- Never assume data are causal just because attribution fields exist. Where experiments are absent, mark incremental effect **not identified**.

## Scope

**In:** research `spec/empirical-validation-v0.md`, `evals/empirical-validation-v0.md`; application `tests/test_validation_protocol.py` and minimal synthetic schema/metric test fixtures under `tests/fixtures/validation/`. A fitting adapter may be proposed in the spec, but implementing it requires a separate approved card.

**Out:** raw or row-level private data in Git, new required `pyproject.toml` dependencies, production fitting module, automated budget recommendations, causal incrementality claims, marketing API keys or external campaign mutations.

## Procedure with stop gates

1. **Acquire permission and data contract**: identify data owner, allowed use/retention, period, timezone, units, consent/contractual rights, aggregation and de-identification. Minimum observable fields: timestamp, spend, impressions/clicks where available, conversions/orders, collected revenue, refunds, margin, settlement date and intervention annotations. Verify: metadata-only manifest with zero secret values; **STOP** if the owner cannot authorize use.
2. **Pre-register evaluation** before fit: fixed train/validation/chronological holdout windows, primary loss (e.g. MAE on revenue or Poisson deviance on counts, chosen by actual target), simple last-period/seasonal baselines, forecast interval coverage/tolerance, missingness and drift sensitivity, and allowable model revisions. Verify: reviewer can timestamp the protocol and identify leakage edges; no metric selected after observing holdout.
3. **Implement deterministic validation mechanics on synthetic data** only: schema rejection, date boundary tests, stable seed log, no random time leakage, correct metric units, missing/zero denominator behavior. Verify: `uv run pytest tests/test_validation_protocol.py -v` exits 0, and a deliberately leaked split is rejected.
4. **Fit pilot in a bounded independent research environment** using an approved data mount and pinned versions. Record parameter identifiability, posterior predictive checks and time-slice validation. If PyMC Marketing is used, keep it an optional external adapter and record actual API/version. Verify: a repeatable command and redacted artifact checksums are documented; no fitting command is described as executed unless it ran.
5. **Evaluate locked holdout once**: compare against pre-registered baselines, interval diagnostics and downside/settlement counterexamples. Report all failure cases and uncertainty. Verify: independent reviewer can recompute metrics from permitted outputs; no holdout example is also used for tuning.
6. **Decide scope of public claims**: `VALIDATED_FOR_SCENARIO`, `INCONCLUSIVE`, or `NOT_VALIDATED` with population, horizon, data regime and known exclusions. Verify: research `python3 -m unittest discover -s tests -v` and application `uv run pytest -q` both pass after any protocol test changes.

## Done criteria

- [ ] Approved data provenance and pre-registered, timestamped protocol.
- [ ] No raw data/keys in either Git repository or generated report.
- [ ] Chronological holdout comparison against a genuinely simple baseline.
- [ ] Identifiability, predictive error, interval coverage and liquidity sensitivity analyzed.
- [ ] Explicit qualified evidence verdict with failures preserved.
- [ ] All relevant test and provenance checks actually executed.

## STOP and maintenance

Without a legal/usable dataset, finish only the research protocol and synthetic checker; retain **BLOCKED** for empirical claim. If the baseline wins or parameters cannot be identified, record a negative result and do not tune until a new pre-registered experiment. Model evaluation and self-improvement plan 004 must consume this verdict, never synthetic scores alone.

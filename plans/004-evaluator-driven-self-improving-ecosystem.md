# Plan 004: Design a Falsifiable Candidate-Evaluation Contract Before Self-Improvement

> Executor: this is a **research/design and synthetic evaluation spike**. It is not permission to create a self-editing agent, mutate active worktrees, automatically promote a candidate or deploy a model. Preserve the working tree and read DEC-003/004/005/008/009 plus plans 006-008 and their actual completion evidence.
>
> Drift check: `git status --short -- src/funnelscript/ tests/ plans/`, `git diff 41f00f1 -- src/funnelscript/ tests/`; research `git status --short -- spec/ evals/ DECISIONS.md` and `git diff abe561f -- spec/ evals/`. Do not confuse committed HEAD with staged or untracked state.

## Status

- **Priority:** P2 after scientific evidence gates
- **Effort:** L
- **Risk:** HIGH, because a flawed objective can reward model fraud or unsafe marketing decisions
- **Depends on:** 006 semantic conformance, 007 population/metric contract and 008 empirical validation with a genuine permitted holdout receipt
- **Category:** direction / research
- **Planned at:** application `41f00f1`, research `abe561f`, reassessed 2026-10-31
- **Status:** BLOCKED until the three prerequisites have current evidence

## Why this matters

An automated optimizer can make ROAS look better by omitting settlement delays, reducing modeled spend, using arbitrary conversion priors or leaking holdout data. The current code has an older `StrategyAST` Monte Carlo engine and a one-lead World interpreter but no verified equivalent population objective or empirical prediction oracle. The original proposal prematurely combined full engine implementation, a scorer, hidden holdouts, immutable ledger and automatic promotion. The scientifically appropriate next card is to prove that a candidate comparison is even meaningful, and preserve negative results.

## Observed source boundaries and research anchor

- `src/funnelscript/runtime/engine.py`: older marketing simulation with Monte Carlo distributions and `StrategyAST`.
- `src/funnelscript/runtime/world_executor.py`: type-checked World event reducer. `src/funnelscript/stdlib/marketing/lead_response.fnl` represents one assumed lead response, not a trial population.
- `src/funnelscript/runtime/telemetry.py`: distribution metrics. `src/funnelscript/compiler/linter.py`: legacy strategy static checks. `docs/PUBLIC_PREVIEW_READINESS.md` explicitly disclaims empirical forecasting.
- Research DEC-003/004/005/008/009, and completed 006-008 outputs will govern the comparison.
- **H-EV1 (correctness):** syntactically invalid, financially non-conservative under a declared marketing constraint or nondeterministically irreproducible candidates fail hard gates regardless of headline ROAS. Falsifier: such a candidate receives a promotable score.
- **H-EV2 (objective):** a riskier model cannot win solely from mixing incompatible monetary/dimensionless units. Falsifier: a units rescaling changes candidate order with unchanged economics.
- **H-EV3 (holdout):** a candidate tuned only on training cases may fail an independently sequestered validation set without making the evaluator approve it. Falsifier: leakage or fallback-to-training leads to ACCEPT.
- **Invariant:** compare like with like: equal data regime, population definition, units, time horizon and trial design. A hash-chain alone is **not** cryptographic immutability without an independently trusted signing/anchoring boundary.

## Scope

**In:** research `spec/candidate-evaluation-v0.md`, `evals/candidate-evaluation-v0.md`; application `tests/test_evaluator_contract.py` and tiny synthetic `tests/fixtures/evaluator-contract/` fixtures *after prerequisites are available*. Optional non-executable score/decision schema in the research spec.

**Out:** `src/funnelscript/runtime/evaluator.py` production code, `scripts/eval_candidate.py`, `scripts/verify_ledger.py`, Git worktree mutation, HMAC key provisioning, new runner dependencies, model promotion, write-capable agent loops, provider effects, CI deployment, hidden credentials or making model-accuracy claims.

## Step-by-step research and verification

1. **Require current upstream proof:** read verified 006 trace oracle, 007 reference metric units and 008 validation verdict. If 008 is still BLOCKED or `NOT_VALIDATED`, STOP implementation and record exactly which missing evidence prevents candidate ranking. A paper-only candidate-comparison risk analysis may still be written but not marked DONE.
2. **Define candidate identity and legality:** immutable source/input/seed/model version tuple; separate compiler/type/schema gate, economic model constraints, reproducibility gate, numerical sanity and validation-data contract. Hard invalidity cannot be traded for a high score. Verify: research spec has each gate, reject code and a falsifiable counterexample.
3. **Define objectives mathematically:** avoid direct `w1*ROAS + w2*(1-P(ruin)) - w3*CVaR($)` without dimensionless normalization and pre-registered risk preferences. Prefer a Pareto or thresholded policy with specified units, confidence intervals and loss tails. Compare candidates by paired/common-random-number trials only if RNG substreams and contamination controls from 007 are proven. Verify: a manual three-candidate table with units shows consistent ranking under currency rescaling.
4. **Define holdout and anti-gaming controls:** candidate proposal process must not read evaluation-only data; repository-tracked test fixtures are **visible** and therefore not secret. Record locked train/validation/holdout access rules, re-evaluation after objective changes and counterexamples for omission of fees, settlement, refunds, fatigue and conversion denominators. Verify: reviewer can identify what data each actor may see.
5. **Make a synthetic contract oracle, not an autonomous agent:** after prerequisites, write `tests/test_evaluator_contract.py` asserting malformed candidate rejection, units invariance, robust-versus-fragile ranking and tamper detection limits. The oracle must use independent manually derived expected outcomes, not call the same scorer to compute the answer. Verify: `uv run pytest tests/test_evaluator_contract.py -v` exits 0; `uv run pytest -q` and research `python3 -m unittest discover -s tests -v` exit 0.
6. **Review promotion governance:** specify human approval, artifact provenance, rollback plan, risk policy, external validation refresh cadence and separate implementation cards. No implementation proceeds from a single synthetic score. Verify: `evals/candidate-evaluation-v0.md` records observed experiments, failed hypotheses and an explicit `DESIGN_ACCEPTED`/`INCONCLUSIVE` verdict.

## Done criteria

- [ ] Upstream 006-008 evidence is current and permits meaningful comparable metrics.
- [ ] Hard gates cannot be bypassed by a favorable objective score.
- [ ] Objective units, signs, denominators, uncertainty and holdout protocol are pre-registered.
- [ ] Negative and adversarial candidates are tested with an independent oracle.
- [ ] Ledger semantics distinguish local integrity from trusted immutability; no false "guarantee" of model truth.
- [ ] A bounded future implementation plan is proposed, with no source evaluator/agent/auto-promotion built by this card.

## STOP conditions and maintenance

STOP if the target is one-lead World versus population StrategyAST without the 007 bridge; if real validation fails under 008; if candidate authors can inspect supposedly hidden holdouts; if automated worktrees or deployment are requested in this research card; or if a score depends on arbitrary currency scaling. Future implementation must re-run the full corpus after any objective, data or code change and preserve all rejected verdicts.

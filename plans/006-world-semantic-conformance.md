# Plan 006: Establish a World Semantic Conformance Oracle

> Executor: read the complete plan and both repository AGENTS.md files. This is a **test and research contract**, not an invitation to redesign the World runtime. STOP on unexpected scope expansion. Update the index only after verified completion.
>
> Drift preflight: in the application run `git status --short -- src/funnelscript tests/ examples/` and `git diff 41f00f1 -- src/funnelscript tests/ examples/`; in research run `git status --short -- spec/ evals/` and `git diff abe561f -- spec/ evals/`. Include staged/untracked modifications; commit-to-commit comparison alone is insufficient.

## Status

- **Priority:** P1
- **Effort:** M
- **Risk:** MED, because tests may expose a real semantic inconsistency that this plan must not silently fix
- **Depends on:** 003 implemented and verified; 001 baseline green
- **Category:** tests / research
- **Planned at:** application `41f00f1`, research `abe561f`, 2026-10-31
- **Status:** TODO

## Why this matters

The World reference interpreter has separate tests for event scheduling, typed state, guards, sampling and imported modules. The next population and evaluator work needs a stable, independent **behavioral oracle** that checks their interactions rather than merely checking that each feature works in isolation. A deterministic corpus of adversarial traces is a prerequisite to comparing two runtimes or claiming seeded counterfactuals.

## Current state and invariants

- `src/funnelscript/core/event_machine.py`: `Event.__post_init__` rejects invalid time; `EventMachine.run` orders events by time, priority and insertion ordinal, bounds events and owns `random.Random(seed)`.
- `src/funnelscript/runtime/world_executor.py:60-95`: `_evaluate` interprets typed expressions, and sampled transitions use a caller-supplied RNG.
- `src/funnelscript/parser.py`, `src/funnelscript/compiler/world_ast.py`: source grammar and exact primitive type checking. The latter rejects implicit cross-type arithmetic.
- `tests/test_event_machine.py`, `tests/test_world_rules.py`, `tests/test_world_payloads.py`, `tests/test_world_stochastic.py`, `tests/test_world_modules.py`: existing test patterns. Avoid copying identical assertions.
- Research: `spec/event-kernel-v0.md`, `spec/rule-transitions-v0.md`, `spec/stochastic-operators-v0.md`, `spec/marketing-stdlib-v0.md`; accepted DEC-019, DEC-027 through DEC-032.
- **H-C1:** same World source, seed and events produce byte-canonical state and event trace across repeated executions. Falsifier: unequal state/trace with identical versions and inputs.
- **H-C2:** transition source order does not change reads of pre-event state; false guards consume no sample and emit no event. Falsifier: a rule reads a value written earlier in the same event.
- **H-C3:** invalid payload/module path/event time/type is rejected before model state is mutated. Falsifier: partial state change on a rejected event.
- **Invariant:** `t_next >= t_current`; `events_processed <= max_events`; no compiler-level marketing or financial rule. Valid seeded traces use a canonical serialization with stable key ordering.

## Scope

**In:** application `tests/test_world_conformance.py` (new), `tests/fixtures/world-conformance/` (minimal deterministic source/trace fixtures); research `spec/world-conformance-v0.md` and `evals/world-conformance-v0.md` (new).

**Out:** production parser/executor/compiler changes, `pyproject.toml`, package dependencies, provider calls, market calibration, reinterpretation of DEC-008/009. If tests prove a production defect, STOP and author a separate TDD repair card.

## Steps and exact verification

1. **Research before tests:** record the three hypotheses, input grammar, trace canonicalization rule and falsifiers in `spec/world-conformance-v0.md`. Separate semantic replay from empirical accuracy. Verify: `rg -n 'H-C1|H-C2|H-C3|Falsifier|canonical' spec/world-conformance-v0.md` in research, with each heading present.
2. **Build minimal traces:** one simultaneous assignment rule, one equal-time tie, one false guard plus later sample, one typed event payload, one imported module alias, and invalid near-neighbors. Do not encode a giant fixture unrelated to real behavior. Verify: `uv run pytest tests/test_world_conformance.py -v` after writing the tests, expected collection and execution; if any expected behavior fails, STOP and record RED evidence.
3. **Repeat and perturb:** compare at least three replay runs under one seed, plus a changed seed for a stochastic model; test event processing cap and EOF/binary boundaries from 003. Verify: `uv run pytest tests/test_world_conformance.py -v` exits 0 and asserts trace equality and expected differences, not only success exit codes.
4. **Record verification provenance:** write source SHA, fixture IDs, interpreter version, exact command and pass/fail totals to `evals/world-conformance-v0.md`. Verify: `python3 -m unittest discover -s tests -v` exits 0 in research; `uv run pytest -q` exits 0 in application.
5. **Review independence:** check fixtures do not simply duplicate the implementation logic or call internal helpers to calculate expected answers. Verify: reviewer reads fixture expected values without deriving them from `WorldExecutor` in the same test.

## Test plan and done criteria

- [ ] Correct and deliberately invalid fixed traces cover H-C1 through H-C3.
- [ ] Test assertions detect event order, state atomicity, RNG consumption boundary and rejection before side effects.
- [ ] Both full suites pass on current worktrees after 003; no hardcoded total counts.
- [ ] `spec/` and `evals/` explicitly label external market validity **not tested**.
- [ ] `git status --short` shows only declared plan implementation files plus pre-existing changes that were not altered.
- [ ] Research trilogy and application master/failure lessons are synchronized by the implementing executor if any new decision or defect is established.

## STOP and maintenance

STOP if 003 is unfinished, expected semantics conflict with an accepted DEC, a production fix is required, or a fixture cannot be validated independently. Capture the smallest failing trace for a new repair plan. A future population engine or browser bridge must run this same corpus or declare which contracts it does not implement.

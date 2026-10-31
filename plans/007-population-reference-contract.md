# Plan 007: Prove a Population and Reference Metric Contract

> Executor: this is a bounded **architecture and experimental spike**, not authorization to replace the legacy simulator or implement a 100,000-agent production engine. Read both AGENTS.md files, DEC-003/005/008/009/010, and this entire plan.
>
> Drift preflight: application `git status --short -- src/funnelscript/runtime/ src/funnelscript/stdlib/ tests/ examples/`, `git diff 41f00f1 -- src/funnelscript/runtime/ src/funnelscript/stdlib/ tests/ examples/`; research `git status --short -- spec/ evals/ DECISIONS.md`. Inspect staged and untracked files before touching any owned path.

## Status

- **Priority:** P1
- **Effort:** L
- **Risk:** HIGH, because an incorrect metric/agent abstraction contaminates every downstream forecast
- **Depends on:** 006 complete; 003 semantics stable
- **Category:** direction / architecture / tests
- **Planned at:** application `41f00f1`, research `abe561f`, 2026-10-31
- **Status:** TODO

## Why this matters

The World interpreter currently executes one source-defined actor journey, while the older `SimulationEngine` reports campaign-level Monte Carlo distributions over a separate `StrategyAST`. There is no evidenced population-equivalent bridge. A numerical claim about 100,000 consumers, ROAS, liquidity or CVaR needs explicit population accounting, input assumptions, trace semantics, units and statistical aggregation before speed work or automatic scoring.

## Observed entry points and research anchors

- `src/funnelscript/runtime/world_executor.py`: one World state and one seeded event run.
- `src/funnelscript/runtime/engine.py`: legacy `SimulationEngine`; it references `entities.audiences[0]` and processes a separate `StrategyAST.logic_flow`.
- `src/funnelscript/runtime/telemetry.py`: existing ROAS/CAC/cash-risk distribution types. Do not silently assume they can be reused by World without a mapping.
- `src/funnelscript/stdlib/marketing/lead_response.fnl` and `examples/marketing_lead_response.fnl`: **one exposure/lead**, not a population forecast.
- `src/funnelscript/core/event_machine.py`: seeded clock with a run-local RNG; no independent per-agent stream contract.
- Research `spec/marketing-stdlib-v0.md`; DEC-003/005/006/008/009/010/019/032. The language core must remain domain-neutral.

**H-POP1:** a fixed finite cohort conserves agent identity over all intermediate/terminal partitions: `sum(N_state(t)) = N_initial`. Falsifier: lost/duplicated agent on an event or terminal transition.

**H-POP2:** independent, stable RNG substream identity for `(world_seed, agent_id, trial_id)` preserves an unchanged agent's trajectory under cohort reordering. Falsifier: permuting cohort order changes matched agent outcomes.

**H-POP3:** one reference accounting convention reconciles `initial_cash + settled_receipts - paid_spend - declared_costs` to ending cash, while receivables remain illiquid until settlement. Falsifier: spending against unpaid revenue or failing conservation. This is a **marketing-library** constraint, not a universal language axiom.

## Scope

**In:** research `spec/population-reference-v0.md`, `evals/population-reference-v0.md`; application `tests/test_population_reference.py` and a small `tests/fixtures/population-reference/` corpus. A short architecture recommendation and experiment may live in those files.

**Out:** public runtime rewrites, replacement/removal of legacy StrategyAST, provider integrations, new required Python dependencies, frontend changes, real-market parameters, scale boasts or production migration. Only a reviewed follow-on implementation card may change production modules.

## Step-by-step experiment

1. **Map both engines' contracts**: document one-input, one-trial, one-agent, one-population, cohort/segment and metric scopes; record which fields are absent, unit conversions, zero-denominator behavior, timing of cash flow and what `agents_count` means in each. Compare two architectural options: (A) World-backed population runner with a compatibility adapter and (B) continued separate engines with explicit non-parity. Recommend A *provisionally*; do not treat it as accepted DEC until review. Verify: `rg -n 'WorldExecutor|SimulationEngine|Decision|Trade-off|Falsifier' spec/population-reference-v0.md`.
2. **Define metrics before implementation**: ROAS revenue/spend and accounting perspective, CAC spend/new customers, conversion base, `P(insolvency)` trial denominator, VaR/CVaR sign/tail, zero cases, currency, timeframe and reporting intervals. Reject direct summation of dimensionless ROAS with monetary CVaR. Verify: each metric includes formula, unit, missing-data policy and independently calculable example in the spec.
3. **Write a tiny independent oracle** for two labeled segments with 10, 100 and 1,000 modeled agents, including terminal outcomes and delayed cash. Use tests and fixed fixtures; avoid introducing a third permanent engine. If no existing World API permits a defensible mechanism, document the blocking semantic gap and STOP before inventing a compiler keyword. Verify: `uv run pytest tests/test_population_reference.py -v` exits 0 once contract tests are expressible; otherwise record a reproducible failing scenario.
4. **Test paired counterfactual identity**: identical seeded inputs reproduce per-agent traces; cohort iteration order changes nothing for matched stable IDs. Verify: same test command, with explicit permutation and seed assertions.
5. **Record a reviewer-ready decision**: list measured runtime/memory for 10/100/1,000 on named hardware, accuracy limits, compatibility risks, and the minimum next production implementation card. Verify: `uv run pytest -q` and research `python3 -m unittest discover -s tests -v` exit 0; report observed results only.

## Done criteria

- [ ] Independently checkable population and cash conservation examples.
- [ ] Reference metric definitions with units, denominators and sign conventions.
- [ ] Fixed-seed and order-perturbation tests.
- [ ] Explicit legacy compatibility matrix, non-equivalence boundaries and architecture decision request.
- [ ] No source or frontend engine rewrites; no performance claims extrapolated from 1,000 to 100,000 agents.
- [ ] Empirical prediction remains explicitly unvalidated; a separate Gate E requires real data.

## STOP and maintenance

STOP if ownership/identity cannot be represented without a new semantic contract, if a test relies on copying runtime logic as its expected answer, if a financial invariant conflicts with DEC-009, or if the comparison would require modifying out-of-scope production code. Record the precise missing capability. Later 005 browser-parity and 008 calibration cards must use this metric convention, not invent another.

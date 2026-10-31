# Plan 005: Make Web Studio Simulation Fidelity and Claims Explicit

> Executor: this card repairs the **honesty and repeatability** of the browser preview. It is not authorization to declare a second TypeScript engine equivalent to the Python World or legacy Strategy simulator. Read the UI call path, tests and DEC-008/009 before changes.
>
> Drift preflight: `git status --short -- apps/web/src/ apps/web/package.json` and `git diff 41f00f1 -- apps/web/src/ apps/web/package.json`. Read existing user edits if present; avoid generated `apps/web/dist/`.

## Status

- **Priority:** P1 for any visible simulation claims
- **Effort:** M
- **Risk:** MED, because inaccurate financial cards can mislead users
- **Depends on:** none for truthful labeling and reproducible illustrative mode; 007 is a hard dependency for any **authoritative engine parity** claim
- **Category:** correctness / UX / tech-debt
- **Planned at:** application `41f00f1`, reassessed 2026-10-31
- **Status:** TODO

## Why this matters

The visual editor produces `StrategyAST` from graph nodes and edges, but `runInBrowserSimulation` ignores the graph's `logic_flow`, hardcodes AOV and uses only the first audience. It invokes unseeded `Math.random` and reports the passed `agentsCount` although its simulation loop does not simulate a population of that size. A multi-branch canvas may therefore display familiar financial figures that do not represent its actual graph. The first acceptable remedy is a truthful, bounded illustration with negative tests; a reference-equivalent engine is separate future work.

## Verified current path and research anchors

- `apps/web/src/lib/transpiler.ts`: graph/AST conversion with `logic_flow`. `apps/web/src/lib/transpiler.test.ts` covers only one simple 3-node roundtrip; `bun test` returned 1 pass.
- `apps/web/src/lib/simulator.ts:25-36`: `const aov = 120.0`, `ast.entities.audiences[0]`, first paid and conversion touchpoints; no graph traversal.
- `simulator.ts:81,84`: `Math.random()` draws with no explicit seed; `simulator.ts:142`: `agents_per_trial: agentsCount` is metadata, not computed agents.
- `apps/web/src/App.tsx:143-147`: `runSimulation` calls `runInBrowserSimulation(currentAst, 100, virtual_agents_count)`; the results feed UI state.
- `apps/web/src/components/telemetry/DistributionCards.tsx`, `CashRunwayChart.tsx`: user-facing numerical output.
- `apps/web/src/types.ts:106`: `SimulationResult` contract.
- **H-WEB1:** unsupported topology or audience coverage cannot silently produce an authoritative financial forecast. Falsifier: two materially different unsupported flows show equivalent "simulated" results without a disclosure or error.
- **H-WEB2:** illustrative calculations under a declared seed/input are reproducible; changing supported parameters affects the corresponding metric. Falsifier: identical inputs/seed yield different numeric fields or an ignored parameter is represented as modeled.
- **H-WEB3:** the UI never claims to have simulated N consumer agents when N is not used in state transitions.
- **Invariant:** disclose exactly what fields and flow shapes the illustration consumes; anything unmodeled is unsupported, not zero-effect by assumption.

## Scope

**In:** `apps/web/src/lib/simulator.ts`, new `apps/web/src/lib/simulator.test.ts`, `apps/web/src/lib/transpiler.test.ts`, `apps/web/src/App.tsx`, and the two telemetry components if required to display status; `apps/web/src/types.ts` only for an explicit illustrative/unsupported result discriminator.

**Out:** changes to Python simulation physics, creating a new WebAssembly runtime, heavy dependencies, invented graph traversal semantics, non-existent server APIs, claims of real-data market calibration or a redesigned visual canvas.

## Steps and verification

1. **Characterize current behavior with RED tests:** two audience segments, a graph with an extra branch, changed edge destination, altered conversion touchpoint, no touchpoint, and repeated identical input with `Math.random`. Demonstrate which changes the current implementation ignores. Verify: `cd apps/web && bun test` produces the expected new failing behavior tests before the fix. Preserve one existing transpiler roundtrip test.
2. **Agree the supported illustrative contract:** document in the function/type and UI which simple single-path strategy inputs are actually consumed. For unsupported graph shapes, return an explicit `unsupported`/error status rather than silently producing risk forecasts. Do not infer true behavioral meaning from arbitrary React Flow edge names. Verify: test calls to unsupported multi-audience/branch inputs assert the named status and do not present ordinary metrics.
3. **Make repeatability explicit:** accept a seed or injected RNG when a simulation is actually supported; remove direct ambient `Math.random` from the calculation path. Do not report `agents_per_trial = 10000` when the engine does not simulate that many independent agents. Either model this count correctly under the future 007 contract or omit/label it as a display input ignored by the current illustration. Verify: two runs under one input/seed have equal outputs; changed seed can alter at least one supported stochastic outcome.
4. **Expose user-visible truth:** update `App.tsx` and the telemetry result components to label `Illustrative browser estimate, not calibrated or reference-engine output` and show an unsupported-flow explanation instead of confidence-looking ROAS/CAC charts. Ensure no existing text implies Python/Web semantic parity. Verify: reviewer traces the discriminant from `simulator.ts` into each UI rendering branch.
5. **Retain graph conversion integrity:** add at least one roundtrip graph test with multiple nodes/branches that verifies topology and attributes without pretending those graph shapes are simulated. Verify: `cd apps/web && bun test` exits 0; `bun x tsc --noEmit` exits 0 if existing local typescript is available; `bun run build` exits 0 **during implementation verification**, not during this read-only advisor pass.
6. **Record compatibility boundary:** if 007 later chooses an authoritative engine/protocol, create a new versioned golden-trace parity implementation card instead of silently growing TypeScript math. Verify: the UI text and tests state its precise modeled scope.

## Done criteria

- [ ] Reproducible supported illustrative scenario with seeded draws.
- [ ] Unsupported graphs/audiences fail visibly rather than reuse misleading financial forecasts.
- [ ] No falsely reported virtual-agent population count or causal prediction claim.
- [ ] App render states align with the simulator's result discriminant.
- [ ] Bun test, TypeScript check and production build pass after code changes.
- [ ] No Python engine behavior changed; authoritative parity explicitly awaits 007.

## STOP conditions and maintenance

STOP if the only viable honest behavior would break an agreed public API, if user-facing result types cannot represent an unsupported state without broader design approval, or if graph semantics cannot be defined from the current `StrategyAST` contract. Record the gap. Any later semantic bridge must compare exact input/seed/time-horizon traces against 007, not only visually similar charts.

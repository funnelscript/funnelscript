# FunnelScript Architecture Recovery Audit and Remediation Plan

Status: BASELINE AUDIT COMPLETE; REMEDIATION UNDER OWNER REVIEW. Audit date: 2026-11-02.
Scope: local funnelscript at 156c383 (main) and funnelscript-research at 805d31b (main).
Policy: Pause feature delivery. This audit is evidence, not an autonomous authorization for source/runtime changes, deletions, merges, or compatibility decisions. The owner subsequently requested bounded remediation work; its exact branch status and verification evidence are tracked in [RECOVERY_EXECUTION.md](RECOVERY_EXECUTION.md). Separate confirmed behavior from growth risk and research uncertainty.

## 1. Verified baseline

- Both worktrees were clean on main at discovery. Each repository listed exactly one primary worktree.
- Application: uv run pytest -q => 573 passed, 58 subtests passed, exit 0.
- Research: python3 -m pytest -q => 57 passed, exit 0. The CONTRIBUTING.md documented unittest command also passed 5 tests, but it does not run every pytest-only research check. Research CI correctly runs pytest.
- Web: Bun 1.4.3, 1 test passed, exit 0. Production TypeScript/Vite build passed, exit 0. The remote shell initially lacked Bun in PATH; using the installed /Users/mamdouhaboammar/.bun/bin/bun resolved this environment issue.
- These results do not prove market predictive validity, browser/Python semantic parity, bounded memory, or live-provider safety.

## 2. Actual system map and ownership

Source-defined World path:
  .fnl text -> Lexer/Parser -> WorldAST/WorldTypeChecker -> WorldExecutor -> EventMachine
  -> typed state and processed/pending events. PopulationExecutor runs isolated agent-local Worlds with keyed RNG substreams. Marketing ledger/metrics/provenance/commit modules are opt-in domain-level Python adapters, not universal World rules.

Legacy strategy path:
  StrategyAST source/JSON -> legacy linter -> SimulationEngine -> legacy telemetry/export.
  CLI simulate still uses the legacy path; CLI run-world uses WorldExecutor.

Browser Studio path:
  TypeScript StrategyAST -> graph transpiler -> ReactFlow canvas.
  A separate runInBrowserSimulation(StrategyAST) produces synthetic financial cards without executing World semantics or graph logic_flow.

Research path:
  Accepted decisions and debates -> spec/ grammar and bounded scientific contracts -> evals/ fixtures/receipts -> tests and application conformance. Scientific calibration with legally permitted, held-out real-world data remains unproven.

Canonical ownership proposal (requires owner acceptance):
- Language semantics: research/spec plus executable app conformance tests.
- Active public behavior: app implementation/tests and versioned CLI reference.
- Architectural decisions: one canonical accepted-ADR register, with an automatically verified link/index in the other repository.
- Proposed plans: one tracked, active execution index; historical/ignored plans clearly archival.
- Marketing economics: explicit domain-owned models and ledger; not unconditional language-kernel axioms.

## 3. Findings and evidence

F-01 | P0 | CONFIRMED: Browser Studio's displayed simulation ignores graph topology and does not simulate the advertised agent count.
Evidence: apps/web/src/lib/simulator.ts:18-37 reads a subset of StrategyAST; :81-84 uses Math.random; :142 echoes agentsCount without using it to calculate. apps/web/src/App.tsx:142-149 presents this via Run Simulation; :166-170 edits edges without updating AST. Executed controlled Bun probe with constant random source: changing logic_flow and agents from 10 to 100000 yielded identical modeled metrics (ROAS mean 37.8), with only the displayed agents_per_trial field changing.
Impact: users may trust model metrics as consequences of a DAG or large agent population despite neither being calculated. Existing one Web test only covers graph transpilation.
Root boundary: browser simulator's input contract and UI result claim.
Remediation: immediately relabel/disable unsupported simulation claims or reject unsupported graphs, then choose one verified authoritative execution contract. Do not claim Python parity by adding a seed alone.

F-02 | P0 | CONFIRMED: Governing policy conflicts with an accepted architecture decision.
Evidence: app AGENTS.md section "Economic Conservation & Physical Invariants" says every simulation kernel must enforce audience conservation, spending halt and wallet constraints globally. app docs/DECISIONS.md:129-139 (DEC-009) explicitly removes these model-specific rules from universal compiler axioms; CONTRIBUTING.md and WorldExecutor maintain domain neutrality. Research AGENTS.md also instructs synchronization.
Impact: independent agents following AGENTS.md literally can reintroduce prohibited global economic rules and invalidate debt, credit, nonmarketing Worlds.
Root boundary: conflicting governance/source-of-truth, not an immediate runtime defect.
Remediation: record an accepted clarification; make AGENTS.md refer to DEC-008/009 and distinguish generic safety from optional marketing contracts. Preserve historical accepted ADR text, append dated clarifications.

F-03 | P1 | CONFIRMED: Accepted decision ledger drift across repositories.
Evidence: research DECISIONS.md includes accepted DEC-037 and its entry/section (lines 44,497); application docs/DECISIONS.md has no DEC-037. The full ledgers have diverged in length/content.
Impact: contributors cannot reliably reconstruct the same accepted grammar/semantics from both checkouts.
Root boundary: duplicated independently maintained canonical decision files without a sync gate.
Remediation: select canonical ownership; add automatic ID/status/link parity check and allow app summary/index to reference research instead of duplicating full prose.

F-04 | P1 | CONFIRMED: Active local plan drift and missing version control.
Evidence: app plans/007g-007h-post-007e-language-and-runtime-consolidation.md:11,95-97,321 still schedules Phase 007G as NOT STARTED; app main 156c383 and research main 805d31b are Phase 007G merge commits. app and research plans/NEXT_PHASES.md differ (cmp fails at line 173), and git check-ignore -v confirms /plans/ ignored in both repositories.
Impact: later agents can rerun finished work, miss dependencies, or base migrations on an out-of-date execution queue.
Root boundary: ephemeral mirrored execution plans are treated as authority after merges.
Remediation: establish one tracked current-phase index with verified merged-SHA receipts; preserve historical files as archival notes, not executable orders; cross-repo references should point to authoritative facts.

F-05 | P1 | CONFIRMED resource-contract gap, NOT a violation of the current max_events definition.
Evidence: app src/funnelscript/core/event_machine.py:91-97 eagerly enqueues every input, :103-105 bounds processed-event count, :110-117 enqueues emitted events without pending-queue cap, :125-126 retains processed/intents/pending tuples. Executed World package probe with max_events=1, 200 future events, until=0: processed 0, pending 200.
Impact: max_events is not an input/backlog/memory budget. Unexpectedly large event inputs or emissions may exhaust memory before reaching the processing guard.
Root boundary: EventMachine resource-policy contract and input/admission checks.
Remediation: design separate total-admitted, pending, emitted-per-step, processed, trace-retention and time/cancellation budgets; preserve existing event ordering and explicit failure semantics. Compare bounded in-memory calendar vs streaming/batched scheduling using workload proofs before choosing.

F-06 | P1 | CONFIRMED bounded capability / future growth risk, NOT current conformance failure.
Evidence: app src/funnelscript/runtime/world_executor.py:309-343 permits one independently runnable agent template; :355-403 iterates agents serially, retains every RunResult and optional complete trace, and has no cross-agent causal interactions. Research spec/population-identity-rng-v0.md explicitly scopes this to independent agent calendars.
Impact: a correct N=1000 experiment does not establish memory/cost at large N, shared market shocks, global constraints or massive parallel trials.
Root boundary: population execution and result-retention contracts.
Remediation: specify bounded-run, aggregate-only and full-trace result modes without breaking deterministic identity; benchmark N=1k/10k/100k and concurrent trials, RSS and latency on named hardware; defer a replacement engine until measured.

F-07 | P1 | CONFIRMED three distinct execution contracts and unsafe potential migration if performed by deletion-first.
Evidence: app src/funnelscript/cli.py:229-268 still sends simulate to SimulationEngine, and lines 259-265 say "World simulation is not implemented yet" despite run-world being available at :193-226. app plans/007g-007h...:173-255 proposes a later 007H retirement, explicitly conditioned on capability/metric replacement. Browser simulator adds a third interpretation.
Impact: confusing CLI diagnostics, incompatible report contracts and migration breakage if old paths are removed before replacement.
Root boundary: explicit source-language/CLI versioned execution contract.
Remediation: first build a capability matrix (input grammar, seed, events, agents, horizon, metrics, output schema, errors, exports, browser), independently specified migration oracles and deprecation semantics. Only delete legacy execution after defined essential behavior is proven and the owner approves the breaking boundary.

F-08 | P2 | CONFIRMED research/documentation representation drift.
Evidence: research paper/README.md:131-230 calls a StrategyFile-only grammar the "Complete & Closed Specification", while research spec/grammar.ebnf includes the newer World/import/expression language. Application language docs describe the current implemented subset.
Impact: readers and future agents may mistake a historical paper grammar for the current grammar.
Root boundary: ambiguity between working-paper historical formalism and normative language specification.
Remediation: relabel the paper section historical/scope-limited and link the canonical versioned grammar; only the research spec/ plus parser tests should define supported syntax.

F-09 | P1 scientific gate | CONFIRMED unverified target, NOT a code bug.
Evidence: research README.md "Current evidence boundary", research paper/README.md implementation notes, app README.md, app plans/008-empirical-calibration-pilot.md explicitly deny calibration and out-of-sample forecasting proof.
Impact: engineering quality cannot justify claims of campaign investment forecast accuracy.
Remediation: pre-register empirical validation protocol, metric/assumption provenance, permitted observations, time-based holdout, naive baselines, uncertainty calibration and falsification. Keep market-forecast claims blocked absent data and results.

F-10 | P2 | CONFIRMED diagnostics coverage gap.
Evidence: ParserError stores source-token line/column in parser.py, but WorldTypeError in compiler/world_ast.py:113-147 raises free-text type errors without source spans; CLI check_command uses Rich already.
Impact: extending grammar increases time to locate source errors; adding CLI formatting alone cannot reconstruct missing spans.
Root boundary: AST span and structured compiler diagnostic data model.
Remediation: introduce additive source span/error codes at parser-to-typechecker boundary, then support CLI and machine-readable outputs with contract tests.

F-11 | P2 | CONFIRMED contributor-doc verification-command mismatch.
Evidence: research CONTRIBUTING.md instructs python3 -m unittest discover -s tests -v (5 successful cases), while research CI runs pytest and fresh local python3 -m pytest -q produced 57 passed.
Impact: a contributor following the documented local verification gate can miss pytest-only research oracles.
Remediation: document the same pytest gate used by CI; retain unittest as an optional narrower documentation-link smoke.

## 4. Causal remediation sequence

R0 — Freeze and classify (no feature implementation).
- Freeze current feature/merge execution pending owner review; capture both SHAs, test commands and artifact locations.
- Classify each finding as correctness defect, contract drift, resource risk, scientific evidence gate, or intentional experimental limitation.
- Completion: accepted audit ledger with owners and a single execution queue. No "fix all" workstream.

R1 — Restore architectural authority and decision integrity (must precede language/runtime redesign).
- Resolve AGENTS vs DEC-009 conflict.
- Choose canonical accepted-ADR ownership; add parity checks and explicit proposal/accepted/implemented distinctions.
- Replace ignored mirrored current plans with one tracked, concise current-phase index. Keep old plans archival until checked, never destructively erase undocumented decisions.
- Completion: same accepted decision IDs/statuses seen from both repos; completed 007G cannot be scheduled again; CI catches a deliberately inconsistent example.

R2 — Prevent misleading browser metrics (can proceed independently after R0).
- Immediate safe mode: make browser results explicitly illustrative, or suspend numeric risk claims and unsupported graph-to-metrics relationship.
- Define supported browser graph/World semantics; build tests that change graph, audience population, seed and settings and prove changed/rejected outcomes.
- Choose between (A) browser as editor/client of authoritative World execution and (B) explicitly separate demonstration mode. Do not present mode B as semantic parity.
- Completion: public UI cannot indicate that ignored edges or unused agent counts affect results; golden fixtures and user-facing tests cover the contract.

R3 — Specify bounded execution and reproducible scale (after R1 contract freeze).
- Independent resource limits: queue admission, emitted events, processed events, wall time/cancellation, result retention and memory.
- Preserve time/priority/insertion ordering and per-agent keyed RNG. Measure 1k/10k/100k events, 1k/10k/100k independently modeled agents, concurrent trials, elapsed time and RSS; include adverse event explosions and failure semantics.
- Compare bounded heap plus aggregate summaries against streaming or chunked execution; implement only the winning measured, contract-preserving design.
- Completion: published benchmark methodology and CI or reproducible non-flaky regression bounds; resource failure is explicit, predictable and does not silently truncate results.

R4 — Decide World-first convergence, not deletion-first (after R1 and R3).
- Map all accepted legacy capability and report contracts to authoritative World semantics or explicitly retired behavior.
- Version output schemas and migration rules; preserve independent golden oracles and installed-CLI tests.
- Implement/report behavioral replacements through reviewed incremental PRs; retire legacy only after owner-authorized semantic break and reliable migration evidence.
- Completion: exactly one authoritative source-defined simulation contract for claims; Browser and CLI either use it or clearly identify their narrower mode.

R5 — Evidence and product trust (parallel scientific research, no unsupported forecast claims).
- Validate reference economics independently of implementation and against realistic stress cases.
- Obtain lawful data-owner authorization, define cohorts and outcomes, pre-register temporal holdout and baseline comparison, record uncertain or failed hypotheses.
- Completion: qualified predictive claims only after out-of-sample evidence; otherwise market prediction remains explicitly not validated.

R6 — Developer interfaces after R1/R4 boundaries.
- Structured compiler spans, stable package API for Python-to-FunnelScript, versioned playbooks and deterministic golden examples.
- Completion: external consumer contract tests and no arbitrary Python callbacks exposed inside untrusted .fnl.

## 5. Recovery dependency graph

R0 -> R1 -> R3 -> R4 -> R6.
R0 -> R2 (immediate truthful UI boundary); R2 must reconcile with R4 before authoritative browser claims.
R1 -> R5 (research protocol can progress without implementing World migration).
No JIT, RPython port, arbitrary Python FFI, new execution engine, Live provider adapter or autonomous optimization is implied by this audit.

## 6. Acceptance and rollback controls

- Each implementation slice: approved research anchor/hypothesis, explicit public old/new contract, owner, negative tests, unaffected conformance oracles, focused diff, independent review, both repository CI evidence where applicable, and rollback procedure.
- Architecture choices require at least two materially different designs and a falsifier; a single design is not auto-approved because a plan says so.
- Stop conditions: unexplained divergence in accepted ADRs, incomplete or misleading browser metric contract, weakened test oracle, unbounded resource consequence without a policy, external data/provider writes without authorization, or legacy deletion before required behavior replacement.
- All scientific, user, and marketing claims must distinguish software correctness, modeled accounting validity and held-out market validity.
- This draft is analysis, not an accepted ADR, commit, release, or authorization to change runtime contracts.

## 7. Implementation checkpoint and unresolved owner decisions

On 2026-11-02, the owner requested work against this audit. Initial, reversible R1/R2 containment was implemented on separate local application and research remediation branches with new negative tests. See [the tracked current execution index](RECOVERY_EXECUTION.md) for exact status and local evidence; this historical audit's F-01 through F-11 findings remain baseline observations.

Owner review is still required to choose canonical accepted-ADR ownership, a cross-repository parity enforcement mechanism, the future authoritative Web Studio execution boundary, and resource/admission contracts. The present browser mode is only a clearly labeled, bounded single-path illustration; the existing default sample's conditional graph is explicitly unsupported. No merges, automatic cleanup, legacy removal, new predictive claims or release were authorized or performed.

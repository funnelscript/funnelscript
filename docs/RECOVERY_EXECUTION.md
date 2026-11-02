# FunnelScript Architecture Recovery: Current Execution Index

Updated: 2026-11-02. This is the **tracked current-phase index**. See
[ARCHITECTURE_RECOVERY_AUDIT.md](ARCHITECTURE_RECOVERY_AUDIT.md) for evidence, causal findings,
dependencies and acceptance gates. Historical local `plans/` drafts remain archival and
are not authoritative task status. Feature development remains paused for recovery.

## Baseline and worktrees

| Repository | Baseline main | Local remediation branch |
| --- | --- | --- |
| Application | `156c383` | `remediation/architecture-recovery-r1-r2` |
| Research | `805d31b` | `remediation/architecture-recovery-r1-docs` |

Phase 007G: **merged in both default branches**. Phase 007H: **not started**.
No legacy/runtime removal is authorized by this index. Do not reschedule completed 007G.

## Recovery stages

| Stage | State | Evidence / remaining gate |
| --- | --- | --- |
| R0: Audit baseline | Recorded; owner review ongoing | Audit F-01 through F-11 and baseline test commands |
| R1: Decision and plan authority | **Partial; research-owned direction selected** | AGENTS/DEC-009 aligned; 37 index rows agree across remediation branches; eight parity tests and a standard-library cross-repo validator now pass locally. Research PR #7 merged the index repair into research/main (2b5b08f). Application CI now checks the accepted-decision index against live research/main on pull requests and pushes; the [first live CI run](https://github.com/funnelscript/funnelscript/actions/runs/41441760351) passed the ADR parity, Python/wheel and Bun jobs. DEC-034 historical body wording differs intentionally. Formal governance ADR not yet accepted |
| R2: Honest Web Studio preview | **Containment implemented, pending review** | Browser discriminates unsupported vs illustrative; deterministic seed; no agent-count claim; unsupported default conditional graph has no metrics; 9 new negative/contract tests |
| R3: Resource bounds and scale | **Proposed; no runtime code changed** | Research `spec/runtime-resource-envelope-v0.md` defines separate admission, retention and replay gates; `evals/runtime-resource-baseline-2026-11-02.md` records the 100k pending-event counterexample. Implementation still blocked on accepted contract and R1 |
| R4: Runtime convergence | **Blocked on R1/R3** | World-first compatibility map and migration gates; no legacy deletion |
| R5: Empirical product validity | **Not started** | Lawful datasets, independent baselines and preregistered out-of-sample protocol |
| R6: Developer interface stability | **Blocked on R1/R4** | Versioned spans, Python API and executable examples |

## Current software evidence (application remediation branch; research recovery merged to main)

- Baseline: app `uv run pytest -q`: 573 passed, 58 subtests; research `python3 -m pytest -q`: 57 passed; web Bun: 1 passed.
- R2 red phase: eight initial browser tests failed before the code fix; the ninth malformed-AST guard test also failed RED, including unsupported branch, multi-audience, stale graph and non-determinism.
- R2 first green phase: 10 Bun tests passed, `bun x tsc --noEmit` passed, `bun run build` passed.
- Initial Python suites after the browser fix: app 573 passed, 58 subtests; research 57 passed.
- Final local regression after all source changes: app `uv run pytest -q`: **574 passed, 58 subtests**; research `python3 -m pytest -q`: **58 passed**; Bun: **10 passed**; `bun x tsc --noEmit` passed; `bun run build` passed. Historical baseline counts above are unchanged.
- 2026-11-02 follow-on: 8 added parity tests passed; application full suite **582 passed, 58 subtests**; research full suite **58 passed**. The cross-repository checker returned `ADR parity OK: 37 indexed decisions` against the research remediation branch. Before Research PR #7 merged, it correctly rejected the then-current `research/main` because DEC-031 through DEC-036 were not indexed there. The new cross-repository CI job passed its first GitHub execution in application [run 41441760351](https://github.com/funnelscript/funnelscript/actions/runs/41441760351), together with Python/wheel and Bun jobs.
- R3 read-only measurements: 100k future events under `max_events=1` produced 0 processed, 100k pending, 22,126,740 traced peak bytes; one-event 100k fan-out produced 1 processed, 100k pending, 22,929,240 traced peak bytes. Single-run CPython 3.12/arm64 diagnostics, not hard RSS guarantees.
- Passing code tests do **not** validate financial forecasts, Python/browser parity or effective handling of 100k agents.

## Owner decisions before later stages

1. Canonical accepted-ADR register: research-owned is the working direction. The application retains its historical ledger, including the intentionally different DEC-034 prose. The local parity validator checks accepted index IDs, titles, dates and statuses, not detailed body equivalence. Its CI gate compares the application ledger to the research default branch, and formal ownership still needs an accepted ADR.
2. Future Web Studio semantics: keep an explicitly illustrative browser mode, or make the browser an editor/client for authoritative versioned World execution. Current preview intentionally supports only one direct audience→paid→conversion path; the sample conditional graph is unsupported.
3. Resource limits and compatibility: review the proposed independent queue/history/intent caps, exact nonbinding equivalence and typed failure semantics before implementation. Approve World migration criteria separately; no existing runtime limits or legacy API have changed.

## Rollback boundary

The research index repair is merged on research/main; application source and CI remediation remain isolated on the application remediation branch. Keep diffs reviewable, merge only after accepted contracts and regression checks, and delete merged branches/worktrees only after checking for untracked local work. Preserve the unrelated uncommitted changes on the research/main checkout. Do not auto-merge or auto-delete based on CI green alone.

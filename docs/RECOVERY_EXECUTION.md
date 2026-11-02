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
| R1: Decision and plan authority | **Partial** | AGENTS/DEC-009 aligned; DEC-037 mirrored; all 37 index rows locally compared equal; local index tests added; canonical ADR ownership and *cross-repository* CI parity still require owner choice |
| R2: Honest Web Studio preview | **Containment implemented, pending review** | Browser discriminates unsupported vs illustrative; deterministic seed; no agent-count claim; unsupported default conditional graph has no metrics; 9 new negative/contract tests |
| R3: Resource bounds and scale | **Blocked on R1 contract** | Specify queue admission, runtime/result retention and benchmark falsifiers before changing EventMachine |
| R4: Runtime convergence | **Blocked on R1/R3** | World-first compatibility map and migration gates; no legacy deletion |
| R5: Empirical product validity | **Not started** | Lawful datasets, independent baselines and preregistered out-of-sample protocol |
| R6: Developer interface stability | **Blocked on R1/R4** | Versioned spans, Python API and executable examples |

## Current software evidence (local branches, not default branch)

- Baseline: app `uv run pytest -q`: 573 passed, 58 subtests; research `python3 -m pytest -q`: 57 passed; web Bun: 1 passed.
- R2 red phase: eight initial browser tests failed before the code fix; the ninth malformed-AST guard test also failed RED, including unsupported branch, multi-audience, stale graph and non-determinism.
- R2 first green phase: 10 Bun tests passed, `bun x tsc --noEmit` passed, `bun run build` passed.
- Initial Python suites after the browser fix: app 573 passed, 58 subtests; research 57 passed.
- Final local regression after all source changes: app `uv run pytest -q`: **574 passed, 58 subtests**; research `python3 -m pytest -q`: **58 passed**; Bun: **10 passed**; `bun x tsc --noEmit` passed; `bun run build` passed. Historical baseline counts above are unchanged.
- Passing code tests do **not** validate financial forecasts, Python/browser parity or effective handling of 100k agents.

## Owner decisions before later stages

1. Canonical accepted-ADR register: research-owned with app-generated mirror, or another reviewed authority and automated parity mechanism. Current mirrored records are **not** a resolved authority policy.
2. Future Web Studio semantics: keep an explicitly illustrative browser mode, or make the browser an editor/client for authoritative versioned World execution. Current preview intentionally supports only one direct audience→paid→conversion path; the sample conditional graph is unsupported.
3. Resource limits and compatibility: approve a versioned admission/error/retention contract and legacy-to-World migration criteria before runtime changes or deletions.

## Rollback boundary

All changes are isolated to local remediation branches. Keep their diffs reviewable, merge only after accepted contracts and regression checks, and delete merged branches/worktrees only after checking for untracked local work. Do not auto-merge or auto-delete based on CI green alone.

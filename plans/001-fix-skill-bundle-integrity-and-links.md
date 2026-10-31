# Plan 001: Complete the In-Progress Skill Bundle Integrity Repair

> Executor: this is a **reconciliation** card, not a fresh cleanup. Inspect the already staged renames/deletion and untracked academic-paper reference before changing anything. Never reset or recreate the existing user edits. Follow the source skill-bundle research contract and stop on a mismatch.
>
> Drift check (both repositories): `git status --short -- agents/skills/ agents/README.md tests/test_skill_bundle.py` and `git diff 41f00f1 -- agents/skills/ agents/README.md tests/test_skill_bundle.py` in the application, `git diff abe561f -- agents/skills/ agents/README.md tests/test_skill_bundle.py` in research. Compare staged and untracked state explicitly; `git diff SHA..HEAD` alone misses it.

## Status

- **Priority:** P1
- **Effort:** S
- **Risk:** LOW, if existing staged work is preserved
- **Depends on:** none
- **Category:** bug / DX
- **Planned at:** application `41f00f1`; research `abe561f`; reassessed 2026-10-31
- **Status:** DONE (verified 2026-10-31 in both repositories)

## Why this matters

Four skill directory renames and removal of a redundant archive have already been staged in both repos. The latest full test runs each failed one subtest in the same place: the academic-paper entrypoint points to `../shared/output_language_pair.md`, which does not exist in the bundled skill root. Meanwhile an untracked language-pair registry now exists under `agents/skills/academic-paper/references/`. Repeating the cleanup would risk overwriting the maintainer's ongoing work. The next action is precise link and registry conformance, then independent verification.

## Current state and research anchor

- `agents/skills/academic-paper/SKILL.md:622` contains `[shared/output_language_pair.md](../shared/output_language_pair.md)`. From `academic-paper/` it resolves to a missing sibling `agents/skills/shared/output_language_pair.md`.
- `agents/skills/academic-paper/references/output_language_pair.md` already exists as an **untracked** file in each repository. Its own link to `../academic-paper/references/abstract_writing_guide.md` appears to resolve incorrectly from its location; verify and correct the smallest possible reference, if necessary.
- Four `literature_search_*` directories were staged for Git renames to matching `literature-search-*` names. `agents/skills/j-space/Archive.zip` deletion is staged. `agents/README.md` has local changes.
- `tests/test_skill_bundle.py` exists as an untracked conformance test. Research `spec/skill-bundle-v0.md` and `evals/skill-bundle-v0.md` also exist as untracked material; preserve, don't regenerate.
- Research H-B1 through H-B4 and DEC-035 govern the 22-skill primary entrypoint set. Vendor shared files outside this bundle are not implied to be fully available.
- Pre-repair app `uv run pytest -q`: **218 passed, 1 failed**. Research `python3 -m unittest discover -s tests -v`: **3 passed, 1 failed**. The one failed subtest in both is `academic-paper` line 622.
- **H-B2:** every concrete local skill entrypoint link resolves to a shipped file. Falsifier: any `destination.is_file()` failure.
- **Invariant:** primary entrypoint count/names equal index and `name` frontmatter; no deleted script or missing reference from the name cleanup.

## Scope

**In:** existing staged moves/deletion for four literature search skill directories and J-Space archive (verification only); `agents/skills/academic-paper/SKILL.md`; `agents/skills/academic-paper/references/output_language_pair.md`; `agents/README.md` only for factual index correction; existing `tests/test_skill_bundle.py` only to fix a real test defect. Same exact paths in both repos. Research `evals/skill-bundle-v0.md` can receive a fresh test receipt.

**Out:** source language/runtime, any other vendor skill logic, wholesale replacement of skill directories, indiscriminate deletion of ZIPs, generated Rust artifacts, new dependencies or upstream network installs.

## Steps and verification

1. **Inspect existing work, do not repeat it:** run `git status --short -- agents/skills/ agents/README.md` in each repo. Check all four target directories and all 22 SKILL entrypoints. Expected: staged renames/removal remain intact; no unplanned delete. If another process is actively editing the same files, STOP.
2. **Fix the actual entrypoint link:** change only the referenced target in `agents/skills/academic-paper/SKILL.md:622` to `references/output_language_pair.md`, relative to the SKILL file. Confirm the referenced registry exists, preserves the intended default, and links to `abstract_writing_guide.md` with a path valid from its own directory. The registry already exists; do not duplicate it under another tree.
3. **Run focused contract tests:** application `uv run pytest tests/test_skill_bundle.py -v` expected exit 0 with all tests/subtests passing; research `python3 -m unittest discover -s tests -v` expected exit 0 with 4 top-level tests. Record actual totals, not old expected counts.
4. **Run application full suite:** `uv run pytest -q` expected exit 0. The pre-repair baseline had one failure; the final GREEN receipt appears below. Ensure `git status --short` has no unrelated changes introduced by this card.
5. **Synchronize the existing evidence, not fictional success:** update research `evals/skill-bundle-v0.md` with commands and results if currently stale. The implementation executor should reconcile the existing research trilogy, app `docs/MASTER_PLAN.md`, and `failure-lessons/` if their completion claims contradict observed test state, without overwriting concurrent user writing.

## Test plan and done criteria

- [x] Entry point and its registry-relative links resolve in both checkouts.
- [x] 22 primary skill names still match directory slugs and index.
- [x] No redundant archive left inside the extracted skill; no required source removed.
- [x] Both focused and full suites pass with fresh receipts.
- [x] The previous staged/untracked changes have been preserved and reviewed.
- [x] `plans/README.md` records DONE after verification.

**Completion evidence (2026-10-31):** The initial fresh regression still failed on `academic-paper/SKILL.md:622` in both checkouts. Correcting its target to `references/output_language_pair.md` and the registry's internal link to `abstract_writing_guide.md` produced application `uv run pytest tests/test_skill_bundle.py -v`: **4 passed, 58 subtests passed**; full `uv run pytest -q`: **219 passed, 58 subtests passed**; research `python3 -m unittest discover -s tests -v`: **5 passed**. `apps/web` `bun test`: **1 passed**. No test assertion was changed. These are local checkout receipts, not independent agent-pipeline verification.

## STOP conditions and maintenance

STOP if a named skill count differs from 22, the new registry content is absent/corrupt, a source was unexpectedly removed, or the relevant staged changes were authored concurrently and cannot be safely reconciled. Do not suppress the failing assertion or move registry files to make a weak test pass. Future vendor updates must re-run the link/name conformance suite.

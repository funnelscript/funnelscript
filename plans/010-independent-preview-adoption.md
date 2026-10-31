# Plan 010: Verify Independent Developer Adoption of the Experimental Preview

> Executor: keep this scoped to trustworthy onboarding, packaging checks and feedback. Do not publish PyPI artifacts, create GitHub releases, push tags or make stability promises without separate owner approval.
>
> Drift preflight: in the application run `git status --short -- docs/ README.md CONTRIBUTING.md tests/ .github/ pyproject.toml`; inspect `git diff 41f00f1 -- docs/ README.md CONTRIBUTING.md tests/ .github/ pyproject.toml` and untracked files. Research base is `abe561f`. Do not discard concurrent user changes.

## Status

- **Priority:** P2
- **Effort:** M
- **Risk:** LOW for documentation/tests, higher for any separate publication decision
- **Depends on:** 001, 002, 003, 005 and 006 for a refreshed candidate; 007/008 are **not** required for an expressly experimental language preview
- **Category:** dx / docs / release evidence
- **Planned at:** application `41f00f1`, research `abe561f`, 2026-10-31
- **Status:** TODO

## Why this matters

The public tag `v0.2.0a1` was independently installed and tested, but a contributor's clean first-run experience is not yet measured and `plans/001` currently blocks a green local source suite. A credible next preview needs honest docs, reproducible artifacts and failure reports from outside the maintainer's checkout, not an invented confidence score.

## Observed state and hypothesis

- `pyproject.toml`: Python `>=3.12`, `funnelscript` entrypoint and `stdlib/marketing/*.fnl` package data.
- `docs/EXPERIMENTAL_PREVIEW.md`: real Git-source install/starter/check/run-world path, plus local module tutorial.
- `docs/PUBLIC_PREVIEW_READINESS.md`: scoped experimental announcement, explicitly not empirical market validity.
- `.github/workflows/preview-ci.yml`: pinned Python/wheel and Bun/frontend workflow; historical tag CI attestation lives in research `evals/developer-preview-v0.md`.
- Existing `tests/test_preview_quickstart.py` and `tests/test_documentation_links.py`.
- **H-AD1:** an independent Python 3.12+ user can install an exact source tag/commit and run the public tutorial without files from the source checkout. Falsifier: hidden local-path/module dependencies.
- **H-AD2:** two previously uninvolved developers can complete the starter and one module customization without undocumented prompts or repository-specific environment state. Falsifier: a reproducible first-run blocker.
- **Invariant:** installed package version, source SHA and documented commands identify the same artifact; existing file bytes are not overwritten by `init-world`.

## Scope

**In:** application `docs/EXPERIMENTAL_PREVIEW.md`, `docs/PUBLIC_PREVIEW_READINESS.md`, `tests/test_preview_quickstart.py` and focused contributor onboarding details in `CONTRIBUTING.md` if verified wrong; research `evals/developer-preview-v0.md` for new observed adoption receipts.

**Out:** changes to simulation math, public CLI breaking behavior, new required dependencies, PyPI/GitHub Release publishing, changing the old `v0.2.0a1` tag, external marketing integrations or unvalidated forecast claims.

## Execution and checks

1. **Freeze the tested candidate identity:** record `git rev-parse HEAD`, `uv run funnelscript --version`, `git status --short`, and workflow/tag state. Do not claim a pending release passed historical CI. Verify: release evidence names the exact SHA and version.
2. **Run existing suite and clean-install checks:** `uv run pytest -q`; `cd apps/web && bun test`. In a disposable clean environment only, perform the documented `uvx --from git+https://github.com/funnelscript/funnelscript@v0.2.0a1 funnelscript --version` check and the `init-world`, `check`, `run-world` example. Verify: exit 0, correct seed-specific state, no reference to maintainer's checkout. Do not rebuild or install into the advisor's live tree.
3. **Test controlled failure behavior:** existing-file non-overwrite, invalid extension, missing module, invalid event payload and offline/network-install guidance. Add tests only if a concrete missing regression is found. Verify: `uv run pytest tests/test_preview_quickstart.py -v`, with named negative behaviors.
4. **Recruit external first-run feedback:** ask two non-maintainer contributors to follow the exact docs; record consented anonymous time-to-first-model, command failures, confusion points and reproduction environment. If no participants, label the user-study gate PENDING, not PASS. Verify: two independent observation receipts, not synthesized personas.
5. **Decide next release scope:** document what an experimental programming language legitimately enables and exactly what it does not promise. Require fresh CI on the chosen candidate SHA. A future tag, GitHub Release or PyPI push needs independent owner authorization. Verify: no assertion of `PyPI available`, calibrated forecasts or Live capability without matching evidence.

## Done criteria

- [ ] All application/research and Web focused verification gates passed against the final candidate.
- [ ] Clean out-of-checkout install and starter checked on a pinned source identity.
- [ ] Two independent feedback receipts or explicit **PENDING** status.
- [ ] Truthful changelog/onboarding and no source paths, credentials or production claims.
- [ ] No external publication performed without owner approval.

## STOP and maintenance

STOP if tests are still failing from 001, the version SHA mismatches documentation, the environment cannot support a clean install, or distribution requires credentials. Do not modify `v0.2.0a1` retroactively; new behavior requires a distinct future version chosen by the maintainer.

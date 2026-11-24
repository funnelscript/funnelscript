# Failure Lesson: Multi-Repository Umbrella Directory vs Monorepo Tooling Execution Leakage (FL-025)

## Context
The top-level workspace directory `/Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect` is an umbrella container directory serving seven distinct, decoupled Git repositories: `funnelscript`, `fpm`, `fpm-registry`, `funnelscript-studio`, `Business-Foundry`, `funnelscript-research-doc`, and `.github`.

## What happened
Automated test runners, linters, and external file operations were invoked without explicit working directory (`cwd`) scoping to the target child repository. As a consequence, `.pytest_cache`, `.ruff_cache`, and OS metadata files (`.DS_Store`) were created directly in the parent directory. Furthermore, an 11.5 MB video asset (`Introducing Higgsfield MCP 2.0...mp4`) and nine strategic orchestration prompts were placed loosely in the root rather than in dedicated subsystem or asset folders.

## Observable symptom
Running `git status` from the workspace root failed with:
`fatal: not a git repository (or any of the parent directories): .git`
Meanwhile, directory listings showed root clutter mixed with child repository folders, making automated git hygiene checks ambiguous.

## Impact
- Unscoped test executions created orphan cache files that escaped `.gitignore` rules of child repositories.
- An 11.5 MB video binary created unnecessary disk consumption and risked accidental addition into Git history.
- Root clutter hindered automated repository detection by AI agents and CLI tools.

## Incorrect assumption
The agent implicitly assumed the parent folder was a monorepo or that child repository configurations applied recursively upward to parent directories.

## Root cause
Confirmed. The parent workspace directory is not a Git repository. Running CLI commands without ensuring the process `cwd` matches a child repository root causes outputs, caches, and scratch files to spill into the parent directory where no `.gitignore` is active.

## Why the architecture allowed it
The project lacked an enforced physical check verifying that the current working directory contains a `.git` folder prior to executing tools like `pytest`, `ruff`, or `git`.

## Fix
1. Explicitly mapped all 7 child repositories and ensured all future commands pass `-C <repo>` or execute from child directories.
2. Verified binary identity of the 11.5 MB video against `promo-film/analysis/source.mp4` using `cmp` and removed the duplicate from the root.
3. Purged `.pytest_cache` and `.ruff_cache` from the parent directory.
4. Created a dedicated `plans/` directory to cleanly hold all orchestrator prompts, research audits, and readiness roadmaps.

## Verification
Executed `ls -la` in the root workspace confirming only child repository directories, `plans/`, `promo-film/`, and `README.md` remain. Verified `git -C <repo> status` cleanly across all 7 repositories.

## Prevention rule
All automated test, lint, and version control commands must strictly execute within the specific repository root directory (`cwd`); the parent workspace directory must never host transient execution caches or loose files outside of child repositories, `plans/`, and `README.md`.

## Reusable lesson
When developing in multi-repo workspaces (as opposed to Git submodules or monorepos), tooling must always be hermetically scoped to the target repo boundary.

## Related code
- `/Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/README.md`
- `plans/`

## Related tests
`gate0_repo_hygiene_status` executed across all 7 repository directories.

## Status
Resolved.

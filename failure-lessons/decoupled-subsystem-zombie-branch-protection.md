# Failure Lesson: Decoupled Subsystem Leaving Zombie Required Status Check Lock in GitHub Branch Protection (FL-028)

## Context
FunnelScript originally maintained a monorepo structure containing both Python backend runtime and React/TypeScript web application (`FunnelScript Studio`). When the Studio frontend was decoupled and migrated into its own dedicated repository (`funnelscript-studio`), its corresponding CI job was removed from `preview-ci.yml`.

## What happened
Upon completing all code changes and achieving 100% green tests in Pull Request #21 on `funnelscript/funnelscript`, attempting to merge the pull request via `gh pr merge --admin` failed with a GitHub GraphQL error.

## Observable symptom
GitHub CLI returned the following error:
`GraphQL: Required status check "Bun frontend tests and build" is expected. (mergePullRequest)`
Meanwhile, the PR checks interface showed all active checks (`Python tests and installed wheel`) were 100% green.

## Impact
All pull requests into the `main` branch were completely blocked from merging, deadlocking releases despite all current CI workflows passing.

## Incorrect assumption
The engineering team assumed that removing a job from a GitHub Actions workflow YAML file automatically updates or removes that job from GitHub repository branch protection rules.

## Root cause
Confirmed. GitHub branch protection rules maintain an independent, persistent list of required status check contexts (`required_status_checks.contexts`). When a CI job (`"Bun frontend tests and build"`) is deleted from workflow files, GitHub does not automatically purge it from branch protection settings. The branch continues to require a status check with that exact string identifier, but because no workflow emits it, the requirement can never be fulfilled.

## Why the architecture allowed it
Branch protection configurations are stored in remote GitHub repository settings and are decoupled from version-controlled workflow YAML files in the repository.

## Fix
Queried the GitHub API for active branch protection contexts:
`gh api repos/funnelscript/funnelscript/branches/main/protection/required_status_checks`
Identified the zombie context (`"Bun frontend tests and build"`) and executed a deletion request:
```bash
gh api --method DELETE repos/funnelscript/funnelscript/branches/main/protection/required_status_checks/contexts \
  --input - <<< '["Bun frontend tests and build"]'
```
This left only the active `"Python tests and installed wheel"` context in the required check list. The PR was immediately unblocked and merged cleanly.

## Verification
Executed `gh pr merge 21 --repo funnelscript/funnelscript --merge --delete-branch`, resulting in successful fast-forward merge and automatic branch deletion.

## Prevention rule
When removing CI workflow jobs, retiring obsolete status checks, or decomposing a repository into sub-repositories, engineers must immediately audit and update remote GitHub branch protection contexts in the same release pass to prevent zombie check deadlocks.

## Reusable lesson
Repository settings on hosted Git platforms (GitHub, GitLab, Bitbucket) frequently outlive workflow file modifications; decoupling repositories requires auditing both code-level CI files and administrative branch protection rules.

## Related code
- `.github/workflows/preview-ci.yml`
- GitHub branch protection API endpoint: `/repos/{owner}/{repo}/branches/main/protection`

## Related tests
- `gh api repos/funnelscript/funnelscript/branches/main/protection`
- `gh pr merge` automated validation

## Status
Resolved.

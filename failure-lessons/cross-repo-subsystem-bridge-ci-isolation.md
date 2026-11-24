# Failure Lesson: Subsystem CLI Bridge Assuming Monorepo Sibling Layout in Isolated CI Runners (FL-027)

## Context
The FunnelScript command-line interface provides an integrated sub-command (`funnelscript fpm <args>`) implemented in `src/funnelscript/cli.py` (`fpm_command`) that delegates to the Funnel Package Manager (`fpm`). Verification is performed via `tests/test_cli_fpm.py`.

## What happened
In local multi-repo development, `fpm` is present in the sibling directory `../fpm` and in development virtual environments. However, in GitHub Actions CI for the `funnelscript/funnelscript` repository, only the single `funnelscript` repository is cloned. Consequently, `fpm` is not installed as a binary in the CI runner's system `PATH`, nor is `../fpm` present on disk. During CI test execution, `test_cli_fpm.py` failed with an assertion error.

## Observable symptom
GitHub Actions CI test logs displayed:
`FAILED tests/test_cli_fpm.py::test_cli_fpm_command_help - assert 1 == 0`
`FAILED tests/test_cli_fpm.py::test_cli_fpm_command_init_scaffold - assert 1 == 0`

## Impact
The test suite failed in standard, isolated single-repository checkouts, breaking CI pipelines for external contributors who clone only `funnelscript` rather than the entire multi-repo workspace.

## Incorrect assumption
The test author assumed that `fpm` would always be available in the test execution environment, conflating a multi-repo local workspace layout with an isolated single-repo CI environment.

## Root cause
Confirmed. `fpm_command` correctly returns exit code 1 and prints an informative diagnostic panel (`❌ fpm (Funnel Package Manager) executable not found`) when the `fpm` executable cannot be resolved. However, `test_cli_fpm.py` unconditionally asserted `code == 0`, failing to account for environments where `fpm` is absent.

## Why the architecture allowed it
The test lacked an environment capability check and failed to test the failure-closed fallback branch of the CLI bridge.

## Fix
Refactored `tests/test_cli_fpm.py` to introduce an environment detection helper:
```python
def _is_fpm_available() -> bool:
    if shutil.which("fpm") is not None:
        return True
    candidate_dirs = [
        Path(__file__).resolve().parents[2] / "fpm",
        Path(__file__).resolve().parents[3] / "fpm",
        Path.cwd().parent / "fpm",
        Path.cwd() / "fpm",
    ]
    for cand in candidate_dirs:
        if (cand / ".venv/bin/fpm").is_file() or (cand / "src/fpm").is_dir():
            return True
    return importlib.util.find_spec("fpm") is not None
```
When `_is_fpm_available()` returns `True`, tests verify code 0 and artifact generation. When `False` (as in isolated CI runners), tests assert code 1 and verify that the diagnostic advice banner is displayed cleanly without unhandled exceptions.

## Verification
Tested both scenarios:
1. In full multi-repo environment with `../fpm` present: all tests passed with code 0.
2. In isolated container without `fpm`: tests passed with code 1 and verified diagnostic message.
3. Verified full green suite (1,191 passed) on GitHub Actions CI runner (run #45375003504).

## Prevention rule
Integration tests bridging sibling repositories or optional toolchains must explicitly test both capability-present and capability-absent branches, asserting proper exit codes and diagnostic messaging when external binaries are not provisioned in standalone CI runners.

## Reusable lesson
Never write unit tests for CLI wrappers that unconditionally expect external sibling CLI tools to be installed unless those tools are declared as hard build dependencies in `pyproject.toml` or `package.json`.

## Related code
- `src/funnelscript/cli.py`: `fpm_command(args)`
- `tests/test_cli_fpm.py`

## Related tests
- `tests/test_cli_fpm.py::test_cli_fpm_command_help`
- `tests/test_cli_fpm.py::test_cli_fpm_command_init_scaffold`
- `tests/test_cli_fpm.py::test_cli_fpm_command_verify_on_invalid_pkg`

## Status
Resolved.

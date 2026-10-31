# Plan 002: Harden CLI Error Classification, Event Input Bounds and Export Failures

> Executor: follow the source-grounded error contract; write regression tests before behavior changes. Preserve valid user-selected output paths. Do not treat arbitrary local absolute paths as path traversal.
>
> Drift preflight: `git status --short -- src/funnelscript/cli.py tests/test_cli.py` and `git diff 41f00f1 -- src/funnelscript/cli.py tests/test_cli.py`, including staged/untracked changes. Stop if the quoted code no longer matches.

## Status

- **Priority:** P1
- **Effort:** M
- **Risk:** MED, because CLI exit/diagnostic changes affect scripts
- **Depends on:** 001's clean baseline
- **Category:** correctness / security-boundary hardening
- **Planned at:** application `41f00f1`, reassessed 2026-10-31
- **Status:** TODO

## Why this matters

`check_command` and `simulate_command` catch every `Exception` while parsing, so internal programmer errors can be silently reclassified as invalid user input. JSON `--event` input currently has no explicit byte-size policy. Export failures should be clearly classified without refusing legitimate destinations chosen by a CLI user. These are diagnostics and input-contract issues, not evidence of remote exploitation.

## Current state, evidence and hypothesis

- `src/funnelscript/cli.py:58-64`: `try: ast = Parser.from_file(...); except Exception as e:` prints `Parse Error` and returns 1.
- `src/funnelscript/cli.py:215-221`: the `simulate_command` parse path has the same broad catch.
- `src/funnelscript/cli.py:138-158`: `_parse_world_input_event` calls `json.loads(spec, object_pairs_hook=_unique_json_object)`; it rejects extra top-level keys but does not check an explicit input byte limit before parsing.
- `src/funnelscript/core/event_machine.py:24-35`: `Event.__post_init__` **already rejects** non-numeric, non-finite and negative timestamps. Do not add a contradictory second rule or an arbitrary `1e9` upper bound.
- `src/funnelscript/cli.py:226-239`: export delegates to `export_trials_to_csv` and `export_report_to_json` without a scoped filesystem error message.
- `tests/test_cli.py` is the existing CLI test pattern. Exit semantics: success 0, validation failure 1, missing-file I/O 2 (verify any undocumented cases against actual commands).
- **H-CLI1:** a parser contract error remains a controlled CLI exit, while an unexpected `AttributeError` is never mislabeled as a parse error. Falsifier: injected internal fault yields `Parse Error` and exit 1.
- **H-CLI2:** over-limit JSON event strings are rejected before JSON decoding; invalid typed/time records remain rejected. Falsifier: decoder invoked first or a valid documented event rejected.
- **H-CLI3:** an unwritable export destination produces a named I/O diagnostic and nonzero exit without altering unrelated files.
- **Invariant:** parser failure and programmer failure are different classes; preserve intentional paths and documented output format.

## Scope

**In:** `src/funnelscript/cli.py`, `tests/test_cli.py`; optionally `docs/CLI_REFERENCE.md` if new documented limits/exit-code behavior must be recorded, subject to explicit reviewer agreement.

**Out:** parser grammar, EventMachine time invariants, engine math, arbitrary path sandboxing, input recursion framework dependencies and changes to normal successful output.

## Steps and independent verification

1. **Research and characterize:** record exception taxonomy, existing CLI outputs and a falsifiable diagnostic test in the execution note. Check which domain errors `Parser.from_file` can actually raise. Test with a real invalid World before modifying catch clauses. Verify: `uv run pytest tests/test_cli.py -v` baseline outcome is recorded after 001 is green.
2. **Write RED tests:** mock `Parser.from_file` to throw an unexpected `AttributeError` in each entrypoint; assert it is not converted to the user syntax panel. Assert known `LexerError`/`ParserError` still get controlled status. Verify: `uv run pytest tests/test_cli.py -k 'parse or unexpected' -v`, expected regression failure before changing code.
3. **Replace two broad catches** with the actual known domain exceptions (e.g. `LexerError`, `ParserError`, relevant schema/validation errors), plus an explicitly separate `OSError` path where appropriate. Unexpected internal faults should propagate or become a distinct internal-error status with preserved trace to stderr; they must not be represented as syntax mistakes. Verify: focused tests exit 0.
4. **Bound event JSON before decode:** use an explicitly documented maximum encoded input size, provisionally 64 KiB, measured as bytes; reject over-limit strings with `ValueError`. Keep Event time validation delegated to `Event`. Add non-object/duplicate/extra-fields and valid documented payload tests. If nested resource abuse is empirically reproducible, introduce a small bounded depth check with tests; do not hand-roll a generic JSON parser. Verify: `uv run pytest tests/test_cli.py -k 'event' -v` exits 0.
5. **Classify export failures:** validate a destination's parent/permission errors by handling `OSError` at the export boundary and avoid partial misleading success messages. Retain legitimate user-chosen absolute and relative paths. Test with a temporary denied/missing directory and cleanup in a test fixture; do not write outside isolated test paths. Verify: `uv run pytest tests/test_cli.py -v` exits 0.
6. **Full regression:** `uv run pytest -q` exits 0; `uv run funnelscript check examples/black_friday_2026.json` exits 0; existing `run-world` JSON event smoke works. No fixed test total is promised.

## Test plan and done criteria

- [ ] Unexpected exceptions never masquerade as parse errors in either entrypoint.
- [ ] Known malformed syntax and JSON events have controlled diagnostics.
- [ ] Event time behavior matches the existing Event dataclass, with no arbitrary upper bound.
- [ ] Oversized encoded JSON rejected before decode, with documented bound.
- [ ] Invalid export target reports failure; valid absolute paths remain permitted.
- [ ] Focused and full tests pass, scope has no unrelated edits, and the index status is updated with evidence.

## STOP conditions and maintenance

STOP if error categorization requires changing public exit codes without user approval, unexpected errors are intentionally trapped by a documented integration contract, or tests depend on undocumented brittle message strings. This plan fixes CLI input/output boundaries; future network/prod threat modeling is a separate security exercise.

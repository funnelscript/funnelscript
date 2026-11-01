# Testing and Verification Failure Lessons

---

## 1. Python Import Path Resolution in `src/`-Layout Pyproject Packages

### Context
Executing the initial test suite via `uv run pytest -v` against a newly scaffolded `src/funnelscript/` directory structure.

### What happened
Pytest was executed from the repository root, but failed during test collection because Python could not resolve `import funnelscript`.

### Observable symptom
```text
ModuleNotFoundError: No module named 'funnelscript'
```

### Impact
Blocked immediate test execution in CI/local shells; prevented verification of Phase 1 and 2 code until virtual environment import paths were configured.

### Incorrect assumption
Assumed pytest automatically appends `src/` to `sys.path` when run from repository root.

### Root cause
**Confirmed:** By default, standard pytest does not inject `src/` unless explicitly declared in `pyproject.toml` under `[tool.pytest.ini_options]` with `pythonpath = ["src"]` or installed in editable mode (`uv pip install -e .`).

### Why the architecture allowed it
The initial `pyproject.toml` template contained only build metadata and dependencies, omitting pytest configuration tables.

### Fix
Added the explicit pytest configuration table to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```
Additionally executed `uv pip install -e .` to establish proper wheel entry points.

### Verification
`uv run pytest -v` successfully collected and executed all test files without `sys.path` hacks.

### Prevention rule
Every Python repository adhering to `src/` layout MUST explicitly declare `pythonpath = ["src"]` in `pyproject.toml` upon repository creation.

### Reusable lesson
Standard layout patterns (`src/`) protect against accidental local import shadowing during distribution builds, but require explicit configuration for test harnesses.

### Related code
[`pyproject.toml`](../pyproject.toml)

### Related tests
[`tests/test_agent_core.py`](../tests/test_agent_core.py)

### Related lessons
- `Bun test type definition absence under TypeScript project tsc -b`

### Status
**Resolved**

---

## 2. Parser Method Signature Drift in Test Fixtures

### Context
Authoring Phase 3 scale tests in `tests/test_engine_scale.py` to benchmark 100,000 agents against strategy ASTs.

### What happened
The test fixture called `Parser.from_json_string(SAMPLE_STRATEGY)` instead of the actual public method `Parser.from_json_str(SAMPLE_STRATEGY)`.

### Observable symptom
```text
AttributeError: type object 'Parser' has no attribute 'from_json_string'. Did you mean: 'from_json_str'?
```

### Impact
5 out of 5 tests in `test_engine_scale.py` errored at setup during initial run, halting verification.

### Incorrect assumption
Assumed method name was `from_json_string` based on common language memory rather than inspecting the actual module exports.

### Root cause
**Confirmed:** Method signature mismatch between test fixture authoring and `src/funnelscript/parser.py` definition.

### Why the architecture allowed it
Dynamic duck-typing in Python allows arbitrary method names to pass until runtime evaluation unless static type-checking (`mypy` / `pyright`) is invoked in pre-commit.

### Fix
Corrected call site in `tests/test_engine_scale.py` to `Parser.from_json_str()`.

### Verification
`uv run pytest -k benchmark` executed cleanly, demonstrating $66,000,000\text{ agent-days/second}$.

### Prevention rule
Inspect module definitions or `__all__` exported symbols before writing integration test fixtures; do not rely on LLM statistical memory for method names.

### Reusable lesson
API naming consistency matters: standardizing on `loads` (Python standard) or `from_json_str` across all parsing classes prevents call-site divergence.

### Related code
[`src/funnelscript/parser.py`](../src/funnelscript/parser.py)

### Related tests
[`tests/test_engine_scale.py`](../tests/test_engine_scale.py)

### Related lessons
- `Linter Duck-Typing ID Access Mismatch`

### Status
**Resolved**

---

## 3. Schema Title Assertion Mismatch in CLI Unit Tests

### Context
Validating `funnelscript schema --output schema.json` in `tests/test_cli.py`.

### What happened
The test asserted that `schema["title"] == "FunnelScriptStrategy"`, but the Pydantic schema exporter configured the title as `"FunnelScript Strategy Specification"`.

### Observable symptom
```text
AssertionError: assert 'FunnelScript Strategy Specification' == 'FunnelScriptStrategy'
```

### Impact
1 test failed in `tests/test_cli.py`, preventing clean quality gate pass.

### Incorrect assumption
Assumed schema title matched the class name `FunnelScriptStrategy` without verifying the Pydantic schema generator configuration.

### Root cause
**Confirmed:** `export_json_schema()` injected an explicit human-readable title `"FunnelScript Strategy Specification"` into the Draft 2020-12 schema header.

### Why the architecture allowed it
The test was written with a hardcoded expectation before inspecting the actual output of `schema.py`.

### Fix
Updated assertion in `tests/test_cli.py` to match the canonical specification title `"FunnelScript Strategy Specification"`.

### Verification
`uv run pytest tests/test_cli.py` passed with 7/7 green assertions.

### Prevention rule
Never assert brittle literal tokens without confirming the canonical specification output.

### Reusable lesson
Contract tests should validate structural schema integrity (properties, required keys, $schema draft version) rather than cosmetic title strings unless title stability is a formal requirement.

### Related code
[`src/funnelscript/compiler/schema.py`](../src/funnelscript/compiler/schema.py)

### Related tests
[`tests/test_cli.py`](../tests/test_cli.py)

### Related lessons
- `Parser Method Signature Drift in Test Fixtures`

### Status
**Resolved**

---

## 4. Bun Test Type Definition Absence Under TypeScript `tsc -b`

### Context
Compiling the frontend web application in `apps/web/` using `bun run build` (`tsc -b && vite build`).

### What happened
Co-locating a unit test `src/lib/transpiler.test.ts` that imported `{ test, expect } from 'bun:test'` broke the TypeScript project build.

### Observable symptom
```text
src/lib/transpiler.test.ts:1:30 - error TS2307: Cannot find module 'bun:test' or its corresponding type declarations.
1 import { test, expect } from 'bun:test';
```

### Impact
Frontend production build halted; web distribution could not be compiled despite runtime tests passing under `bun test`.

### Incorrect assumption
Assumed Bun runtime automatically provides ambient TypeScript declarations for `bun:test` to `tsc`.

### Root cause
**Confirmed:** While the `bun` CLI runtime provides built-in test runners, the standard TypeScript compiler (`tsc`) requires physical type definition packages (`bun-types`) declared in `compilerOptions.types`.

### Why the architecture allowed it
The project was initialized with Vite's React template, which defaults to DOM/ESNext types and lacks Bun's ambient execution environment definitions.

### Fix
1. Installed `bun-types` dev dependency: `bun add -d bun-types`.
2. Registered `"types": ["bun-types"]` in `apps/web/tsconfig.json`.

### Verification
`bun test && bun run build` executed sequentially: 1 test passed in 0.42ms, and `tsc -b` completed with 0 errors in 1.95s.

### Prevention rule
Whenever using Bun test utilities inside TypeScript Vite or Next.js applications, `bun-types` MUST be installed and declared in `tsconfig.json`'s `compilerOptions.types`.

### Reusable lesson
Multi-runtime monorepos (e.g. Bun for runtime + `tsc` for type verification) require affirmative bridging of type declarations.

### Related code
[`apps/web/tsconfig.json`](../apps/web/tsconfig.json)

### Related tests
[`apps/web/src/lib/transpiler.test.ts`](../apps/web/src/lib/transpiler.test.ts)

### Related lessons
- `Python Import Path Resolution in src/-Layout Pyproject Packages`

### Status
**Resolved**


---

## 5. New Module API Causing Pytest Collection Failure Before Behavioral RED

### Context
Adding a domain-neutral event kernel to the existing `src/` package while preserving test-first development.

### What happened
The first focused test import referenced `funnelscript.core.event_machine` before that new module existed. Pytest reported a collection error rather than running the intended behavioral assertions.

### Observable symptom
```text
ModuleNotFoundError: No module named 'funnelscript.core.event_machine'
collected 0 items / 1 error
```

### Impact
The first result did not qualify as a behavioral RED test, even though it identified a missing public module.

### Root cause
The test harness could not import the contract under test; this is a collection-level boundary, not evidence that scheduling logic was wrong.

### Fix and verification
Bootstrapped the minimal module interface with an intentionally unimplemented `EventMachine.run`, then reran the focused suite. Fourteen tests executed and failed on missing semantics or invalid-input validation. The implemented reference kernel subsequently passed those tests; final suite verification follows.

### Prevention rule
For a brand-new module, distinguish public-API bootstrap failures from executable behavior failures. Count RED only after tests reach meaningful assertions and runtime code paths.

### Status
**Resolved at the focused-test boundary; full-suite evidence recorded separately.**


---

## 6. Distinguish Lexer Rejection from Parser Rejection in Grammar RED Tests

### Context
Implementing the experimental `rule`/`transition` grammar using test-driven development.

### What happened
A negative test expected a `ParserError` for the unsupported `*` operator in a World rule. The lexer, which intentionally did not tokenize `*`, correctly raised `LexerError` before parsing began. The first RED failure therefore partly reflected an overly narrow test expectation rather than the intended grammar property.

### Root cause
The test conflated two distinct phases of a compiler frontend: tokenization and syntax analysis. Unsupported characters can be rejected before the parser receives input.

### Fix and verification
The test now asserts `(LexerError, ParserError)` for invalid source spellings. The compiler still rejects unsupported operators rather than silently interpreting them. After implementing the narrow grammar and interpreter, the focused suite passed 22 tests and the complete Python suite passed 86 (including a post-review AST-mutation regression test).

### Prevention rule
For negative grammar tests, assert a **rejection boundary**, and only require a specific exception class when the lexical versus syntactic distinction is itself the behavior under test. Never broaden the assertion to a catch-all exception that would hide a runtime crash.

### Status
Resolved and covered by `tests/test_world_rules.py`.


---

## 7. Negative Grammar Tests Can Pass Before a New Feature Exists

### Context
Test-first implementation of source-level `emit Event after Delay;` statements.

### Observed sequence
The initial 13-test focused suite had 10 failures from the old parser rejecting valid new syntax, while three tests rejecting malformed syntax already passed. After parser and static checker implementation, five meaningful runtime failures remained: scheduling, same-time order, future pending events, zero-delay recursion cap, and CLI-observed event count.

### Root cause of potential false confidence
An invalid-source test passing only proves rejection. It does not demonstrate support for valid syntax or observable runtime semantics, and must not be counted as a Green implementation milestone by itself.

### Resolution and prevention
Retained both positive executable assertions and negative type/syntax checks, verified the parser-only stage separately, then implemented event scheduling only after the runtime RED was visible. The final focused suite passed 15 tests and the complete Python suite passed 101 after review-driven priority inheritance and fractional-delay regressions. Future grammar work must pair at least one valid parse/execution assertion with rejection cases.

### Status
Resolved; see `tests/test_world_emissions.py` and the research evaluation manifest.


---

## 8. Validate Guarded Event Chains Beyond Syntax Acceptance

### Context
Adding conditional `when (state OP literal)` clauses to the World interpreter under TDD.

### Observation
The initial 20-case guard suite had 16 failures and 4 existing rejection passes. After lexer/parser/AST support, 15 passed but 5 runtime failures remained: false guards still produced transitions and events, so a bounded chain exhausted `max_events` instead of stopping at its guard limit.

### Lesson
Successful syntax/type acceptance does not establish operational behavior. A guarded rule needs both a static rejection check and a runtime falsifier demonstrating that state and event scheduling are skipped on a false predicate.

### Prevention
Test an observable event chain and assert final state, processed event count, and pending calendar, along with independent negative type cases. The final stage passed 20 focused tests and 121 total tests.

### Status
Resolved; see `tests/test_world_guards.py` and `funnelscript-research/evals/world-guards-v0.md`.


---

## 9. Validate Messages at Both Ingress and Calendar Insertion (2026-10-31)

**Failure class:** Data-boundary type and numeric validity leak in a deterministic event interpreter. Detected by the Typed Event Payloads v0 TDD falsification matrix, not by the initial happy-path tests.

**Controlled reproduction:** `uv run pytest -q tests/test_world_payloads.py` began with 29/29 expected RED failures from unsupported source contracts, then reached GREEN after AST/parser/runtime work. Four new adversarial tests subsequently demonstrated that `float('nan')`, `float('inf')` and `float('-inf')` were accepted as input event values, and the CLI even serialized invalid numeric state. Two additional probes showed mixed-type Python mapping keys raised a generic `TypeError` while an invalid source-emitted record could remain pending past a finite horizon without ever being validated. Both calendar-boundary RED tests failed deterministically; follow-up privacy and duplicate-key RED probes established separate CLI serialization failure modes before their respective fixes.

**Root contributors:** The core Event class intentionally owns no model schema; initial World runtime validation checked exact primitive classes but not IEEE-754 finiteness. The diagnostic path assumed all dictionary keys were comparable strings. The outgoing path relied on *future* receiver validation rather than validating the message at enqueue time, so stopping before the receiver deferred the error indefinitely.

**Bounded repair:** Keep the general EventMachine payload model unchanged. Enforce plain string-key maps, exact schema shape, bool-int separation and finite float values in `WorldExecutor._validated_payload`. Validate generated events using the same method **before** returning them to the scheduler, so a horizon cannot mask invalid messages. Retain an explicit WorldExecutionError with stable classification for malformed external records.

**Evidence:** 37 focused payload tests now pass. A privacy RED probe caught raw malformed event arguments echoed to stderr; the CLI now emits a non-echoing syntax message. A separate JSON RED probe caught duplicate field names silently overriding earlier values; strict duplicate-key rejection now applies to nested payloads. Final fresh verification: 158 Python tests pass, package sdist and wheel build successfully, and source compilation passes. The example CLI input and source-generated event both produce the expected final states; `uv build` succeeds. See `funnelscript-research/evals/typed-event-payloads-v0.md` for the red-green timeline and H-P probes.

**Preventive invariant:** For every World event (external or generated), `keys(payload) = keys(schema)`, all keys are strings, `type(value) = declared primitive type`, and float values satisfy `isfinite`, **before** the event is applied or enters a future calendar slot. This does not yet enforce general finite arithmetic on all state updates or validate calibrated market behavior.


---

## 13. Forward AST Type Alias Referencing a Later Runtime Class

### Context and falsifiable expectation

Adding an explicit typed `SampleExpression` to the World AST after RED tests established the previous parser's incompatibility. The module must import successfully for runtime tests to execute.

### Observed failure

`uv run pytest tests/test_world_stochastic.py -q --tb=short` failed during collection with `NameError: name 'SampleExpression' is not defined` in the `StateExpression = Annotated[...]` union.

### Root cause and mechanism

**Confirmed by source inspection and re-run:** The new class was introduced *below* a module-level union that evaluated `SampleExpression` immediately. `from __future__ import annotations` defers function/class annotations, but does not defer arbitrary module-level expressions. This was a declaration-order defect, not an RNG/runtime/pytest defect.

### Intervention, verification and prevention

Moved `SampleExpression` above `StateExpression`. Focused test collection resumed and the full 25 focused tests passed; 183 full Python tests passed after all source edits. **Preventive invariant:** A runtime-evaluated discriminated union must only reference classes defined earlier in module initialization. Test import/collection after adding AST variants before diagnosing behavioral failures.

### Status

Resolved. No skipped or weakened tests. This collection failure is separate from the original expected 21 behavioral RED cases.

---

## 14. Bun Installed But Missing from Noninteractive Shell PATH

### Context and falsifiable expectation

Run existing frontend validation, `bun test` and `bun run build`, after core-language edits. An unavailable executable does not establish a test failure.

### Observed failure

Both commands exited `127` with `zsh:1: command not found: bun` from noninteractive Mac shell invocations.

### Competing hypotheses and discriminating probe

Either Bun was not installed, or the current shell's PATH omitted its binary. Direct read-only checks found an executable user-local Bun binary and a Homebrew-managed symlink.

### Intervention and verification

Executed the installed binary by absolute path without changing shell initialization or installing dependencies. `bun test` passed (1 test, 0 failures); `bun run build` completed `tsc -b && vite build` successfully. The initial failure was **tool discovery**, not a frontend regression.

### Prevention

When a required development command is not on PATH, resolve a verified local binary before claiming inability to test. Preserve the initial environment failure and the replacement verification command in evidence.

### Status

Resolved for this session; no repository runtime or system PATH mutation was necessary.


---

## 15. World Import Grammar Rejected Source Modules Before Resolver Tests

### Scope and hypothesis

The first Marketing Standard Library milestone requires the existing World parser to accept contextual source `import` statements while the legacy source paths continue to work. The TDD contract predicts rejection before the parser is extended.

### Observed failure signature

The first `uv run pytest tests/test_world_modules.py -q --tb=short` yielded **20 failed, 1 passed**. Every new import path reached `Parser.parse_world` and failed with `Expected entity or agent declaration` before module resolution or safety validation. The existing language control passed. This is expected **feature-absence RED**, not a regression in the existing World parser.

### Causal mechanism and alternatives

The previous grammar permitted only `entity` and `agent` in a World body. The lexer already classified `import` as an identifier, so introducing a new global token was unnecessary. A file-access or wheel-packaging explanation could not account for a failure at the first declaration keyword, before any import path was examined.

### Intervention

Added contextual import parsing, a bounded path resolver, an alias-based one-export compiler expansion, a packaged `.fnl` marketing module and package-data metadata. The parser still emits standard World AST declarations, preserving the existing runtime.

### Verification and lessons

Focused tests progressed to 21 passing and then 23 after adjacent falsification. Standalone imports, duplicate aliases, invalid paths, symlink traversal, cyclic modules, malformed exports, TypeChecker compatibility, two independent aliases and external-CLI execution were all checked. The package wheel included the library source and the isolated install smoke passed. **Prevention:** for parser extensions, first distinguish a missing grammar production from downstream resolver/runtime failures; do not count many same-signature RED tests as independent root causes.

### Status

Resolved as a deliberately test-first feature gap. No unrelated tests were weakened or removed.

---

## 16. Invalid Negative-Path TDD Checks Counted an Unknown Command as Success

**Class:** Test oracle design / false green. **Status:** Resolved. **Scope:** `tests/test_preview_quickstart.py`.

**Observed:** The first source-free test run produced three expected failures and three passing tests for invalid extensions or nonexistent parents. All three passes occurred only because argparse rejected the unknown `init-world` command, so their assertions `returncode != 0` did not exercise the target validation.

**Hypotheses:** (A) The command-specific invalid-target checks executed and passed; (B) they short-circuited at the missing CLI command. The stderr `invalid choice: init-world` falsified A.

**Correction:** Required `.fnl` or `directory` diagnostics in negative tests before modifying production code. The second RED run produced six deterministic missing-command failures; after minimal CLI implementation, all six passed.

**Invariant learned:** Negative tests must assert an error originating at the intended trust boundary, not merely a nonzero exit code. Keep an explicit failure signature so an upstream parser/dispatcher rejection cannot masquerade as successful validation.

---

## 17. Double-Escaped Newline in Remotely Authored CLI Output

**Class:** Tool-mediated source escaping / user-facing output. **Status:** Resolved. **Scope:** `src/funnelscript/cli.py` starter status line.

**Observed:** An isolated-wheel scenario created, checked, and ran a valid World, but its informational output showed a literal backslash-n sequence between the filename and suggested check command.

**Mechanism and discriminating evidence:** The remote edit payload crossed JavaScript and Python-string escape layers, turning the intended newline into a literal `\\n` in a Python source string. The wheel smoke confirmed the issue was actually shipped in the candidate, while the World source and runtime result remained correct.

**Correction:** Replaced the output with a single correctly escaped newline passed to plain `print`, avoiding Rich markup interpretation of user file paths. Extended `tests/test_preview_quickstart.py` to reject a literal `\\nRun:` and require a real newline before `Run:`.

**Invariant learned:** Verify rendered CLI output at the installed-artifact boundary, not only source compilation or parser behavior. Nested transport escaping is an independent user-facing failure mode.

---

## 18. Documentation Copy Drift, Broken Links, and a False-Green Matcher

**Class:** Documentation integrity / test harness validity. **Status:** Resolved. **Scope:** Research `CONTRIBUTING.md`, app `failure-lessons/`, developer entrypoints and documentation link regressions.

**Observed failure:** The research contributor guide advertised absent `src/` and `apps/web/` directories, tried to run application-only tests from a research checkout, and linked to three nonexistent `docs/DECISIONS.md`-style locations. The app's failure lessons contained 18 workstation-specific absolute file URLs, unusable from GitHub.

**TDD timeline:** An initial research `unittest` run passed with a `FutureWarning`, but the regex contained an extra escaping layer and matched no actual links. The warning and an independent link audit invalidated that false green. After correcting the matcher, the focused test failed with **three missing-link subtests**. Replacing the contributor guide with true research paths moved it to green. An independent app `pytest` link test then failed on the first private `file:` URL, and passed after replacing the stale absolute references with repository-relative paths and a public cross-repository URL. Both tests now assert a minimum number of examined links to detect a zero-match harness regression.

**Root cause:** Contribution documentation was copied across two repositories with different physical layouts; historical local-machine hyperlinks were retained. The first test's transport-escaped regex validated only that no matches were found, not that the audit ran. A green status without a nonzero observation count was insufficient evidence.

**Prevention:** Each repository verifies its own canonical Markdown links in CI-compatible standard tools. Keep contributor commands tied to present files and real CLIs, refuse `file:` links in application docs, preserve explicit shipped-versus-proposed labels, and verify example outputs separately against installed artifacts. Link presence does **not** verify external URLs, Markdown anchors, truth of prose, or market-model validity.


---

## 19. Bundled Skill Name Drift, Missing Shared Contract and Ignored Build Bloat

**Class:** Developer tooling / vendored skill provenance / misleading artifact size. **Status:** Immediate defects resolved, transitive vendor closure explicitly unverified. **Scope:** `agents/skills/`, `agents/README.md`, `.agents/product-marketing.md` and mirrored research skill bundles.

**Observed:** Each checkout contained 22 primary skills, but four literature-search directories used underscores while their own frontmatter declared hyphenated names. The academic-paper entrypoint linked to a missing shared language-pair registry. J-Space carried an unused archive of its already extracted content. Local `du` showed roughly 48 MiB of `agents/` data, although the tracked skill tree was about 5.7 MiB; 38.3 MiB per checkout was ignored Rust `target/` output.

**Hypotheses:** (A) The bundle was heavy because of tracked distribution assets; (B) it was mostly regenerable ignored compiler output. `git ls-files`, `git check-ignore`, direct size measurements and the successful manifest-scoped `cargo clean` corroborated B. A separate path hypothesis predicted skill loaders may reject mismatched directory/frontmatter names, independently confirmed by the official Agent Skills format specification.

**RED -> interim GREEN -> RED -> final GREEN:** New `tests/test_skill_bundle.py` initially reported **six failures** per repository: four name mismatches, one missing file link and one duplicate archive. After directory/index/archive repairs, an interim focused run passed, but an independent full-suite rerun still failed on `academic-paper/SKILL.md:622` in both checkouts. The registry existed under `academic-paper/references/`, while the entrypoint still pointed to absent `../shared/output_language_pair.md`; the registry's guide link also ascended into a non-existent `academic-paper/` level. Correcting the two paths yielded app focused **4 passed, 58 subtests passed**, app full **219 passed, 58 subtests passed**, research full **5 passed**, and Bun Web **1 passed**. No existing test assertion was weakened.

**Remediation:** Moved four tracked skill directories with Git, updated discovery names, removed the duplicate ZIP, and cleaned ignored Cargo artifacts using its exact manifest. Added a narrow registry derived from the original research-skill contract; documented that the broader academic-paper suite still references upstream shared protocols not fully vendored. Corrected the internal product-marketing note's false present-tense WASM, `fpm`, cloud and economic-outcome claims.

**Prevention and limits:** Treat an intermediate GREEN as provisional until the final tree has been retested; validate the entrypoint-to-registry and registry-to-guide edges from their actual containing directories. Assert `name == directory`, a 22-skill index, direct resource existence, and no duplicate ZIP. Distinguish on-disk generated sizes from committed bytes. Do not prune nested tools, legal notices, datasets or tests based only on apparent duplication. The current checker does not validate transitive upstream dependencies, external URLs, license compatibility or actual model-agent behavior; OOTB-028 records that possible future gate.


---

## 19. Broad CLI Parser Catches and Premature Export Success

**Class:** Diagnostic ambiguity / unbounded input / partial-export reporting. **Scope:** `src/funnelscript/cli.py` and `tests/test_cli.py`. **Research:** DEC-036, H-CLI1 to H-CLI3.

**Baseline falsifier:** Seven focused tests failed before implementation: injected `AttributeError` was displayed as a parser fault in two entrypoints, two injected `PermissionError` read failures returned validation status, two oversized JSON inputs reached `json.loads`, and a second export failure escaped after a CSV success message.

**Correction:** Catch only declared parser/lexer/type/JSON failures and explicit source I/O errors; reject >64 KiB JSON event arguments before decoding; catch export `OSError` and postpone all success notices. Keep timestamp rules with `Event` and permit user-selected absolute output paths.

**Limit:** Output files can still be partially created before a later export fails; this correction prevents false success reporting, not partial writes. Compiler semantics and real-world prediction claims are unchanged.

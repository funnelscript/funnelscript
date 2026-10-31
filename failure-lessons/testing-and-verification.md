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
[`pyproject.toml`](file:///Users/mamdouhaboammar/Documents/funnelscript/pyproject.toml)

### Related tests
[`tests/test_agent_core.py`](file:///Users/mamdouhaboammar/Documents/funnelscript/tests/test_agent_core.py)

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
[`src/funnelscript/parser.py`](file:///Users/mamdouhaboammar/Documents/funnelscript/src/funnelscript/parser.py)

### Related tests
[`tests/test_engine_scale.py`](file:///Users/mamdouhaboammar/Documents/funnelscript/tests/test_engine_scale.py)

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
[`src/funnelscript/compiler/schema.py`](file:///Users/mamdouhaboammar/Documents/funnelscript/src/funnelscript/compiler/schema.py)

### Related tests
[`tests/test_cli.py`](file:///Users/mamdouhaboammar/Documents/funnelscript/tests/test_cli.py)

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
[`apps/web/tsconfig.json`](file:///Users/mamdouhaboammar/Documents/funnelscript/apps/web/tsconfig.json)

### Related tests
[`apps/web/src/lib/transpiler.test.ts`](file:///Users/mamdouhaboammar/Documents/funnelscript/apps/web/src/lib/transpiler.test.ts)

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

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

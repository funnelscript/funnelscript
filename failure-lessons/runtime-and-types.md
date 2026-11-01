# Runtime and Types Failure Lessons

---

## 1. Frozen Dataclass Attribute Mutation via `object.__setattr__`

### Context
Initializing immutable `PsychographicProfile` instances in `src/funnelscript/core/agent.py` with bounding and validation in `__post_init__`.

### What happened
Attempted to clamp attribute floats (`brand_affinity`, `price_sensitivity`, `fomo_index`) using `object.__setattr__("brand_affinity", val)`.

### Observable symptom
```text
TypeError: object.__setattr__ expected 2 arguments, got 1
```

### Impact
Instantiation of any `Agent` crashed immediately upon creation, blocking Phase 1 verification.

### Incorrect assumption
Assumed `object.__setattr__` behaves like a bound instance method that implicitly receives `self`.

### Root cause
**Confirmed:** In Python, calling `object.__setattr__` directly invokes the unbound descriptor function, which strictly requires three arguments: `(self, name, value)`. Calling it with two arguments passed `(name, value)` as `(self, name)` with 1 missing argument.

### Why the architecture allowed it
Python's standard library does not provide a specialized helper for mutating frozen dataclasses in `__post_init__`; developers must use unbound `object.__setattr__`.

### Fix
Passed `self` explicitly as the first argument across all field assignments:
```python
object.__setattr__(self, "brand_affinity", float(np.clip(self.brand_affinity, 0.0, 1.0)))
```

### Verification
`tests/test_agent_core.py::test_agent_profile_clamping` passed 100% green.

### Prevention rule
When mutating frozen dataclass attributes within `__post_init__`, always supply three arguments: `object.__setattr__(self, field_name, value)`.

### Reusable lesson
Unbound dunder methods on `object` (`__setattr__`, `__delattr__`) always demand the target instance as the first parameter.

### Related code
[`src/funnelscript/core/agent.py`](../src/funnelscript/core/agent.py)

### Related tests
[`tests/test_agent_core.py`](../tests/test_agent_core.py)

### Related lessons
- `TypeScript Strict Unused Variable and Discriminated Union Build Failures`

### Status
**Resolved**

---

## 2. Linter Duck-Typing ID Access Mismatch

### Context
Implementing semantic linter rule `FS102` (Orphaned Touchpoint Detection) in `src/funnelscript/compiler/linter.py`.

### What happened
The method `self.entities_touchpoint_ids()` returned a set of strings `{"tp_meta", "tp_landing"}`. Later, the linter attempted to iterate through the result assuming it contained `TouchpointNode` objects with an `.id` attribute:
```python
registered_ids = {tp.id for tp in self.entities_touchpoint_ids()}
```

### Observable symptom
```text
AttributeError: 'str' object has no attribute 'id'
```

### Impact
Semantic linting crashed on valid strategy ASTs, failing compiler test execution.

### Incorrect assumption
Assumed the helper method returned node dataclass instances rather than projected string identifiers.

### Root cause
**Confirmed:** Inconsistent naming between collection helpers: `entities_touchpoint_ids()` returned strings, while the calling site assumed it was a collection of models.

### Why the architecture allowed it
Lack of static type annotations on helper return values allowed the mismatch to go undetected until runtime.

### Fix
Standardized access: directly used `self.ast.entities.touchpoints` and mapped `.id` explicitly, or used the string set directly without redundant attribute access:
```python
registered_ids = {tp.id for tp in self.ast.entities.touchpoints}
```

### Verification
`tests/test_linter.py` executed with 7/7 passing tests, verifying FS101 through FS501 diagnostics.

### Prevention rule
Distinguish identifier collections from entity model collections through unambiguous method naming (`get_touchpoint_ids() -> set[str]` vs `get_touchpoints() -> list[TouchpointNode]`).

### Reusable lesson
Never perform duck-typed attribute access on collections whose elements might already be primitive identifiers.

### Related code
[`src/funnelscript/compiler/linter.py`](../src/funnelscript/compiler/linter.py)

### Related tests
[`tests/test_linter.py`](../tests/test_linter.py)

### Related lessons
- `Frozen Dataclass Attribute Mutation via object.__setattr__`

### Status
**Resolved**

---

## 3. TypeScript Strict Unused Variable & Discriminated Union Build Failures

### Context
Running production build (`bun run build`) on the React 19 web dashboard in `apps/web/`.

### What happened
The TypeScript compiler (`tsc -b`) failed with 12 errors regarding unused imports (`React`, `Layout`, `Audience`) and un-narrowed property access on `LogicStep` union types.

### Observable symptom
```text
TS6133: 'React' is declared but its value is never read.
TS2339: Property 'action' does not exist on type 'LogicStep'.
  Property 'action' does not exist on type 'ConditionalBranchStep'.
```

### Impact
Prevented web package compilation and verification of Phase 5 dashboard.

### Incorrect assumption
1. Assumed `import React from 'react'` was required in React 19 (the modern JSX transform does not require it).
2. Assumed `step.action === 'TriggerTraffic'` was valid TypeScript without a discriminated union type guard.

### Root cause
**Confirmed:** Vite React TypeScript templates enforce `noUnusedLocals: true` and `noUnusedParameters: true`. In addition, `LogicStep` was defined as `TriggerTrafficStep | ConditionalBranchStep`, where `action` is present only in `TriggerTrafficStep` and `type` is present only in `ConditionalBranchStep`.

### Fix
1. Removed all unused default `React` and icon imports.
2. Implemented proper discriminated type guards:
   ```typescript
   if ('action' in step && step.action === 'TriggerTraffic') { ... }
   else if ('type' in step && step.type === 'ConditionalBranch') { ... }
   ```
3. Prefixed unused parameters with `_` (`_edges: Edge[]`).

### Verification
`bun run build` completed in 1.77s with zero TypeScript diagnostics.

### Prevention rule
Always enforce discriminated union type guards with the `in` operator when working with polymorphic AST nodes in TypeScript.

### Reusable lesson
Modern JSX transforms do not require default `React` imports; omit them to prevent `noUnusedLocals` build failures.

### Related code
[`apps/web/src/lib/transpiler.ts`](../apps/web/src/lib/transpiler.ts)

### Related tests
[`apps/web/src/lib/transpiler.test.ts`](../apps/web/src/lib/transpiler.test.ts)

### Related lessons
- `Bun Test Type Definition Absence Under TypeScript tsc -b`

### Status
**Resolved**

---

## 4. Interactive CLI Subprocess Deadlock in Background Tasks

### Context
Scaffolding the web application using `bun create vite apps/web --template react-ts`.

### What happened
The command ran asynchronously in a background subshell (`task-391`), but hung indefinitely waiting for user input.

### Observable symptom
```text
create-vite v9.3.3
│
◆ Which linter to use?
│ ● Oxlint
│ ○ ESLint
```

### Impact
Command execution blocked for over 30 seconds, requiring manual background task termination and cleanup.

### Incorrect assumption
Assumed `bun create vite ... --template react-ts` was non-interactive when a template flag was provided.

### Root cause
**Confirmed:** Newer releases of `create-vite` (v9.3+) prompt interactively for linter selection even when `--template` is supplied, unless non-interactive CI flags are specified.

### Why the architecture allowed it
Executing high-level scaffolding CLIs in headless environments without checking whether they require interactive TTY input.

### Fix
Terminated the hung process, cleanly scaffolded `package.json` with exact verified dependencies, and ran non-interactive `bun install`.

### Prevention rule
In agentic and automated environments, never invoke wizard-style scaffolding CLIs that may prompt for terminal interactive selection. Author explicit `package.json` files and execute deterministic package installation.

### Reusable lesson
Declarative configuration (explicit files) is always more reliable in automation than procedural scaffolding CLIs.

### Related code
[`apps/web/package.json`](../apps/web/package.json)

### Related tests
N/A (Scaffolding process)

### Related lessons
- `Python Import Path Resolution in src/-Layout Pyproject Packages`

### Status
**Resolved**

---

## 6. Premature Finite-State Initialization Rejection During Arithmetic Hardening (FL-020)

**Symptom:** First Phase 003 `uv run pytest -q` returned 1 failed / 282 passed / 58 subtests because `test_outbound_payload_is_checked_before_entering_pending_calendar` uses an externally constructed infinity state to prove a later outbound record validation boundary.

**Root cause:** Applying finite-float arithmetic safety indiscriminately to state initializers altered an existing independent error-timing contract. The required invariant was only that arithmetic operands and produced floating-point values be finite; it did not authorize a change to all World initial states.

**Correction:** Remove the new initializer finiteness rule while retaining exact primitive initializer typing. Runtime arithmetic rejects non-finite operands and outputs explicitly; existing payload emission validation still fails when trying to publish an invalid float. Re-run the existing regression and the complete application suite.

**Evidence:** Focused existing regression 1 passed (exit 0); final 283 Python tests and 58 subtests passed (exit 0). Keep compiler changes narrow and preserve error precedence across components.

# FunnelScript Failure Lessons Index

This index categorizes all engineering failures, debugging breakthroughs, and resulting architectural invariants across the FunnelScript ecosystem.

---

## Lessons Registry

| ID | Title | Category | Status | Primary Root Cause |
| :---: | :--- | :--- | :---: | :--- |
| **FL-001** | [Python Import Path in src-Layout](testing-and-verification.md#1-python-import-path-resolution-in-src-layout-pyproject-packages) | Testing & Verification | **Resolved** | Missing `pythonpath = ["src"]` in pytest options |
| **FL-002** | [Parser Method Signature Drift](testing-and-verification.md#2-parser-method-signature-drift-in-test-fixtures) | Testing & Verification | **Resolved** | Test fixture called `from_json_string` instead of `from_json_str` |
| **FL-003** | [Schema Title Assertion Mismatch](testing-and-verification.md#3-schema-title-assertion-mismatch-in-cli-unit-tests) | Testing & Verification | **Resolved** | Brittle literal assertion on human-readable title |
| **FL-004** | [Bun Test Type Absence Under tsc](testing-and-verification.md#4-bun-test-type-definition-absence-under-typescript-tsc--b) | Testing & Verification | **Resolved** | `bun-types` not registered in `tsconfig.json`'s `types` |
| **FL-005** | [Frozen Dataclass setattr Mutation](runtime-and-types.md#1-frozen-dataclass-attribute-mutation-via-object__setattr__) | Runtime & Types | **Resolved** | Calling unbound `object.__setattr__` without instance `self` |
| **FL-006** | [Linter Duck-Typing ID Access](runtime-and-types.md#2-linter-duck-typing-id-access-mismatch) | Runtime & Types | **Resolved** | Calling `.id` on collection already projected to strings |
| **FL-007** | [TypeScript Strict Unused & Union Access](runtime-and-types.md#3-typescript-strict-unused-variable--discriminated-union-build-failures) | Runtime & Types | **Resolved** | Unused JSX `React` imports & missing `'action' in step` type guards |
| **FL-008** | [Interactive CLI Subprocess Deadlock](runtime-and-types.md#4-interactive-cli-subprocess-deadlock-in-background-tasks) | DevOps & Tooling | **Resolved** | Interactive terminal prompts inside headless subshells |
| **FL-009** | [Conflating Model Assumptions with Language Axioms](architecture-and-domain-boundaries.md#1-conflating-model-assumptions-with-language-axioms) | Architecture & Scope | **Resolved** | Hardcoding e-commerce rules as universal compiler constraints |
| **FL-010** | [GitHub REST API Org Provisioning Block](architecture-and-domain-boundaries.md#2-github-rest-api-prohibition-on-personal-account-org-provisioning) | DevOps & Tooling | **Resolved** | Third-party REST API restricts org creation to web browser UI |
| **FL-011** | [New Module Collection Failure Before Behavioral RED](testing-and-verification.md#5-new-module-api-causing-pytest-collection-failure-before-behavioral-red) | Testing & Verification | **Resolved** | Bootstrap an executable API contract before counting behavior-level RED |
| **FL-012** | [World AST Incorrectly Sent to Campaign Linter](architecture-and-domain-boundaries.md#3-dispatching-a-new-typed-world-ast-into-the-legacy-campaign-linter) | Architecture & Scope | **Resolved** | Typed AST dispatch before invoking domain-specific compiler stages |
| **FL-013** | [Forward AST Union Declaration](testing-and-verification.md#13-forward-ast-type-alias-referencing-a-later-runtime-class) | Testing & Verification | **Resolved** | Module-level union evaluated before new class binding |
| **FL-014** | [Bun Missing from Shell PATH](testing-and-verification.md#14-bun-installed-but-missing-from-noninteractive-shell-path) | DevOps & Tooling | **Resolved** | Installed Bun binary not included in noninteractive zsh PATH |
| **FL-015** | [World Import Grammar Feature-Absence RED](testing-and-verification.md#15-world-import-grammar-rejected-source-modules-before-resolver-tests) | Testing & Verification | **Resolved** | Parser previously accepted only entity and agent declarations in World blocks |
| **FL-016** | [Unknown CLI Command False-Green TDD](testing-and-verification.md#16-invalid-negative-path-tdd-checks-counted-an-unknown-command-as-success) | Testing & Verification | **Resolved** | Nonzero exit code alone did not prove intended target validation |
| **FL-017** | [Double-Escaped Starter CLI Newline](testing-and-verification.md#17-double-escaped-newline-in-remotely-authored-cli-output) | DevOps & Tooling | **Resolved** | Nested editing transport escaped user-facing newline twice |
| **FL-018** | [Docs Copy Drift, Broken Links and False-Green Matcher](testing-and-verification.md#18-documentation-copy-drift-broken-links-and-a-false-green-matcher) | Documentation & Verification | **Resolved** | Cross-repo template drift, local file URLs and a zero-match regex |
| **FL-019** | [Bundled Skill Name Drift and Build Bloat](testing-and-verification.md#19-bundled-skill-name-drift-missing-shared-contract-and-ignored-build-bloat) | Developer Tooling | **Verified with full suites; vendor closure unverified** | Skill path metadata mismatch, entrypoint/registry link drift and ignored Cargo artifacts |

| **FL-020** | [Premature Finite-State Initializer Rejection](runtime-and-types.md#6-premature-finite-state-initialization-rejection-during-arithmetic-hardening-fl-020) | Runtime & Types | **Resolved** | New arithmetic finiteness guard accidentally changed existing initializer/payload validation timing |

---

## Rules We Now Enforce

1. **Continuous Trajectory Synchronization:** The agent MUST update roadmaps (`ROADMAP.md`), debates (`DEBATES.md`), and failure lessons (`failure-lessons/`) whenever architectural decisions or milestone completions occur.
2. **Deterministic Scaffolding:** Never use interactive CLI wizards in automation; author explicit configuration files (`package.json`, `pyproject.toml`) and run non-interactive package managers.
3. **Multi-Runtime Type Bridging:** In TypeScript projects evaluated by `tsc` but executed by Bun, always declare `"types": ["bun-types"]` in `tsconfig.json`.
4. **Frozen Dataclass Safety:** `object.__setattr__(self, name, value)` must always supply `self` as the first argument when mutating frozen dataclasses in `__post_init__`.
5. **Separation of Language Kernel vs. Model Constraints:** The language compiler checks syntax, types, and topology; model-specific economic rules (mass conservation, liquidity halts, solvency bounds) must be declared as expressive constraints (`constraint { ... }`), not universal compiler axioms.

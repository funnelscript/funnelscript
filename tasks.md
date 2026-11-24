# FunnelScript Meta-Ontology & Core Traits: Master Execution Tracker (`tasks.md`)

**System:** FunnelScript 3-Tier Meta-Ontology & Core Traits Subsystem  
**Source Specifications:** [01_VISION_AND_ARCHITECTURE.md](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/docs/meta-ontology/01_VISION_AND_ARCHITECTURE.md) | [02_IMPLEMENTATION_ROADMAP.md](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/docs/meta-ontology/02_IMPLEMENTATION_ROADMAP.md) | [03_ANTI_PATTERNS_AND_GUARDRAILS.md](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/docs/meta-ontology/03_ANTI_PATTERNS_AND_GUARDRAILS.md) | [04_TESTING_AND_VERIFICATION.md](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/docs/meta-ontology/04_TESTING_AND_VERIFICATION.md)  
**State Ledger:** [META_ONTOLOGY_STATE.json](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/META_ONTOLOGY_STATE.json)  
**Research References:** Palantir Foundry (`operational-ontology`) & ObjectStack (`objectstack`) in `research/funnelscript-palantier/`  
**Execution Environment:** Python 3.12, `pytest-xdist` (10 workers), `ruff`

---

## 1. Executive Architecture & Research Synthesis

### 1.1 The 3-Tier Meta-Ontology Model
FunnelScript decouples arbitrary domain concepts from compiler and runtime cores. Domain packages compose 5 Kernel Primitives and implement standard Traits:

```
+-------------------------------------------------------------------------+
| TIER 3: Community & Industry Packages (fpm)                             |
| e.g. ecommerce/d2c_scale, leadgen/sales_capacity, marketing/saas_plg    |
| Defines domain entities (CODParcel, SalesLead, Seat)                    |
+-------------------------------------------------------------------------+
                                 | implements
                                 v
+-------------------------------------------------------------------------+
| TIER 2: Core Interoperability Traits (core/commerce_traits)             |
| Standard protocols: FinancialBinding, Capacitated, TimeDelayed,         |
|                     Attributable, Ingestable                            |
+-------------------------------------------------------------------------+
                                 | lowers statically to (0 reflection)
                                 v
+-------------------------------------------------------------------------+
| TIER 1: FunnelScript Kernel Behavioral Primitives (5 Built-ins)         |
| Pool<T>, Flow<T>, LedgerAccount<C>, CapacityGuard, Metric               |
| Understood natively by DEVS Event Machine, Ledger, Linter, & Solver     |
+-------------------------------------------------------------------------+
```

### 1.2 Palantir Foundry & ObjectStack Reverse-Engineering Synthesis
From our reverse-engineering analysis of `gura105/operational-ontology` (57.5 MB REA evidence bundle) and `objectstack-ai/objectstack`:

1. **Strict Action-Gated State Mutations:**
   - Object reads and traversals never mutate state.
   - All state transitions and balance updates are governed by lifecycle actions with verified preconditions.
   - Attempted invalid actions generate auditable rejection diagnostics.
2. **Read / Write & Ingestion Separation:**
   - Raw external records (CSV, Meta, Stripe) belong to source space.
   - Declarative `mapping.toml` files hydrate strongly-typed entity instances with cryptographic provenance (`source_file_hash`, `row_id`, `idempotency_key`).
   - Dirty or unmapped rows route to the Dead-Letter Queue (DLQ)—never silently guessing types or inserting nulls.
3. **Zero-Cost Runtime Abstraction (Ontology as Software):**
   - 100% of trait conformance, dimensional verification, and diamond-conflict detection occurs at compile/lint time.
   - Lowering pass (`lowering.py`) erases ontology wrappers into flat DEVS primitives (`StateDefinition`, `EventRuleDefinition`) and double-entry postings before tick `0` starts.
   - Zero dynamic reflection (`getattr`, string dispatch) in simulation execution loops.
4. **Double-Entry Financial Conservation:**
   - All monetary variables operate with exact integer minor units (`Decimal`) and zero floating-point drift.
   - Invariant: $\sum \text{Debits}_c(t) - \sum \text{Credits}_c(t) = 0$ for every currency $c$ at every tick.

---

## 2. Master Progress & Release Gate Dashboard

### 2.1 Phase Execution Status

| Phase | Milestone Name | Status | Deliverables | Tests | Gate |
| :--- | :--- | :---: | :--- | :---: | :---: |
| **Phase 0** | Grammar & Contract Specification Freeze | **VERIFIED** | `spec/meta-ontology-traits-v1.md`<br>`spec/grammar.ebnf` | 800/800 | Spec Drift Clean |
| **Phase 1** | Kernel Primitives & Lowering Pass (`Compiler -> Runtime`) | **VERIFIED** | `tokens.py`<br>`world_ast.py`<br>`parser.py`<br>`ledger.py`<br>`lowering.py`<br>`formatter.py`<br>`cli.py (fmt)`<br>`test_lowering_equivalence.py` | 805/805 | **Gate G2: PASSED** |
| **Phase 2** | Static Trait Resolution & Dimensional Verification (`linter.py`) | **VERIFIED** | `compiler/linter.py`<br>`compiler/dimensions.py`<br>`compiler/diagnostics.py`<br>`tests/fixtures/meta-ontology/`<br>`tests/test_trait_conformance.py` | 821/821 | **Gate G1: PASSED** |
| **Phase 3** | Official Standard Trait Package (`core/commerce_traits`) | **VERIFIED** | `packages/core/commerce_traits/fpm.toml`<br>`index.fnls`<br>`README.md`<br>`tests/test_core_commerce_traits.py` | 828/828 | **Gate G4 (Partial)** |
| **Phase 4** | Declarative Data-to-Object Mapping Layer (`Ingestable`) | **VERIFIED** | `connectors/object_mapper.py`<br>`cli.py (funnelscript map inspect)`<br>`tests/test_object_mapper.py` | 834/834 | **Gate G5: PASSED** |
| **Phase 5** | Flagship Migration, Conservation Fuzzing & Performance | **VERIFIED** | `packages/ecommerce/d2c_scale/`<br>`examples/holistic_8ps_composition.fnls`<br>`tests/test_cross_package_interop.py`<br>`tests/verification/test_meta_ontology_invariants.py`<br>`scripts/benchmark_meta_ontology.py` | 844/844 | **Gates G3, G4, G6: PASSED** |

---

### 2.2 Master Release Gate Checklist (G1–G6)

| Gate ID | Verification Criterion | Target Threshold | Measured Status | Verification Artifact |
| :---: | :--- | :--- | :---: | :--- |
| **G1** | Negative Trait conformance suite (`FNL-O301`..`FNL-O305`) | 100% caught statically; 0 raw tracebacks | **PASSED** | `tests/test_trait_conformance.py` |
| **G2** | Lowering bit-exact equivalence & `snapshot()` determinism | 100% hash match across 5 `PYTHONHASHSEED` runs | **PASSED** | `tests/verification/test_lowering_equivalence.py` |
| **G3** | Hypothesis mass, capacity & ledger conservation fuzzing | 0 invariant violations across 500+ generated graphs | **PASSED** | `tests/verification/test_meta_ontology_invariants.py` |
| **G4** | Cross-package `fpm` interoperability (`pkg_a` + `pkg_b` + `core/commerce_traits`) | Compiles, lints, and reconciles cleanly on 1 ledger | **PASSED** | `tests/test_cross_package_interop.py` |
| **G5** | `Ingestable` dirty-data hydration, DLQ routing & replay idempotency | 100% offline pass; 0 duplicate postings | **PASSED** | `tests/test_object_mapper.py` |
| **G6** | `100k`-event lowering performance benchmark | $\le 5\%$ runtime and memory overhead vs raw DEVS | **PASSED** | `scripts/benchmark_meta_ontology.py` |

---

## 3. Detailed Phase Breakdown & Task Lists

### Phase 0: Grammar & Contract Specification Freeze
- [x] **Task 0.1:** Read and internalize `docs/meta-ontology/01..04`, `AGENTS.md`, and `EXECUTION_RULES.md`.
- [x] **Task 0.2:** Author formal specification [spec/meta-ontology-traits-v1.md](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/spec/meta-ontology-traits-v1.md).
- [x] **Task 0.3:** Extend [spec/grammar.ebnf](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/spec/grammar.ebnf) with `WorldTraitDeclaration`, `WorldEntityDeclaration`, `ImplementsClause`, `PrimitiveField`, `LifecycleHandler`, `PostStatement`, `DelayBranchStatement`.
- [x] **Task 0.4:** Verify zero grammar ambiguities or regressions on existing parser tests (800/800 tests passing).
- [x] **Task 0.5:** Initialize [META_ONTOLOGY_STATE.json](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/META_ONTOLOGY_STATE.json) with Phase 0 `VERIFIED`.

---

### Phase 1: Kernel Primitives & Lowering Pass (`Compiler -> Runtime`)
- [x] **Task 1.1:** Token extensions in [tokens.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/tokens.py):
  - Added `TokenType.ARROW` (`->`) and `TokenType.FAT_ARROW` (`=>`).
  - Added lexical recognition with exact `SourceSpan` boundaries.
- [x] **Task 1.2:** AST extensions in [world_ast.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/compiler/world_ast.py):
  - Added `TraitDefinition`, `TraitMemberDefinition`, `TraitParameter`.
  - Added `PrimitiveFieldDefinition` (`Pool`, `Flow`, `LedgerAccount`, `CapacityGuard`, `Metric`, `Attribute`).
  - Added `LedgerPostingDefinition`, `PostStatementDefinition`, `DelayBranchDefinition`, `BranchArmDefinition`, `LifecycleHandlerDefinition`.
  - Extended `EntityDefinition` with `implements: list[str]`, `primitives`, and `handlers`.
  - Updated `WorldTypeChecker` for declaration uniqueness and primitive checks.
- [x] **Task 1.3:** Parser extensions in [parser.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/parser.py):
  - Added `_parse_trait_members` and `_parse_type_expression` (supporting compound/generic types).
  - Added `_parse_world_declaration` support for `trait` and `entity ... implements ...`.
  - Enforced static prohibition of class inheritance: `extends` rejected with `FNL-O305`.
  - Added parsing for 5 Kernel Primitives, attributes, and lifecycle handlers (`on_<event> -> { post ...; delay ...; }`).
- [x] **Task 1.4:** Double-entry ledger kernel in [ledger.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/ledger.py):
  - Implemented `FinancialLedger`, `LedgerAccount`, `Posting`, `Transaction`.
  - Backed by integer minor units (`Decimal`) with zero float drift.
  - Conservation check: $\sum \text{Debits} - \sum \text{Credits} = 0$.
  - State snapshot, restore, and SHA-256 state hashing.
- [x] **Task 1.5:** Lowering pass in [lowering.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/compiler/lowering.py):
  - Implemented `LoweringPass` and `LoweredWorld`.
  - Erases all `TraitDefinition` wrappers before simulation tick 0.
  - Lowers primitives and lifecycle handlers to flat `StateDefinition`, `EventRuleDefinition`, and ledger postings.
  - Zero runtime dynamic reflection (`getattr`) in execution loops.
- [x] **Task 1.6:** Formatter & CLI in [formatter.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/formatter.py) & [cli.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/src/funnelscript/cli.py):
  - Implemented idempotent formatter `format_funnelscript` (`fmt(fmt(s)) == fmt(s)`).
  - Added `funnelscript fmt <file> [--check]` CLI subcommand.
- [x] **Task 1.7:** Verification Suite 2 in [test_lowering_equivalence.py](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/funnelscript/tests/verification/test_lowering_equivalence.py):
  - Verified bit-exact equivalence vs hand-written DEVS world.
  - Verified 100% ledger hash match across 5 `PYTHONHASHSEED` runs (`0`, `123`, `999`, `4242`, `1337`).
  - Verified `snapshot()` and `restore()` bit-exact match against uninterrupted simulation.
  - Verified zero runtime reflection and formatter idempotency.
- [x] **Task 1.8:** Checkpoint [META_ONTOLOGY_STATE.json](file:///Users/mamdouhaboammar/Documents/M-Research/Funnel-Script-ProJect/Business-Foundry/META_ONTOLOGY_STATE.json): marked Phase 1 `VERIFIED`, Gate G2 `PASSED` (805 passed tests, zero ruff warnings).

---

### Phase 2: Static Trait Resolution & Dimensional Verification (`linter.py`)
- [x] **Task 2.1: Diagnostic Codes & Error Infrastructure:**
  - Defined canonical diagnostic codes in `src/funnelscript/compiler/diagnostics.py`:
    - `FNL-O301`: Missing required Trait member or lifecycle handler.
    - `FNL-O302`: Trait dimensional unit mismatch (e.g. `Duration` passed where `Currency<USD>` is expected).
    - `FNL-O303`: Unbalanced double-entry posting inside a `FinancialBinding` handler.
    - `FNL-O304`: Ambiguous Trait diamond collision without qualified disambiguation.
    - `FNL-O305`: Unsupported class inheritance (`extends`).
  - Ensured all diagnostics produce exact `SourceSpan` carets and remediation hints.
- [x] **Task 2.2: Dimensional Unit System Integration:**
  - Implemented `src/funnelscript/compiler/dimensions.py` with dimensional unit expressions:
    - `Currency<ISO>`, `Duration<Unit>`, `Rate<Num/Denom>`, `Count<Entity>`, `Prob`, `Scalar`.
  - Implemented dimensional compatibility checking with subtyping and generic conformance rules.
- [x] **Task 2.3: Static Trait Conformance Checker in `linter.py`:**
  - Implemented `WorldLinter` inside `src/funnelscript/compiler/linter.py`:
    - Resolves declared traits across world declarations and local imports.
    - Verifies every `entity X implements TraitY` satisfies all declared field signatures and handler signatures (`FNL-O301`).
    - Verifies dimensional matching of entity fields against trait specifications (`FNL-O302`).
    - Verifies double-entry balance in `post` statements: for every transaction, debits equal credits in matching currencies (`FNL-O303`).
    - Detects and rejects diamond collisions when multiple traits define conflicting members without disambiguation (`FNL-O304`).
- [x] **Task 2.4: Suite 1 Test Suite & Negative Fixtures:**
  - Built `tests/fixtures/meta-ontology/` containing valid and negative test cases for each `FNL-O3xx` code.
  - Built `tests/test_trait_conformance.py` verifying 100% static error capture with zero raw Python tracebacks (**Gate G1: PASSED**).
- [x] **Task 2.5: Phase 2 Verification & Checkpoint:**
  - Ran full test suite with `pytest-xdist` (821 passed, 58 subtests passed in 11.54s).
  - Cleaned all ruff linting errors across all meta-ontology files.
  - Updated `META_ONTOLOGY_STATE.json` (`phase_2: VERIFIED`, Gate G1 marked passed).

---

### Phase 3: Official Standard Trait Package (`core/commerce_traits`)
- [x] **Task 3.1: Package Structure & Manifest:**
  - Created directory `packages/core/commerce_traits/`.
  - Authored `packages/core/commerce_traits/fpm.toml` specifying version `0.1.0`, MIT license, description, and exports.
  - Authored `packages/core/commerce_traits/README.md` with complete documentation.
- [x] **Task 3.2: Universal Behavioral Traits (`index.fnls`):**
  - Defined `trait FinancialBinding`: `currency`, `clearing_account`, `on_settlement`.
  - Defined `trait Capacitated`: `capacity_limit`, `on_bottleneck`.
  - Defined `trait TimeDelayed`: `transit_delay`, `on_delay_elapsed`.
  - Defined `trait Attributable`: `channel_id`, `touchpoint_id`, `on_touchpoint`.
  - Defined `trait Ingestable`: `mapping_schema`, `idempotency_key`, `on_ingest`.
- [x] **Task 3.3: Minimal Commerce Protocols (`index.fnls`):**
  - Defined shared contracts: `Offer`, `CustomerCohort`, `Channel`, `Order`, `Settlement`.
  - Strictly enforced interface-only rule: zero hardcoded industry formulas or channel assumptions.
- [x] **Task 3.4: Package Verification Suite:**
  - Implemented `tests/test_core_commerce_traits.py`:
    - Package resolution via `fpm.toml` and `index.fnls`.
    - Linter conformance and clean AST validation across namespace (`as std`) and named (`{ ... }`) imports.
    - Verified negative trait conformance against standard traits (`FNL-O301`).
    - Verified zero-reflection lowering and deterministic DEVS execution in `WorldExecutor`.
    - Verified formatter idempotency on standard package source.
- [x] **Task 3.5: Phase 3 Verification & Checkpoint:**
  - Ran regression suite (828 passed, 58 subtests passed in 9.30s).
  - All ruff linting checks passed cleanly.
  - Updated `META_ONTOLOGY_STATE.json` (`phase_3: VERIFIED`, Gate G4 marked partial).

---

### Phase 4: Declarative Data-to-Object Mapping Layer (`Ingestable`)
- [x] **Task 4.1: Object Mapper Engine:**
  - Authored `src/funnelscript/connectors/object_mapper.py`:
    - Reads an entity's `Ingestable` trait contract.
    - Hydrates typed entity instances from raw CSV, Stripe, and Segment JSON rows.
    - Driven strictly by an explicit, hashed `mapping.toml` file.
- [x] **Task 4.2: Cryptographic Provenance & DLQ Routing:**
  - Attached `source_file_hash`, `row_id`, and `idempotency_key` to every hydrated object instance.
  - Routed malformed, missing, or negative-duration rows to the Dead-Letter Queue (DLQ) with line-level diagnostics (`DLQ-001`..`DLQ-004`).
  - Enforced zero silent runtime coercion, fallback guessing, or LLM-based runtime mapping.
- [x] **Task 4.3: CLI Helper Command:**
  - Implemented `funnelscript map inspect <data.csv> --target <pkg/entity>` in `cli.py`:
    - Inspects headers and emits a proposed draft `mapping.toml` for explicit user review.
- [x] **Task 4.4: Suite 5 Test Suite:**
  - Implemented `tests/test_object_mapper.py`:
    - Verified dirty-data rejection and DLQ routing.
    - Verified idempotent replay (zero duplicate postings on re-ingestion).
    - Verified end-to-end ledger provenance back to `source_file_hash` (**Gate G5: PASSED**).
- [x] **Task 4.5: Phase 4 Verification & Checkpoint:**
  - Full test suite run (`pytest-xdist`: 834 passed).
  - Updated `META_ONTOLOGY_STATE.json` (`phase_4: VERIFIED`, Gate G5 marked passed).
  - Submitted Phase 4 completion report and received user approval for Phase 5.

---

### Phase 5: Flagship Migration, Conservation Fuzzing & Performance
- [x] **Task 5.1: Flagship Package Refactoring:**
  - Refactored `packages/ecommerce/d2c_scale/` to declare `CODParcel` implementing `core/commerce_traits` (`FinancialBinding`, `TimeDelayed`, `Attributable`, `Ingestable`).
  - Refactored `packages/leadgen/sales_capacity/` to declare `SalesLead` and `SalesRepDesk` implementing `core/commerce_traits` (`FinancialBinding`, `Attributable`, `Ingestable`, `Capacitated`).
  - Guaranteed 100% backward compatibility: all 59 existing package module tests pass.
- [x] **Task 5.2: Holistic Cross-Package Composition Proof:**
  - Created `examples/holistic_8ps_composition.fnls` importing both `d2c_scale` and `sales_capacity`.
  - Authored `tests/test_cross_package_interop.py` (**Suite 3 / Gate G4: PASSED**):
    - Verified 2 independent packages share a single `LedgerAccount` and `CustomerCohort` with zero glue code.
    - Verified balanced ledger across cross-package transactions ($\sum \text{Debits} - \sum \text{Credits} = 0$).
    - Verified `format_funnelscript` round-trips idempotently on multi-package worlds.
- [x] **Task 5.3: Property-Based Conservation Fuzzing (Hypothesis):**
  - Implemented `tests/verification/test_meta_ontology_invariants.py` (**Suite 4 / Gate G3: PASSED**):
    - Generated 1,500 fuzzed graphs across 3 property suites.
    - Formally verified 4 invariants across all random seeds with 0 violations:
      1. Non-negativity: $Q_{\text{pool}}(t) \ge 0$.
      2. Mass conservation: $\sum Q_{\text{active}}(t) + \sum Q_{\text{in\_transit}}(t) = Q_{\text{init}} + \text{In} - \text{Out}$.
      3. Capacity ceiling: $\text{Throughput} \le C_{\max}$.
      4. Financial conservation: $\sum \text{Debits}_c(t) - \sum \text{Credits}_c(t) = 0$.
- [x] **Task 5.4: 100k-Event Performance Benchmark:**
  - Implemented `scripts/benchmark_meta_ontology.py` and `tests/test_benchmark_meta_ontology.py` (**Suite 6 / Gate G6: PASSED**):
    - Measured 100,000-event simulation: Trait-based lowered entity vs. raw DEVS rules.
    - Measured results: +2.22% runtime overhead (threshold $\le 5\%$), -80.14% memory overhead (threshold $\le 5\%$), executing at 40,751 events/sec with zero runtime reflection.
- [x] **Task 5.5: Final Master Release Verification:**
  - Verified all 6 Release Gates (**G1 through G6**) green.
  - Ran full test suite across entire monorepo: **844 passed, 1 skipped, 58 subtests passed** in 10.93s.
  - Ran `ruff check` on all meta-ontology files with zero warnings.
  - Updated `META_ONTOLOGY_STATE.json` and `tasks.md` (all phases `VERIFIED`).

---

## 4. Non-Negotiable Guardrails Compliance Matrix

| Rule | Description | Enforcing Mechanism | Verified Status |
| :---: | :--- | :--- | :---: |
| **1** | **Composition Over Inheritance** | Parser rejects `extends` with `FNL-O305`; flat `implements` only | **ENFORCED** |
| **2** | **Zero Industry Logic in Core** | No domain branches in `core/`, `runtime/`, or `ledger.py` | **ENFORCED** |
| **3** | **Zero-Cost Runtime Abstraction** | 100% trait erasure in `lowering.py` before tick 0; 0 reflection | **ENFORCED** |
| **4** | **Single Source of Truth** | Python only (`src/funnelscript/`); 0 TypeScript changes | **ENFORCED** |
| **5** | **Explicit Data Mapping & DLQ** | `mapping.toml` + cryptographic hash provenance; no silent coercion | **ENFORCED** |
| **6** | **Strict Phase Dependency Sequence** | Linear Phase $N \to N+1$ with explicit gate verification and user pause | **ENFORCED** |

---

## 5. Working Commands Reference

```bash
# Run full test suite in parallel (10 workers)
uv run pytest -n auto

# Run Suite 2 lowering equivalence tests specifically
uv run pytest tests/verification/test_lowering_equivalence.py -vv

# Format FunnelScript files idempotently
uv run funnelscript fmt <file.fnls>

# Code quality and linting checks
uv run ruff check src/ tests/
```

# Meta-Ontology & Traits: Sequenced Implementation Roadmap

**Document 2 of 4** | **Scope:** Step-by-Step Execution Order, Concrete Deliverables & Rationale ("Why This Order?")

---

## 1. Dependency-Driven Execution Order

Building a Meta-Ontology in the wrong order causes severe rework (e.g., writing packages before Trait checking exists forces every package to be rewritten). Follow this exact 6-phase sequence:

```text
Phase 0 (Freeze Spec)
   -> Phase 1 (5 Kernel Primitives in AST & Runtime)
      -> Phase 2 (Trait System & Static Contract Checker in Linter)
         -> Phase 3 (Official `core/commerce_traits` Package via `fpm`)
            -> Phase 4 (Declarative Data-to-Object Mapping Layer)
               -> Phase 5 (Migrate Flagship Packages & Cross-Package Proof)
```

---

## 2. Detailed Phase Breakdown (What to Do & Why)

### Phase 0: Grammar & Contract Specification Freeze
* **What to Do:**
  * Author a concise specification (`spec/meta-ontology-traits-v1.md`) defining the exact syntax for `entity`, `trait`, `implements`, and the 5 Kernel Primitives (`Pool`, `Flow`, `LedgerAccount`, `CapacityGuard`, `Metric`).
  * Update `spec/grammar.ebnf` with minimal, non-breaking extensions.
* **Why First:** Locking the grammar before touching `parser.py` or `world_ast.py` prevents syntax drift between the compiler, `funnelscript fmt`, and `fpm` packages.
* **Target Files:** `spec/meta-ontology-traits-v1.md`, `spec/grammar.ebnf`.

### Phase 1: Kernel Primitives & Lowering Pass (Compiler $\to$ Runtime)
* **What to Do:**
  * Add AST nodes in `src/funnelscript/compiler/world_ast.py` for `EntityDecl`, `TraitDecl`, and the 5 Kernel Primitives.
  * Build a **Lowering Pass** (`src/funnelscript/compiler/lowering.py`) that compiles any `entity` declaration down into standard DEVS event-machine rules (`event_machine.py`) and `ledger.py` postings.
  * Ensure the runtime (`world_executor.py`, `engine.py`) executes only lowered primitives with zero dynamic reflection overhead.
* **Why Second:** The runtime must know how to execute the 5 Kernel Primitives cleanly and deterministically before we layer abstract Traits on top of them.
* **Target Files:** `tokens.py`, `parser.py`, `compiler/world_ast.py`, `compiler/lowering.py`, `runtime/world_executor.py`.

### Phase 2: Static Trait Resolution & Dimensional Verification (`linter.py`)
* **What to Do:**
  * Implement static Trait conformance checking inside `src/funnelscript/compiler/linter.py`:
    * Verify that every `entity X implements TraitY` provides all required fields, typed dimensions, and lifecycle handlers.
    * Enforce dimensional compatibility across Trait boundaries (e.g., `FinancialBinding` must carry an explicit ISO currency; `TimeDelayed` must carry a `Duration` unit).
  * Emit span-accurate error codes (`FNL-O301`: Missing Trait Member, `FNL-O302`: Trait Dimension Mismatch, `FNL-O303`: Unbalanced Ledger Binding).
* **Why Third:** Static verification must exist *before* authoring any standard or community packages so the compiler itself guards package quality from day one.
* **Target Files:** `compiler/linter.py`, `compiler/dimensions.py`, `compiler/diagnostics.py`.

### Phase 3: Ship the Minimal Standard Package (`core/commerce_traits`)
* **What to Do:**
  * Create the official `core/commerce_traits` package (version `0.1.0`) structured for `fpm`.
  * Define **only** the minimal universal protocols:
    * Core Behavioral Traits: `FinancialBinding`, `Capacitated`, `TimeDelayed`, `Attributable`, `Ingestable`.
    * Minimal Commerce Interfaces: `Offer`, `CustomerCohort`, `Channel`, `Order`, `Settlement`.
  * Keep the package strictly interface-only (zero industry-specific formulas or hardcoded assumptions).
* **Why Fourth:** Community packages need a single, stable vocabulary to interoperate. Building this right after the Trait checker proves the Trait system works across `fpm` package boundaries.
* **Target Files:** `packages/core/commerce_traits/fpm.toml`, `packages/core/commerce_traits/index.fnls`, `tests/test_core_commerce_traits.py`.

### Phase 4: Declarative Data-to-Object Mapping Layer (`Ingestable` Trait)
* **What to Do:**
  * Build `src/funnelscript/connectors/object_mapper.py` that reads an entity's `Ingestable` trait declaration and binds raw external rows (CSV, Meta Ads, Stripe, Segment) into validated entity instances.
  * Support explicit column/field mapping files (e.g., `mapping.toml`) plus an automated schema-suggestion CLI command (`funnelscript map inspect data.csv --target ecommerce/d2c_scale`) that asks the user to confirm ambiguous column bindings rather than guessing silently.
  * Attach provenance metadata (`source_file_hash`, `row_id`, `idempotency_key`) to every instantiated object.
* **Why Fifth:** This bridges the gap between raw real-world business data and user-defined domain objects without hardcoding platform-to-object logic inside the core engine.
* **Target Files:** `connectors/object_mapper.py`, `cli.py`, `tests/test_object_mapper.py`.

### Phase 5: Flagship Package Migration & Multi-Package Composition Proof
* **What to Do:**
  * Refactor `ecommerce/d2c_scale` and `leadgen/sales_capacity` to declare their domain objects (`CODParcel`, `SalesLead`, `SalesRepDesk`) using `entity ... implements core/commerce_traits.*`.
  * Build a **Cross-Package Composition Example** (`examples/holistic_8ps_composition.fnls`) that imports two independent packages simultaneously—proving they share a single `LedgerAccount`, `CustomerCohort`, and `CapacityGuard` with zero glue code.
* **Why Last:** Real-world packages stress-test every assumption in Phases 1–4. If writing `d2c_scale` and `sales_capacity` feels verbose or awkward, refine the Trait ergonomics *before* opening `fpm` to external contributors.
* **Target Files:** `packages/ecommerce/d2c_scale/`, `packages/leadgen/sales_capacity/`, `examples/holistic_8ps_composition.fnls`.

---

## 3. Summary Milestone Table

| Phase | Core Deliverable | Dependency Prerequisite | Exit Gate |
| :--- | :--- | :--- | :--- |
| **Phase 0** | `spec/meta-ontology-traits-v1.md` + EBNF update | Stable `parser.py` | Grammar passes drift checks with zero ambiguity. |
| **Phase 1** | 5 Kernel Primitives + `lowering.py` | Phase 0 | Custom `entity` compiles to DEVS + Ledger with 0 runtime overhead. |
| **Phase 2** | Static Trait Checker (`FNL-O3xx`) | Phase 1 + Dimensional Typing | Missing/mismatched trait bindings caught at compile time. |
| **Phase 3** | `core/commerce_traits` v0.1.0 | Phase 2 + `fpm` bridge | Package installs via `fpm` and passes `linter.py`. |
| **Phase 4** | `object_mapper.py` (`Ingestable`) | Phase 3 + Connectors | Messy CSV/Stripe logs hydrate typed entities with provenance. |
| **Phase 5** | Flagship Migration + 2-Package Composition | Phase 4 | `d2c_scale` + secondary package interoperate cleanly on 1 ledger. |
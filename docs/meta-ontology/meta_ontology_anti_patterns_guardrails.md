# Meta-Ontology & Traits: What to Avoid & Engineering Guardrails

**Document 3 of 4** | **Scope:** Critical Risks, Anti-Patterns, and Non-Negotiable Constraints

---

## 1. Fatal Anti-Patterns to Avoid

### Anti-Pattern 1: The "Semantic Web / OWL" Trap (Over-Modeling Philosophy)
* **What it looks like:** Designing deep 6-level inheritance hierarchies (`Thing -> EconomicAsset -> IntangibleAsset -> BrandAsset -> BrandEquity`) or debating philosophical definitions of macroeconomics inside the core repo.
* **Why it fails:** Deep inheritance creates brittle coupling and endless academic debates while delivering zero simulation value.
* **The FunnelScript Rule:** **Composition over Inheritance, always.** FunnelScript supports flat `entity` definitions implementing **Traits** (just like Rust traits or Go interfaces). Never implement multi-level class inheritance (`extends`).

### Anti-Pattern 2: Unconstrained Community Silos (No Shared Trait Vocabulary)
* **What it looks like:** Letting every `fpm` package invent its own incompatible definitions for `Order`, `Customer`, and `Revenue` without a shared `core/commerce_traits` contract.
* **Why it fails:** Package A (`acquisition`) cannot feed Package B (`retention`) or Package C (`treasury`). The ecosystem fragments into isolated scripts that cannot be composed into a holistic 8Ps strategy.
* **The FunnelScript Rule:** Every official `fpm` package MUST bind its public inputs/outputs to `core/commerce_traits` protocols, and `fpm publish --dry-run` should warn if a public package exposes raw untyped dicts instead of Trait-bound entities.

### Anti-Pattern 3: "Magic" Silent Entity Resolution
* **What it looks like:** Automatically guessing how to join messy CSV columns or stitch user IDs across Meta, Shopify, and Stripe using opaque heuristics or LLM guesses at runtime without user visibility.
* **Why it fails:** Silent mapping mistakes corrupt financial ledgers and break reproducibility—violating FunnelScript's core promise of deterministic auditing.
* **The FunnelScript Rule:** **Explicit, auditable mapping.** An AI assistant or CLI helper may *suggest* a `mapping.toml` binding from raw data to an `Ingestable` entity, but the binding file MUST be saved, version-controlled, hashed, and deterministically executed.

### Anti-Pattern 4: Runtime Reflection & Dynamic Dispatch Overhead
* **What it looks like:** Keeping rich ontology metadata graphs alive during every DEVS simulation tick and resolving Trait methods dynamically via Python reflection (`getattr`, string lookups).
* **Why it fails:** Destroys simulation throughput when scaling to $100\text{k}+$ events or running multi-start Operations Research optimization sweeps.
* **The FunnelScript Rule:** **Zero-Cost Abstraction.** All Trait resolution, dimensional checking, and entity validation happen 100% at compile/lint time. The lowering pass (`lowering.py`) strips ontology wrappers into flat, `__slots__`-backed DEVS primitives before tick `0` starts.

### Anti-Pattern 5: Hardcoding Industry Assumptions in the Core Engine
* **What it looks like:** Adding `if entity.type == "CODParcel":` or special-casing SaaS MRR inside `world_executor.py` or `ledger.py`.
* **Why it fails:** Breaks the Meta-Ontology boundary and turns the core engine into a tangled monolith.
* **The FunnelScript Rule:** If a domain concept cannot be expressed by composing the 5 Kernel Primitives (`Pool`, `Flow`, `LedgerAccount`, `CapacityGuard`, `Metric`) + Traits, fix the **expressiveness of the primitives**—never hack a domain-specific `if`-branch into the runtime.

### Anti-Pattern 6: Cold-Start Abandonment
* **What it looks like:** Building an abstract Meta-Ontology engine and expecting an external community to show up and build all the marketing packages from scratch.
* **Why it fails:** Nobody builds packages for a new DSL until they see battle-tested reference packages solving painful real-world problems.
* **The FunnelScript Rule:** Maintain at least 2–3 first-party flagship packages (`ecommerce/d2c_scale`, `leadgen/sales_capacity`, `marketing/saas_plg`) built strictly on top of the Meta-Ontology as living proof and templates for contributors.

---

## 2. What to Watch Out For (Subtle Edge Cases)

1. **Trait Diamond Conflicts:**
   * *Risk:* An entity implements two traits (`TraitA` and `TraitB`) that both define a field or handler with the same name (e.g., `on_expire`).
   * *Guardrail:* Reject ambiguous trait collisions statically with error `FNL-O304` and require explicit qualified disambiguation.
2. **Orphaned Mass Across Entity Boundaries:**
   * *Risk:* Package A emits a `Lead` entity and Package B consumes a `Prospect` entity via an adapter, accidentally duplicating or dropping units during conversion.
   * *Guardrail:* Require every cross-entity `Flow` to declare an explicit conservation ratio (e.g., `1:1` identity transfer or explicit batch yield) verified by the linter and runtime mass-conservation checks.
3. **Breaking Trait Versions in `fpm`:**
   * *Risk:* Updating `core/commerce_traits` from `0.1.0` to `0.2.0` breaks half the community packages.
   * *Guardrail:* Treat `core/commerce_traits` as strictly SemVer-locked. Adding optional fields with defaults is a minor bump; changing or removing any required Trait member is a major breaking version.
4. **Over-Complicating `.fnls` Syntax for Non-Developers:**
   * *Risk:* Exposing heavy Rust-like generic syntax (`entity Foo<T: FinancialBinding + 'static>`) scares away growth engineers and strategists.
   * *Guardrail:* Keep Trait syntax clean, flat, and declarative (`entity CODParcel implements FinancialBinding, TimeDelayed`). Hide advanced plumbing inside `fpm` packages so end-users consuming a strategy only configure clean, readable parameters.

---

## 3. Hard Architecture Checklist (Before Merging Any PR)

- [ ] Did this change add any industry-specific logic to `src/funnelscript/core/` or `runtime/`? *(Must be NO)*
- [ ] Does every new `entity` lower cleanly to the 5 Kernel Primitives with zero runtime reflection? *(Must be YES)*
- [ ] Are all Trait violations caught at compile/lint time with exact source spans? *(Must be YES)*
- [ ] Does `core/commerce_traits` remain free of hardcoded business formulas or channel assumptions? *(Must be YES)*
# FunnelScript Meta-Ontology & Core Traits Specification (v1.0)

**Document Type:** Formal Specification  
**Status:** Approved / Frozen (Phase 0)  
**Standard Package:** `core/commerce_traits` (v0.1.0)  
**Kernel Target:** FunnelScript DEVS Event Engine (`event_machine.py`, `ledger.py`, `world_executor.py`)

---

## 1. Abstract & System Model

FunnelScript implements a **3-Tier Meta-Ontology** that decouples domain modeling from the execution core. Domain concepts (e.g., `CODParcel`, `CustomerCohort`, `SalesLead`) are defined in community or standard packages (`fpm`) as **entities** that implement **traits**. 

The core compiler, linter, and runtime know nothing of specific business domains. Instead, every custom entity declaration lowers statically into compositions of the **5 Kernel Primitives**:
1. `Pool<T>` (Stock / Inventory $Q(t) \ge 0$)
2. `Flow<T>` (Directed Rate / Event Transition)
3. `LedgerAccount<Currency>` (Double-entry Financial Account)
4. `CapacityGuard` (Operational Throughput Ceiling)
5. `Metric` (Side-effect-free Derived Observation)

Runtime execution is zero-cost: trait conformance, diamond-conflict disambiguation, and dimensional verification are completed 100% at compile/lint time. Lowered entities execute as flat, `__slots__`-backed DEVS event-machine rules and double-entry postings before tick `0`.

---

## 2. Syntax & Grammar Specifications

### 2.1 Trait Declaration
A trait defines an abstract interface contract comprising required typed fields and lifecycle handler signatures:

```fnls
trait TraitIdentifier {
    // Required fields with dimensional typing
    field_name: TypeExpression;
    
    // Required lifecycle handler signatures
    on_event_name(param: TypeExpression);
}
```

#### Invariants:
- Traits MUST NOT contain state initialization values or default expressions.
- Traits MUST NOT contain executable handler bodies.
- Traits MUST NOT inherit or implement other traits (`trait A extends B` is prohibited).

### 2.2 Entity Declaration & Trait Conformance
Entities define concrete state and behavior by composing Kernel Primitives and implementing Traits:

```fnls
entity EntityIdentifier implements TraitRefList {
    // Attributes & Dimensional Parameters
    attribute_name: TypeExpression = defaultValue;

    // Kernel Primitives
    state pool_name: Pool<EntityIdentifier>;
    ledger account_name: LedgerAccount<CurrencyCode>;
    capacity guard_name: CapacityGuard(max_units, window_duration);
    metric kpi_name: Metric = expression;

    // Events & Lifecycle Handlers
    on_lifecycle_event -> {
        post debit(TargetAccount, amount), credit(SourceAccount, amount);
        delay(transit_duration) -> branch(probability) {
            true  => emit SuccessEvent(self);
            false => emit FailureEvent(self);
        }
    }
}
```

#### Invariants:
- **Flat Composition Only:** Multi-level class inheritance (`entity X extends Y`) is strictly prohibited. The compiler emits `FNL-O305`.
- **Exhaustive Trait Implementation:** An entity must provide all fields and lifecycle handlers required by every implemented trait. Missing items emit `FNL-O301`.
- **Diamond Collision Disambiguation:** If two traits require a field with the same name, the entity must qualify the field explicitly (e.g., `TraitA.status` and `TraitB.status`) unless both traits require the exact same type and semantics. Unqualified collisions emit `FNL-O304`.

---

## 3. The 5 Kernel Primitives & Lowering Semantics

| Kernel Primitive | Formal Mathematical Semantics | Lowering Target in DEVS Runtime |
| :--- | :--- | :--- |
| **`Pool<T>`** | Non-negative discrete or continuous mass: $Q(t) \ge 0$. Conservation: $\Delta Q(t) = \text{Inflow}(t) - \text{Outflow}(t)$. | Lowers to a state integer/float scalar in `WorldState` with non-negativity assertion guards. |
| **`Flow<T>`** | Rate $\lambda$ or scheduled event moving mass from source pool to target pool, with optional stochastic delay $\Delta t \sim \mathcal{D}$. | Lowers to scheduled discrete event-machine transitions (`TransitionStatement`, `EmitStatement`) with keyed RNG. |
| **`LedgerAccount<C>`** | Double-entry balance tracked in ISO currency $C$ with zero float drift: $\sum \text{Debits}_C(t) - \sum \text{Credits}_C(t) = 0$. | Lowers to an entry in `FinancialLedger` (`ledger.py`) backed by integer minor units (`Decimal`). |
| **`CapacityGuard`** | Hard operational bottleneck: $\text{Throughput}(t, t + \Delta t) \le C_{\max}$. | Lowers to an event queue guard (`CapacityGuardNode`) with explicit queueing or overflow routing. |
| **`Metric`** | Pure mathematical derived observation: $M(t) = f(Q(t), \text{Balances}(t))$. | Lowers to a cached observation evaluator in `metrics.py` with zero side effects. |

---

## 4. Dimensional Typing & Unit Verification

FunnelScript enforces physical and economic dimensional safety at compile time:

```text
Dimension ::= Currency<ISO_4217>
            | Duration<s | m | h | day | week>
            | Rate<Dimension / Dimension>
            | Count<EntityRef>
            | Prob (dimensionless in [0, 1])
            | Scalar (dimensionless real)
```

### Typing Rules:
1. `FinancialBinding` requires all financial amounts to be parameterized with explicit ISO currency: `Currency<USD>`, `Currency<EGP>`, `Currency<EUR>`. Cross-currency addition or unbalanced postings (`debit(USD), credit(EUR)`) fail statically with `FNL-O302` or `FNL-O303`.
2. `TimeDelayed` requires latency parameters to carry a valid `Duration` unit: `Duration<day>`, `Duration<h>`, `Duration<m>`. Passing a raw scalar fails with `FNL-O302`.
3. `Capacitated` requires throughput rate to match `Rate<Count / Duration>`.

---

## 5. Standard Core Traits Protocol (`core/commerce_traits`)

The minimal shared vocabulary distributed via `fpm`:

### 5.1 `FinancialBinding`
```fnls
trait FinancialBinding {
    currency: Currency;
    settlement_lag: Duration;
    clearing_account: LedgerAccount;
    on_settlement(amount: Currency);
}
```

### 5.2 `Capacitated`
```fnls
trait Capacitated {
    capacity_limit: CapacityGuard;
    on_capacity_exceeded(entity: Object);
}
```

### 5.3 `TimeDelayed`
```fnls
trait TimeDelayed {
    latency: Duration;
    on_delay_elapsed(entity: Object);
}
```

### 5.4 `Attributable`
```fnls
trait Attributable {
    channel_id: string;
    campaign_id: string;
    touchpoint_timestamp: int;
}
```

### 5.5 `Ingestable`
```fnls
trait Ingestable {
    source_record_id: string;
    source_file_hash: string;
    idempotency_key: string;
}
```

---

## 6. Static Compiler Diagnostics Catalog

| Diagnostic Code | Diagnostic Name | Trigger Condition | Severity |
| :--- | :--- | :--- | :--- |
| **`FNL-O301`** | `MissingTraitMember` | Entity declares `implements Trait` but fails to define a required field or lifecycle handler. | **Error (Compile-Time)** |
| **`FNL-O302`** | `TraitDimensionMismatch` | Entity field does not match the dimensional unit required by the Trait contract. | **Error (Compile-Time)** |
| **`FNL-O303`** | `UnbalancedFinancialBinding` | An `on_` lifecycle handler posts debits and credits that do not balance ($\sum D \ne \sum C$). | **Error (Compile-Time)** |
| **`FNL-O304`** | `AmbiguousTraitDiamondCollision` | Two implemented traits declare a conflicting member without explicit qualification. | **Error (Compile-Time)** |
| **`FNL-O305`** | `UnsupportedInheritance` | Entity uses `extends` syntax instead of flat trait composition (`implements`). | **Error (Compile-Time)** |

---

## 7. Lowering Pass Specification (`compiler/lowering.py`)

The lowering pass traverses AST `EntityDecl` nodes and translates them before tick `0`:
1. **Field Lowering:**
   - `state P: Pool<T>` $\to$ creates a non-negative scalar `P` and an arrival buffer in `WorldState`.
   - `ledger L: LedgerAccount<C>` $\to$ registers `L` in `FinancialLedger` under currency `C`.
   - `capacity G: CapacityGuard(max, dt)` $\to$ wraps arrival handlers with a token-bucket rate limiter.
2. **Lifecycle Lowering:**
   - `on_event -> { ... }` lowers to a deterministic DEVS `RuleDeclaration` with explicit event triggers.
   - `post debit(A, x), credit(B, x)` lowers to an atomic transactional entry in `ledger.py` with double-entry balanced postings.
   - `delay(d) -> branch(p) { ... }` lowers to a stochastic event emission scheduled at $t + d$.
3. **Erasing:**
   - Trait annotations, wrapper classes, and trait interfaces are completely erased from the executing AST.
   - The runtime executes only pure `WorldAST` event rules, pools, flows, and ledger accounts.

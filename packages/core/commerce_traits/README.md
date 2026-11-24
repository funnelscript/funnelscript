# `core/commerce_traits`

**Official Standard Trait & Commerce Protocol Package for FunnelScript**  
**Version:** `0.1.0`  
**License:** `MIT`

---

## 1. Overview

`core/commerce_traits` is the canonical standard package for FunnelScript's **3-Tier Meta-Ontology**. It defines domain-neutral, interface-only contracts that allow any custom business or marketing object declared in external `fpm` packages to interoperate seamlessly across:
- **Deterministic DEVS Runtime** (`engine.py`, `world_executor.py`)
- **Double-Entry Financial Auditing** (`ledger.py`)
- **Static Trait & Dimensional Conformance** (`linter.py`, `dimensions.py`)
- **Mathematical Optimization & OR Solver** (`solver/`)

By adhering to the non-negotiable architectural guardrail **Zero Industry Logic in Core**, FunnelScript's compiler lowers all custom entities conforming to these traits directly into the 5 Kernel Primitives (`Pool`, `Flow`, `LedgerAccount`, `CapacityGuard`, `Metric`) with **zero runtime reflection overhead**.

---

## 2. Universal Behavioral Traits

### `trait FinancialBinding`
Defines how entity lifecycle transitions post double-entry financial debits and credits into the immutable ledger.
- **Fields:**
  - `currency: Currency` — ISO currency unit (`Currency<USD>`, `Currency<EGP>`, etc.).
  - `clearing_account: LedgerAccount` — Primitive ledger account for transaction settlement.
- **Handlers:**
  - `on_settlement(amount: Currency)` — Lifecycle handler executing debit and credit postings.

### `trait Capacitated`
Exposes resource consumption per unit so simulation engines and optimization solvers strictly respect operational throughput limits.
- **Fields:**
  - `capacity_limit: CapacityGuard` — Bounded throughput ceiling and rolling time window.
- **Handlers:**
  - `on_bottleneck()` — Lifecycle event triggered when current load exceeds guard capacity.

### `trait TimeDelayed`
Declares the deterministic or stochastic latency distribution between state entry and completion (e.g., courier transit, sales cycle, invoice clearing).
- **Fields:**
  - `transit_delay: Duration` — Dimensional latency duration (`Duration<day>`, `Duration<hour>`).
- **Handlers:**
  - `on_delay_elapsed()` — Lifecycle event triggered when the elapsed time delay expires.

### `trait Attributable`
Exposes touchpoint provenance metadata for algorithmic multi-touch attribution across marketing channels.
- **Fields:**
  - `channel_id: string` — Unique identifier of marketing or acquisition channel.
  - `touchpoint_id: string` — Unique touchpoint or campaign identifier.
- **Handlers:**
  - `on_touchpoint()` — Lifecycle event logging attribution exposure.

### `trait Ingestable`
Declares an explicit mapping contract from raw external data records (CSV, Stripe, Meta Ads, Segment) into typed entity instances with cryptographic provenance.
- **Fields:**
  - `mapping_schema: string` — Name or path of declarative `mapping.toml` schema.
  - `idempotency_key: string` — Deduplication key preventing duplicate state mutations or ledger postings.
- **Handlers:**
  - `on_ingest()` — Lifecycle event called upon raw record validation and entity instantiation.

---

## 3. Minimal Commerce Contracts

`core/commerce_traits` provides five shared contract interfaces:

1. **`Offer`**: Represents commercial offerings with unit pricing, margins, and active order counts.
2. **`CustomerCohort`**: Represents customer populations, churn rates, and active member pools.
3. **`Channel`**: Represents marketing and distribution channels with daily budgets, cumulative spend, and conversion metrics.
4. **`Order`**: Represents commercial transaction orders with gross amounts, tax, discounts, net amounts, and volume metrics.
5. **`Settlement`**: Represents financial clearing cycles with settled vs. pending amounts and settlement throughput metrics.

---

## 4. Usage Examples

### Example A: Namespace Import (`as std`)
```fnls
world MENAStore {
  import "core/commerce_traits" as std;

  entity CODParcel implements std.FinancialBinding, std.TimeDelayed {
    currency: Currency<EGP> = "EGP";
    ledger clearing_account: LedgerAccount<EGP>;
    transit_delay: Duration<day> = 3;
    state value: int = 150;

    on_settlement -> {
      post debit(clearing_account, 150), credit(bank_cash, 150);
    }

    on_delay_elapsed -> {
      emit Delivered();
    }
  }
}
```

### Example B: Named Member Import
```fnls
world B2BSales {
  import "core/commerce_traits" { Capacitated, FinancialBinding };

  entity SalesDeal implements Capacitated, FinancialBinding {
    currency: Currency<USD> = "USD";
    ledger clearing_account: LedgerAccount<USD>;
    capacity capacity_limit: CapacityGuard(20, 1d);
    state deal_size: int = 25000;

    on_settlement -> {
      post debit(clearing_account, 25000), credit(arr_revenue, 25000);
    }

    on_bottleneck -> {
      emit AlertSDRCapReached();
    }
  }
}
```

---

## 5. Architectural Invariants
- **Composition Over Inheritance:** Multi-level inheritance (`extends`) is statically prohibited (`FNL-O305`). Flat composition via `implements` is strictly enforced.
- **Static Verification:** Member completeness (`FNL-O301`), dimensional consistency (`FNL-O302`), double-entry balance (`FNL-O303`), and diamond ambiguity (`FNL-O304`) are verified statically during `funnelscript check`.
- **Zero-Cost Abstraction:** All trait definitions and protocol bindings are lowered into flat, unboxed DEVS rules and ledger accounts before simulation tick 0.

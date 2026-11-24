# FunnelScript Meta-Ontology & Core Traits: Vision & Architecture

**Document 1 of 4** | **Scope:** Architectural Foundation for Extensible Business & Marketing Objects

---

## 1. The Goal: What Are We Trying to Achieve?

FunnelScript aims to be a **Holistic Marketing & Strategy Execution Language** capable of simulating any business model (8Ps / 8Cs: Product, Price, Place, Promotion, People, Process, Physical Evidence, Productivity) without bloating the core compiler with hardcoded industry assumptions.

**Our Target State:**
1. **A Small, Mathematically Rigid Core:** The FunnelScript engine (`parser.py`, `linter.py`, `engine.py`, `ledger.py`) stays lean, deterministic, and domain-agnostic at the surface level—understanding *conservation laws, time delays, queues, dimensional units, and double-entry accounting*.
2. **Infinite Community Extensibility via `fpm`:** Any domain expert or organization can author an `fpm` package defining arbitrary business objects (e.g., `CODParcel`, `BrandEquity`, `WholesaleDistributor`, `ClinicChair`, `SaaSSeat`) and the core engine immediately knows how to **type-check, simulate, financially audit, and optimize** them.
3. **Guaranteed Cross-Package Interoperability:** Two independent `fpm` packages authored by different teams (e.g., `ecommerce/d2c_scale` and `crm/retention_cohorts`) can plug into the same `.fnls` strategy file and exchange customers, orders, and cash flows seamlessly without schema collisions.
4. **Raw Data to Live Business Objects:** Messy external telemetry (CSV, Meta Ads, Stripe, Segment, ERP logs) can be mapped declaratively onto these typed objects so real-world business reality drives the simulation.

---

## 2. The Core Paradigm: Meta-Ontology + Traits (Not a Static Ontology)

Instead of hardcoding a massive, brittle global taxonomy of marketing, business, and economics inside the compiler (the "Semantic Web / OWL Trap"), FunnelScript adopts a **3-Tier Meta-Ontology Architecture**:

```text
+-------------------------------------------------------------------+
| TIER 3: Community & Industry Packages (via `fpm`)                 |
| e.g., `ecommerce/d2c_scale`, `leadgen/sales_capacity`,            |
|       `retail/omnichannel`, `brand/equity_dynamics`               |
| -> Defines domain objects by composing Tier 1 Primitives          |
|    and implementing Tier 2 Traits.                                |
+-------------------------------------------------------------------+
                                 | implements
                                 v
+-------------------------------------------------------------------+
| TIER 2: Core Interoperability Traits (`core/commerce_traits`)     |
| -> Standard shared contracts: `FinancialBinding`, `Capacitated`,  |
|    `TimeDelayed`, `Attributable`, `Ingestable`, `CohortEntity`    |
+-------------------------------------------------------------------+
                                 | lowers to
                                 v
+-------------------------------------------------------------------+
| TIER 1: FunnelScript Kernel Behavioral Primitives (5 Built-ins)   |
| -> `Pool`, `Flow`, `LedgerAccount`, `CapacityGuard`, `Metric`     |
| -> Understood natively by DEVS Runtime, Linter, Ledger, & Solver. |
+-------------------------------------------------------------------+
```

### Why This Works
A compiler cannot understand human linguistic meaning (e.g., what "Brand Equity" means philosophically). A compiler *can* understand **behavioral contracts (Traits)** and **mathematical primitives**. By lowering every user-defined object into combinations of the 5 Kernel Primitives via explicit Traits, the runtime enforces strict invariants (conservation of money, conservation of mass, dimensional safety, and capacity limits) on objects it has never seen before.

---

## 3. Tier 1: The 5 Kernel Behavioral Primitives

Every business or marketing entity—whether digital or offline—reduces to a composition of five atomic runtime primitives:

| Primitive | Mathematical Role | Examples Across the 8Ps | Engine Guarantee |
| :--- | :--- | :--- | :--- |
| **`Pool`** | A state-holding stock or inventory of discrete entities or continuous mass $Q(t) \ge 0$. | `AddressableAudience`, `WarehouseStock`, `LeadBacklog`, `ActiveSubscribers` | Non-negativity & exact mass conservation ($\Delta Q = \text{In} - \text{Out}$). |
| **`Flow`** | A rate- or event-driven transition moving mass/entities from source to target, optionally with stochastic delay $\Delta t$. | `AdImpressionToClick`, `OrderShipping`, `TrialToPaid`, `RTO_Return` | Dimensional unit matching between source, rate, and destination. |
| **`LedgerAccount`** | A double-entry financial account scoped to a single ISO currency. | `BankCash`, `GatewayReceivable`, `AdSpendExpense`, `CourierCODClearing` | Zero float drift (`Decimal`/minor units) & $\sum \text{Debits} = \sum \text{Credits}$. |
| **`CapacityGuard`** | A hard operational throughput or resource ceiling per time unit. | `SalesRepBandwidth`, `WarehousePackLimit`, `StoreFootfallCap`, `CreditLimit` | Explicit queuing, overflow spilling, or SLA degradation when breached. |
| **`Metric`** | A read-only derived observation or KPI computed over pools, flows, and ledger accounts. | `PaperROAS`, `SettledCashRunway`, `EffectiveCAC`, `NPS_Proxy` | Pure side-effect-free evaluation; safe zero-denominator handling. |

---

## 4. Tier 2: Core Traits & Protocols (`core/commerce_traits`)

Traits are the glue that prevents community packages from becoming isolated islands. When a package author defines a custom object (e.g., `entity CODParcel`), they declare which Traits it implements:

1. **`trait FinancialBinding`**: Declares how lifecycle transitions of this object post double-entry debits/credits into `ledger.py` (including settlement lag $\Delta_{\text{settle}}$ and ISO currency).
2. **`trait Capacitated`**: Exposes resource consumption per unit (e.g., 1 `Lead` consumes `15 min` of `SalesRep` bandwidth) so the DEVS runtime and OR Solver automatically respect operational bottlenecks.
3. **`trait TimeDelayed`**: Declares the stochastic or deterministic latency distribution ($\Delta t$) between state entry and exit (e.g., courier transit, sales cycle, invoice payment).
4. **`trait Attributable`**: Exposes touchpoint provenance metadata (`channel_id`, `campaign_id`, `timestamp`) so Multi-Touch Attribution (`attribution.py`) works automatically on any custom conversion object.
5. **`trait Ingestable`**: Declares a declarative mapping contract from external canonical records (`CanonicalAdSpendRecord`, `CanonicalSettlementEvent`, CSV columns) into typed object instances.

### Official Standard Package: `core/commerce_traits`
To solve the cold-start and cross-package compatibility problem, FunnelScript ships **one tiny, versioned standard trait package** (`core/commerce_traits`) containing the minimal shared interfaces (`Customer`, `Order`, `Offer`, `Channel`, `Settlement`) that community packages import when they want to interoperate.

---

## 5. Conceptual `.fnls` Example (How a Community Author Uses It)

```fnls
import "core/commerce_traits" as std;

// A community author defines a domain-specific object for MENA e-commerce
entity CODParcel implements std.FinancialBinding, std.TimeDelayed {
    value: Currency<EGP>;
    shipping_cost: Currency<EGP>;
    rto_prob: Prob;
    transit_delay: Duration<day>;

    // Kernel primitives wired via Traits
    state in_transit: Pool<CODParcel>;
    ledger clearing: LedgerAccount<EGP>;

    on_dispatch -> {
        post debit(ShippingExpense, shipping_cost), credit(BankCash, shipping_cost);
        delay(transit_delay) -> branch(rto_prob) {
            true  => emit ParcelReturned(self);
            false => emit ParcelDelivered(self);
        }
    }

    on_delivered -> {
        post debit(clearing, value), credit(RevenueRecognized, value);
    }
}
```

Because `CODParcel` implements `std.FinancialBinding` and `std.TimeDelayed`, the **Dimensional Linter**, **DEVS Engine**, **Financial Ledger**, and **OR Solver** all process it natively—without the FunnelScript core ever having hardcoded knowledge of "Cash-on-Delivery Parcels".
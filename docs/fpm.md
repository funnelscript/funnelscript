# FunnelScript Package Manager (`fpm`) Specification

> **Implemented & Integrated Specification:** `fpm` is the official package management, dependency resolution, and ecosystem distribution layer for FunnelScript, accessible directly via `funnelscript fpm <command>` or standalone `fpm <command>`.

---

## 1. Architectural Mission

A domain-specific language scales through modular, reusable code primitives. The FunnelScript Package Manager (`fpm`) distributes versioned marketing libraries through a static registry and deterministic, SemVer-compliant dependency resolution:

```
                          ┌───────────────────────────────┐
                          │     fpm Registry (Static)     │
                          │   (GitHub Pages / Fastly CDN) │
                          └───────────────┬───────────────┘
                                          │
                                   fpm add / install
                                          │
                                          ▼
                            ┌───────────────────────────┐
                            │    .fpm/packages/...      │
                            │   (SHA-256 Verified)      │
                            └─────────────┬─────────────┘
                                          │
                                     writes bridge
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   .fpm/resolution-map.json      │
                         └────────────────┬────────────────┘
                                          │
                                  reads map directly
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │         FunnelScript Compiler         │
                      │  (Zero TOML / SemVer / Network Deps)  │
                      └───────────────────────────────────────┘
```

---

## 2. Mutual Commercial Incentive Model

Package ecosystems thrive when authors have structural economic alignment:

### 2.1 The Agency & SaaS Growth Loop
Growth agencies and performance marketing consultancies possess proprietary funnel architectures (e.g., viral referral chains, high-ticket qualification sequences, cart-abandonment recovery protocols). Currently, these are locked in static slide decks or re-implemented manually per client.

Through `fpm`:
* Agencies package proprietary methodologies into versioned, executable FunnelScript libraries (`@agency/high-ticket-funnel`).
* Packages are distributed publicly (for brand authority and inbound client acquisition) or licensed privately to enterprise clients.
* Strategies include verifiable simulation benchmark proofs (e.g., "$95\%$ confidence of $\text{ROAS} \ge 2.8\times$ under $15\%$ ad-fatigue decay").

### 2.2 Third-Party Platform Providers
Ad networks and SaaS platforms (e.g., TikTok Ads, HubSpot, Klaviyo, Snapchat Ads, Google Ads) have strong commercial incentives to author and maintain official FunnelScript provider connectors:
* Connecting a platform to FunnelScript allows enterprises using Marketing as Code to target that platform natively in automated deployments.
* Provider maintainers gain direct integration into enterprise marketing budgets defined in `.fnls` files.

---

## 3. Package Anatomy & Manifest Specification

Every `fpm` package contains a canonical manifest (`fpm.toml`, with `manifest.json` as legacy fallback) and a deterministic lockfile (`fpm.lock`).

### 3.1 `fpm.toml` (Package Manifest)

```toml
[package]
name = "marketing/saas_plg"
version = "0.1.0"
description = "Product-Led Growth (PLG) SaaS Funnel Package with Multi-Tier Subscriptions and Runway Invariants"
license = "MIT"
funnelscript_version = ">=0.2.0"
main = "index.fnls"

[modules]
index = "index.fnls"
acquisition = "acquisition.fnls"
activation = "activation.fnls"
subscription = "subscription.fnls"
treasury = "treasury.fnls"

[dependencies]
"core/commerce_traits" = ">=0.1.0"
```

### 3.2 `fpm.lock` (Deterministic Lockfile)

The lockfile pins exact cryptographic checksums (SHA-256) of all resolved dependencies:

```toml
schema_version = "1.0.0"

[[packages]]
name = "core/commerce_traits"
version = "0.1.0"
source = "registry"
integrity = "sha256-d7a8fbb56e13b0a04718534839cf1396b29f0e132952541a73dd708535a7b0a7"
entry = "index.fnls"
modules = { index = "index.fnls" }
```

### 3.3 `.fpm/resolution-map.json` (Compiler Bridge)

When running `fpm install`, the package manager materializes verified dependencies into `.fpm/packages/` and writes a hermetic mapping:

```json
{
  "schema_version": "1.0.0",
  "packages": {
    "marketing/saas_plg": {
      "version": "0.1.0",
      "entry": "/path/to/packages/marketing/saas_plg/index.fnls",
      "modules": {
        "index": "/path/to/packages/marketing/saas_plg/index.fnls",
        "treasury": "/path/to/packages/marketing/saas_plg/treasury.fnls"
      }
    }
  }
}
```

The FunnelScript compiler reads `.fpm/resolution-map.json` directly with zero runtime overhead or network access.

---

## 4. Official Shipped Packages

FunnelScript ships with three verified flagship packages in `packages/`:

1. **`core/commerce_traits` (`packages/core/commerce_traits`):**
   Standard commerce traits including `Accountable`, `Attributable`, `Fulfillable`, and `LedgerBridge`.
2. **`ecommerce/d2c_scale` (`packages/ecommerce/d2c_scale`):**
   Full D2C E-Commerce scaling model featuring Meta/Google acquisition, COD vs. Prepaid settlement channels, courier remittance lags, and RTO write-offs.
3. **`marketing/saas_plg` (`packages/marketing/saas_plg`):**
   Full Product-Led Growth SaaS model featuring inbound acquisition, PQL activation, multi-tier subscriptions, logo churn, and cash runway solvency.
4. **`leadgen/sales_capacity` (`packages/leadgen/sales_capacity`):**
   B2B and high-ticket service operations with sales rep capacity queues, hiring ramp-ups, and price elasticity dynamics.

---

## 5. Core CLI Workflow

All commands can be executed via `funnelscript fpm <cmd>` or standalone `fpm <cmd>`:

```bash
# 1. Initialize a new package
funnelscript fpm init agency/custom_funnel

# 2. Add dependencies
funnelscript fpm add ecommerce/d2c_scale@0.1.0
funnelscript fpm add marketing/saas_plg

# 3. Deterministic installation (mandatory in CI)
funnelscript fpm install --frozen

# 4. Cryptographic integrity audit
funnelscript fpm verify

# 5. Build deterministic distribution tarball
funnelscript fpm pack --out dist/

# 6. Print resolved dependency tree
funnelscript fpm graph
```

---

## 4. Module Syntax & Import Semantics

FunnelScript source files import external packages via the `import` statement:

```funnelscript
import "@funnelscript/meta-ads" as Meta;
import "@agency/saas-retention/audiences" as SaaS;

strategy "Q4_Enterprise_Acquisition" {
  entities {
    audience Enterprise_Leads = SaaS.HighIntentTrial;
    touchpoint Retargeting_Ad = Meta.DynamicProductAd {
      cost_per_mille = 18.50 USD;
      adstock_decay = 0.40;
    };
  }
}
```

### Import Resolution Rules:
1. **Local Paths:** `import "./channels/email.fnls" as Email;` resolves relative to the current file.
2. **Registry Packages:** `import "@funnelscript/meta-ads" as Meta;` resolves from the local `.funnelscript_modules/` directory created by `fpm install`.
3. **Circular Dependency Detection:** The compiler builds a strict dependency graph across imported modules and rejects circular imports with `CircularDependencyError`.

---

## 5. Security Invariants & Automated Verification

To prevent untrusted code from exhausting marketing budgets or exfiltrating data, `fpm` enforces three static security invariants before package publication:

1. **Static Invariant Audit:** Packages must pass `funnelscript check` without errors or warnings.
2. **Bounded Budget Gas:** All recurring transitions and triggers must declare explicit spend upper bounds ($C_{\text{max}}$). Unbounded bidding loops are rejected.
3. **Zero Arbitrary Execution:** FunnelScript packages contain only declarative `.fnls` strategy code, schemas, and calibration matrices. Arbitrary executable binaries or shell hooks are strictly prohibited.

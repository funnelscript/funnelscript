# FunnelScript Package Manager (`fpm`) Specification

> **Design proposal, not an implemented package manager.** The current CLI has no `fpm` command or deployed package registry. Names, registry domains, quantitative examples, and business models below are illustrative, not verified services or measurements.

---

## 1. Architectural Mission

A domain-specific language scales through modular, reusable code primitives. A proposed FunnelScript Package Manager (`fpm`) would distribute versioned marketing libraries through a registry and deterministic dependency resolution; no such registry, `fpm` CLI, or verified commercial library catalog is currently deployed.

```
                           ┌───────────────────────────────┐
                           │   fpm Public / Private        │
                           │   Strategy Registry           │
                           │  (registry.funnelscript.org)  │
                           └───────────────┬───────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
                        ▼                                     ▼
         ┌──────────────────────────────┐     ┌──────────────────────────────┐
         │     First-Party Libraries    │     │   Commercial Strategy Libs   │
         │   `fs/channels/meta`         │     │   `@agency/saas-retention`   │
         │   `fs/audiences/ecom`        │     │   `@firm/b2b-account-based`  │
         └──────────────────────────────┘     └──────────────────────────────┘
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
* Provider maintainers gain direct integration into enterprise marketing budgets defined in `.fnl` files.

---

## 3. Package Anatomy & Manifest Specification

Every `fpm` package contains a canonical manifest (`funnelscript.json`) and a deterministic lockfile (`funnelscript.lock`).

### 3.1 `funnelscript.json` (Package Manifest)

```json
{
  "name": "@funnelscript/meta-ads",
  "version": "1.2.0",
  "description": "Standard FunnelScript provider and touchpoint kinematics for Meta Marketing API",
  "license": "MIT",
  "author": "FunnelScript Core Team <core@funnelscript.org>",
  "keywords": ["marketing", "meta", "facebook-ads", "touchpoints", "kinetics"],
  "main": "index.fnl",
  "dependencies": {
    "@funnelscript/core-kinetics": "^0.4.0"
  },
  "benchmarks": {
    "default_adstock_decay": 0.45,
    "default_hill_saturation_k": 2500.00,
    "empirical_calibration": "pymc_mmm_v2"
  },
  "verification": {
    "mass_conservation": true,
    "bounded_budget_gas": true,
    "max_daily_spend_limit": 50000.00
  }
}
```

### 3.2 `funnelscript.lock` (Deterministic Lockfile)

The lockfile pins exact cryptographic checksums (SHA-256) of all resolved dependencies:

```json
{
  "lockfile_version": 1,
  "packages": {
    "@funnelscript/core-kinetics@0.4.0": {
      "version": "0.4.0",
      "resolved": "https://registry.funnelscript.org/@funnelscript/core-kinetics/-/core-kinetics-0.4.0.tar.gz",
      "integrity": "sha256-d7a8fbb56e13b0a04718534839cf1396b29f0e132952541a73dd708535a7b0a7"
    },
    "@funnelscript/meta-ads@1.2.0": {
      "version": "1.2.0",
      "resolved": "https://registry.funnelscript.org/@funnelscript/meta-ads/-/meta-ads-1.2.0.tar.gz",
      "integrity": "sha256-a9b1c8f42d31e98a1290483bcde710293847561a0293847561a0293847561a02"
    }
  }
}
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
1. **Local Paths:** `import "./channels/email.fnl" as Email;` resolves relative to the current file.
2. **Registry Packages:** `import "@funnelscript/meta-ads" as Meta;` resolves from the local `.funnelscript_modules/` directory created by `fpm install`.
3. **Circular Dependency Detection:** The compiler builds a strict dependency graph across imported modules and rejects circular imports with `CircularDependencyError`.

---

## 5. Security Invariants & Automated Verification

To prevent untrusted code from exhausting marketing budgets or exfiltrating data, `fpm` enforces three static security invariants before package publication:

1. **Static Invariant Audit:** Packages must pass `funnelscript check` without errors or warnings.
2. **Bounded Budget Gas:** All recurring transitions and triggers must declare explicit spend upper bounds ($C_{\text{max}}$). Unbounded bidding loops are rejected.
3. **Zero Arbitrary Execution:** FunnelScript packages contain only declarative `.fnl` strategy code, schemas, and calibration matrices. Arbitrary executable binaries or shell hooks are strictly prohibited.

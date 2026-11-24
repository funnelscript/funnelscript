# `marketing/saas_plg`

The official **Product-Led Growth (PLG) SaaS Funnel Package** for FunnelScript.

## Overview
This package models a complete multi-tier SaaS business model under cash constraints and churn dynamics:
* **Acquisition (`acquisition.fnls`):** Tracks paid & organic inbound visitor velocity, CAC, and trial starts.
* **Activation (`activation.fnls`):** Models onboarding setup completions and Product Qualified Lead (PQL) milestones.
* **Subscription Desk (`subscription.fnls`):** Multi-tier plans (Starter, Pro, Enterprise), monthly renewals, expansions/upgrades, and logo churn.
* **Treasury (`treasury.fnls`):** Tracks Net Dollar Retention (NDR), Stripe fee processing, operational burn rates, and continuous cash runway monitoring.

## Usage in FunnelScript
```funnelscript
world MyCompanyStrategy {
  import "marketing/saas_plg" as SaaS;
}
```

## Module Structure
```
packages/marketing/saas_plg/
├── fpm.toml
├── manifest.json
├── index.fnls
├── acquisition.fnls
├── activation.fnls
├── subscription.fnls
├── treasury.fnls
└── README.md
```

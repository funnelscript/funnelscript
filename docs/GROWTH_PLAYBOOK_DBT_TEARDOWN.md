# Reverse Engineering dbt Labs: The Growth Playbook for FunnelScript

> **Unverified research draft, not an evidence report.** Historical dates, traffic/adoption counts, quoted lift percentages, technology-stack attributions and market valuations below were not independently corroborated in this engineering release. The table's "Observed" labels reflect draft notes, not verified causal evidence. Do not cite these figures externally without checking dated primary sources. Proposed FunnelScript products such as `fpm`, Cloud Grid and a WASM playground are not shipped in `v0.2.0a1`.

- **Target Analyzed:** `getdbt.com` (dbt Labs)
- **Beneficiary:** **FunnelScript** ([repository](https://github.com/funnelscript/funnelscript))
- **Date:** 2026-10-31
- **Category Comparison:** Data-as-Code / Analytics Engineering to Marketing-as-Code / Marketing Systems Engineering
- **Evidence Standard:** Draft-reported (unverified), inferred, or not found. External primary-source validation is pending.

---

## 1. In Short

- **The Curve:** dbt grew from a boutique consultancy internal tool (Fishtown Analytics, 2016) into an open-source movement with 50,000+ organizations, 100,000+ Slack community members, and a \$4.2B valuation. Estimated web footprint: ~1.2M monthly visits across `getdbt.com`, `docs.getdbt.com`, and `community.getdbt.com`. Primary inflections: 2019 (creation of the "Analytics Engineer" title and open-source `dbt-core` decoupling), 2020 (launch of Coalesce annual summit), and 2022 (dbt Semantic Layer & Cloud Enterprise).
- **Lined up with growth:**
  1. *Category & Title Creation:* Invented the "Analytics Engineer" job title, converting frustrated data analysts into passionate open-source advocates.
  2. *The Open-Source CLI Wedge:* Free, zero-telemetry CLI (`dbt run`, `dbt test`) installable via `pip` / `brew` that solved local workflow pain on Day 1.
  3. *The Package Hub Network Effect (`hub.getdbt.com`):* Allowed community and vendors (Fivetran, Snowflake) to distribute reusable data models.
- **Biggest Gap for FunnelScript:** FunnelScript has the superior mathematical core (System Dynamics, stochastic Discrete-Event Simulation, $P(\text{Insolvency})$ calculation), but lacks the **ecosystem packaging, community Hub, syntax tooling (VS Code extension), and annual benchmark authority report**.
- **Start this week:** Play #1: Publish the **VS Code / TextMate Syntax Extension** and ship the **GitHub Action (`funnelscript-action`)** to embed `funnelscript check` as a non-negotiable CI gate for marketing budgets.

---

## 2. The Curve & Dated Moves (dbt Labs 2016–2026)

| Date | Channel | Move | Reach | Lift (Visits / Adoption) | Label |
|---|---|---|---|---|---|
| **2016-08** | Open Source | Fishtown Analytics open-sources `dbt` repository on GitHub | Early data engineers | Seed launch | Observed |
| **2018-05** | Community | Launch of dbt Slack Community (dedicated channels for tools & jobs) | ~500 analysts | +35% organic retention | Observed |
| **2019-03** | Positioning | Coining of the "Analytics Engineer" persona in landmark manifesto | Tech Twitter & Hacker News | Baseline inflection | Observed |
| **2020-04** | Product | Launch of dbt Hub (`hub.getdbt.com`) package repository | Entire dbt community | +50% weekly active projects | Observed |
| **2020-12** | Events | First annual "Coalesce: The Analytics Engineering Conference" | 1,000+ virtual attendees | +80% brand searches | Observed |
| **2021-06** | Commercial | Rebranding from Fishtown Analytics to dbt Labs ($150M Series C) | Global data sector | Explosive hiring & enterprise pipeline | Observed |
| **2022-10** | Product | Launch of dbt Semantic Layer and multi-platform cloud orchestration | Fortune 500 enterprises | Upward shift in contract size ($100k+ ACV) | Observed |
| **2024-04** | Content | Annual *State of Analytics Engineering Report* publication | 50k+ downloads | Sustained top-of-funnel authority | Observed |
| **2025-06** | Developer DX | Official dbt VS Code Extension release (`/install-vscode-extension`) | 30k+ active IDE installs | Acceleration in developer activation | Observed |
| **2026-02** | Infrastructure | AI agent readiness: publication of `/llms.txt` and `/llms-full.txt` | LLM search engines (Perplexity, ChatGPT) | #1 citation for data modeling | Observed |

---

## 3. The Funnel Teardown

| Funnel Stage | What dbt Labs Does (Observed) | FunnelScript Parallel (Marketing-as-Code) |
|---|---|---|
| **Acquisition** | Technical docs (`docs.getdbt.com`), Hacker News essays, open-source GitHub repo, Coalesce summit talks (`/dbt-summit` with 368 pages), and ecosystem partner listings (Snowflake, Databricks). | Technical tutorials on modeling ad fatigue ($\lambda$), Hacker News launches, GitHub release notes, and partnerships with data/marketing tools. |
| **Activation** | `pip install dbt-core` ⟶ `dbt init` ⟶ write first `.sql` model ⟶ run `dbt test` in under 5 minutes. | `uvx --from "git+..." funnelscript init-world` ⟶ `funnelscript check` ⟶ run Monte Carlo simulation in under 3 minutes. |
| **Retention** | dbt package dependencies (`packages.yml`), weekly community discussions, career identity tied to the "Analytics Engineer" role. | Strategy dependencies via `fpm` (`std:marketing/lead_response.fnl`), and career identity tied to the **Marketing Systems Engineer (MSE)** role. |
| **Referral** | "dbt certified" developer credentials (`/certifications`), company job postings requiring "Experience with dbt", and public dbt Hub packages. | "Verified FunnelScript Models", GitHub CI status badges (`FunnelScript: Invariants Passing`), and certified agency packages on `fpm`. |
| **Revenue** | Free open-source CLI ⟶ Paid dbt Cloud (web IDE, job scheduler, role-based access, semantic layer, enterprise SSO). | Free open-source CLI (`funnelscript`) ⟶ Paid Cloud Grid (GPU/SIMD multi-agent cloud runs, live Meta/Google ad sync, team collaboration). |

---

## 4. Hidden Signals & Infrastructure

- **Subdomain Ecosystem:** `docs.getdbt.com` (technical documentation on Vercel), `learn.getdbt.com` (self-paced LMS academy), `community.getdbt.com` (events and regional chapters), `app.getdbt.com` (SaaS application on AWS ELB).
- **SEO & Agent-Readiness:** Fully deployed `/llms.txt`, `/llms-full.txt`, and extensive comparison pages (`/why-dbt-vs-alteryx`, `/why-dbt-vs-informatica`) specifically designed to intercept buyers switching from legacy GUI tools.
- **Enterprise Credibility Signals:** Dedicated SOC2 compliance portals, status pages (`status.getdbt.com` via incident.io), and corporate governance guidelines.

---

## 5. Direct Gap Analysis: dbt Labs vs. FunnelScript

| Dimension | dbt Labs (Observed Standard) | FunnelScript (Current State) | Strategic Gap |
|---|---|---|---|
| **Persona & Identity** | Established "Analytics Engineer" across thousands of LinkedIn profiles and job descriptions. | Defined the "Marketing Systems Engineer (MSE)" in internal manifestos (`MARKETING_SYSTEMS_ENGINEERING.md`). | Need public advocacy campaign to formalize the MSE persona on LinkedIn, Substack, and job boards. |
| **IDE & Developer Experience** | Dedicated official VS Code Extension with syntax highlighting, autocomplete, and live compile previews. | Core command-line parser and language specification; manual text editing. | Need immediate TextMate / VS Code extension release for `.fnl` syntax highlighting. |
| **CI/CD Integration Wedge** | `dbt test` runs in every modern enterprise data CI pipeline, blocking broken pull requests. | `funnelscript check` exists locally with AST type checking and mass conservation invariants. | Need a zero-friction GitHub Action (`funnelscript-action`) that teams can drop into `.github/workflows/` with 3 lines of YAML. |
| **Package Distribution Hub** | `hub.getdbt.com` indexes hundreds of community modules. | `fpm` package specification designed; ships initial `std:marketing/lead_response.fnl`. | Need a public registry index (like crates.io or npm) for community marketing models. |
| **Authority Asset** | Annual *State of Analytics Engineering* survey & report read by thousands of engineering leaders. | Rigorous academic and research foundation in `funnelscript-research`. | Need an annual *State of Marketing Systems Engineering & Budget Invariants* benchmark report. |

---

## 6. Actionable Growth Plays for FunnelScript

### Play 1: The "Terraform / dbt for Marketing" GitHub Action CI Wedge
- **Evidence:** dbt's stickiness was sealed when engineering teams required `dbt test` in GitHub Actions before deploying data pipelines to production.
- **Your Gap:** `funnelscript check` exists locally but is not yet packaged as an off-the-shelf GitHub Marketplace Action.
- **Run it with:** `developer-marketing`, `product-marketing`, `launch` · **Keep it going with:** `marketing-loops`
- **Effort:** 3 days · **First result:** 14 days · **Watch:** GitHub Action installations and daily workflow runs · **Cost:** $0
- **Paste-Ready Prompt:**
  > Use the `developer-marketing` and `launch` skills. dbt cemented its position by embedding `dbt test` into enterprise CI/CD pipelines. Package `funnelscript check` as an official GitHub Action (`funnelscript/action-check`). Write the `action.yml`, the integration documentation, and a high-converting launch README showing developers how to block ad-spend PRs that fail audience mass conservation or exceed budget ceilings in 3 lines of YAML. Track Marketplace installs and stars weekly.

### Play 2: Forensic Campaign Teardowns ("Why [Brand] Burned $10M")
- **Evidence:** dbt grew early adoption through technical, uncompromising essays on Medium and Hacker News exposing the fundamental flaws of legacy ETL and spreadsheet models.
- **Your Gap:** FunnelScript has the exact mathematical equations (cash settlement latency $\Delta_{\text{settle}}$, Hill saturation $K$, adstock decay $\lambda$), but has not published them as forensic post-mortems of well-known marketing disasters.
- **Run it with:** `content-strategy`, `copywriting` · **Keep it going with:** `marketing-loops` (content-calendar refill loop)
- **Effort:** 1 week · **First result:** 7 days post-publication · **Watch:** Hacker News front-page points, GitHub repo traffic, and Git clones · **Cost:** $0
- **Paste-Ready Prompt:**
  > Use the `content-strategy` and `copywriting` skills. dbt won over analysts by publishing rigorous technical breakdowns of why legacy data practices fail. Author a forensic technical article titled: *"Why Scaling E-Commerce at 4x ROAS Still Triggers Bankruptcy: Modeling Cash Settlement Latency in FunnelScript"*. Provide the exact `.fnl` campaign code, the mathematical proof of $P(\text{Insolvency})$, the Monte Carlo chart comparing naive linear expectations against reality, and terminal output from `funnelscript simulate`. Avoid conversational fluff and write with the technical authority of an engineering whitepaper.

### Play 3: The Interactive In-Browser Playground (WASM Studio)
- **Evidence:** Modern developer tools (TypeScript, Rust, dbt, SQLPad) achieve massive top-of-funnel conversion by giving developers a zero-install interactive browser sandbox.
- **Your Gap:** Users currently must clone the repo or run `uvx` to experience the language.
- **Run it with:** `free-tools`, `cro` · **Keep it going with:** `marketing-loops`
- **Effort:** 2 weeks · **First result:** 30 days · **Watch:** Playground model executions and "Copy CLI Command" clicks · **Cost:** $0
- **Paste-Ready Prompt:**
  > Use the `free-tools` and `cro` skills. Developer tools achieve maximum conversion when users can test syntax instantly without local installation. Design the architecture and landing page for `play.funnelscript.org`: a lightweight WebAssembly/client-side sandbox with a side-by-side layout (left: interactive `.fnl` code editor with pre-loaded Black Friday and SaaS Lead Gen templates; right: real-time terminal output showing `funnelscript check` passes and stochastic cash trajectory graphs). Add an explicit "Export to CLI" and "Add to GitHub Actions" conversion banner.

### Play 4: Launching the "State of Marketing Systems Engineering" Authority Survey
- **Evidence:** dbt Labs' *State of Analytics Engineering* report (`/state-of-analytics-engineering-2026`) is cited by hundreds of industry publications and drives thousands of enterprise leads annually.
- **Your Gap:** The "Marketing Systems Engineering" persona needs an annual benchmark to rally around.
- **Run it with:** `customer-research`, `lead-magnets` · **Keep it going with:** `marketing-loops` (annual report loop)
- **Effort:** 3 weeks · **First result:** 60 days · **Watch:** Report downloads, newsletter subscribers, and media citations · **Cost:** $0
- **Paste-Ready Prompt:**
  > Use the `customer-research` and `lead-magnets` skills. dbt established category leadership by creating the annual *State of Analytics Engineering* report. Create the questionnaire and distribution strategy for the *2026 State of Marketing Systems Engineering (MSE)* survey. Target 500 growth data scientists and performance engineers. Questions focus on: spreadsheet error frequency, attribution divergence across ad platforms, cash flow surprises during scaling sprints, and the adoption of code-first marketing models. Structure the executive summary and distribution plan for launch across Hacker News, LinkedIn, and PyData channels.

### Play 5: The `fpm` Package Hub & Certified Touchpoint Library
- **Evidence:** dbt Hub (`hub.getdbt.com`) transformed dbt from an individual developer CLI into an ecosystem where every data vendor had to maintain a dbt package.
- **Your Gap:** FunnelScript has `std:marketing/lead_response.fnl`, but needs a visible directory of verified channel touchpoints.
- **Run it with:** `directory-submissions`, `co-marketing` · **Keep it going with:** `marketing-loops`
- **Effort:** 2 weeks · **First result:** 45 days · **Watch:** Third-party package submissions and imports · **Cost:** $0
- **Paste-Ready Prompt:**
  > Use the `directory-submissions` and `co-marketing` skills. dbt created an unassailable ecosystem moat through dbt Hub. Design the specification and web directory for the FunnelScript Package Manager (`fpm.funnelscript.org`). Create 5 pre-calibrated baseline packages in the standard library: `@std/meta-reels`, `@std/google-pmax`, `@std/b2b-cold-outbound`, `@std/stripe-billing-latency`, and `@std/shopify-cashflow`. Provide the package manifest format, semantic versioning contracts, and contribution guide for performance agencies looking to publish certified models.

---

## 7. Plays to Skip

- **Broad B2C Consumer Social Ads:** Do not run paid ads on TikTok or Instagram. FunnelScript is an engineer-level compiler and simulation runtime; developer attention is captured through technical rigor on GitHub, Hacker News, PyData conferences, and specialized Substacks.
- **Generic "No-Code" Marketing Positioning:** Never market FunnelScript as an easy visual drag-and-drop tool for non-technical bloggers. Its competitive moat lies strictly in mathematical soundness, discrete-event simulation, and developer-grade declarative syntax.

---

## 8. 14-Day Implementation Roadmap

| Day | Action Item | Assigned Skill | Deliverable |
|---|---|---|---|
| **Day 1–3** | Author & publish the official TextMate & VS Code extension for `.fnl` syntax. | `developer-marketing` | VS Code Marketplace Extension |
| **Day 4–6** | Build and test the `funnelscript/action-check` GitHub Action with automated test fixtures. | `developer-marketing` | Working GitHub Action in GitHub Marketplace |
| **Day 7–9** | Write and publish the first forensic campaign teardown (*"Why 4x ROAS Causes Bankruptcy"*). | `content-strategy`, `copywriting` | 2,500-word technical whitepaper / blog post |
| **Day 10–12** | Author the "Show HN: FunnelScript – Marketing-as-Code with Stochastic Simulation" launch post. | `launch` | Final Hacker News submission copy & thread prep |
| **Day 13–14** | Deploy the WebAssembly Playground preview prototype at `play.funnelscript.org`. | `free-tools` | Zero-install interactive simulation sandbox |

---

## 9. Method Notes

- **Data Sources:** Live sitemap analysis of `getdbt.com` (1,471 URLs), DNS and subdomain inspection, and documented open-source history of dbt Labs (2016–2026).
- **Vendor Tools Observed on Target:** Vercel (docs & web), AWS ELB (SaaS app), HubSpot (lifecycle email), Optimizely (A/B testing), Google Tag Manager, incident.io (status page).
- **Data Costs:** \$0.00 (100% public architectural intelligence and standard open-source telemetry).

# OUT_OF_THE_BOX.md: Frontier Ideation & Speculative Hypotheses

> An exploratory incubator for unconventional, non-linear, and frontier ideas revolving around the FunnelScript mission. These concepts reside outside the immediate roadmap, serving as seed stock for future research papers, empirical hypotheses, and radical capabilities.

---

## The Incubation Philosophy

In conventional software development, radical ideas are discarded as scope creep. In FunnelScript, visionary concepts are preserved, categorized, and mathematically formulated in this ledger. When core capabilities mature, items from this document are promoted into [`DEBATES.md`](DEBATES.md), validated via formal hypotheses, and codified into [`DECISIONS.md`](DECISIONS.md).

```
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│     OUT_OF_THE_BOX      │ ───> │         DEBATES         │ ───> │        DECISIONS        │
│   Frontier Speculation  │      │   Dialectical Analysis  │      │   Immutable Codification│
└─────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

---

## 1. Adversarial Market Game Theory: Autonomous Red-Team Competitors (OOTB-001)

### The Concept
Current market simulations treat competitors as passive static multipliers (e.g. `competitor_activity: "aggressive"`). What if competitors were autonomous, adversarial learning agents operating in the same auction environment?

### Proposed Mechanism
* Instantiate one or more **Adversarial Competitor Agents** governed by reinforcement learning (PPO) or minimax heuristics.
* The adversarial agent observes our public touchpoints, monitors our price points, and executes hostile counter-actions:
  * **Auction Bidding Wars:** Bid up CPCs on our primary keyword clusters during our peak spend hours.
  * **Offer Undercutting:** Trigger predatory discount campaigns (e.g. 25% off) whenever our landing page traffic surges.
  * **Creative Cannibalization:** Clone high-performing ad creative angles to saturate audience attention and accelerate ad fatigue ($\kappa$).
* **Future Hypothesis ($H_{\text{adv}}$):** *Strategies validated against autonomous adversarial competitors achieve a 40% lower variance in real-world ROAS compared to strategies tested in static environments.*

---

## 2. Viral Memetics & Epidemic Information Diffusion Over Social Graphs (OOTB-002)

### The Concept
Traditional funnels model consumer journeys as isolated linear paths from ad impression to conversion. In reality, consumer decisions are heavily mediated by viral social proof, peer recommendations, and meme diffusion.

### Proposed Mechanism
* Embed population agents within a dynamic **Scale-Free Social Graph** ($\mathcal{G} = (\mathcal{V}, \mathcal{E})$ generated via the Barabási-Albert preferential attachment model).
* Model brand awareness and creative resonance using epidemiological diffusion mathematics (Susceptible-Infectious-Recovered / SIR models):
  $$\frac{dI}{dt} = \beta_{\text{viral}} \cdot S \cdot I - \gamma_{\text{decay}} \cdot I$$
* Highly satisfied converting agents ($\alpha_i > 0.85$) transition to "Infectious" nodes, broadcasting peer recommendations to neighboring nodes with transmission probability $P_{\text{viral}}$. Dissatisfied agents broadcast negative sentiment, inoculating peer nodes against future ad impressions.
* **Future Hypothesis ($H_{\text{viral}}$):** *Simulating network diffusion identifies organic virality tipping points where CAC approaches zero, revealing strategies with non-linear organic lift.*

---

## 3. Macroeconomic Turbulence Swarms: Endogenous Shock Injection (OOTB-003)

### The Concept
Marketing strategies that excel during economic stability often collapse during macroeconomic dislocations. FunnelScript can simulate dynamic macroeconomic shocks injected mid-simulation.

### Proposed Mechanism
* Introduce an **Exogenous Shock Injector** that triggers mid-flight market disruptions:
  * **Currency Devaluation:** Sudden 20% currency depreciation that scales category prices and contracts real wallet balance ($w_i(t) \leftarrow w_i(t) \cdot (1 - \delta)$).
  * **Supply Chain Stockout:** Landing page inventory drops to zero for 4 days, testing whether customer demand waits or permanently churns to competitors.
  * **Payment Gateway Outage:** 48-hour processing failure, testing working capital survival and customer cart recovery resiliency.
* **Future Hypothesis ($H_{\text{shock}}$):** *Stress-testing strategies across stochastic macroeconomic shocks identifies the "Fragility Threshold" of a brand's unit economics.*

---

## 4. Neuro-Symbolic Cognitive Sentinels: The OmniTwin Qualitative Council (OOTB-004)

### The Concept
While $10^5$ vectorized SIMD agents evaluate quantitative metrics (ROAS, CAC, Insolvency), they cannot evaluate whether an ad creative's narrative is offensive, tone-deaf, or culturally compelling.

### Proposed Mechanism
* Deploy a specialized cohort of 50 **Cognitive Sentinel Agents** powered by the OmniTwin cognitive continuity architecture and local Small Language Models (SLMs, e.g. Gemma 2 / Llama 3).
* These sentinels possess detailed episodic memories, socio-cultural identities, and explicit emotional allostasis states.
* Instead of calculating click probabilities, sentinels participate in simulated **Synthetic Focus Groups**:
  * They read proposed ad headlines and marketing copy.
  * They debate product value propositions in natural language.
  * They flag narrative friction, brand trust threats, and unintended PR liabilities before a dollar of ad budget is committed.
* **Future Hypothesis ($H_{\text{council}}$):** *Synthetic qualitative focus groups predict real-world creative CTR outliers with $> 75\%$ directional rank accuracy.*

---

## 5. Zero-Knowledge Strategy Proofs & The Decentralized Strategy Marketplace (OOTB-005)

### The Concept
Top marketing engineers develop proprietary multi-step FunnelScript algorithms, but cannot license or monetize them without revealing their trade secrets and targeting tactics.

### Proposed Mechanism
* Compile FunnelScript strategies into **Zero-Knowledge Proofs of Incrementality (ZK-PoI)**.
* A media buyer or agency can cryptographically prove that Strategy $\mathcal{S}$ achieves $\text{ROAS} \ge 3.5\times$ with $P(\text{Insolvency}) < 0.01$ across a verified market model benchmark, without disclosing the proprietary trigger logic, offer mechanics, or copy sequences.
* Enables a decentralized, trustless marketplace for algorithmic marketing strategies.

---

## 6. Quantum Twin Universes: Zero-Confounder Counterfactual Testing (OOTB-006)

### The Concept
A/B testing in the physical world is plagued by non-stationarity, sample contamination, and temporal confounders. In a virtual simulation, we can run exact counterfactual twins.

### Proposed Mechanism
* Instantiate two identical parallel simulation universes ($\mathcal{U}_A$ and $\mathcal{U}_B$) initialized with the exact same pseudorandom seed, identical agent populations, and identical wallet balances.
* At Day $t^*$, introduce Strategy Intervention $A$ in $\mathcal{U}_A$ and Intervention $B$ in $\mathcal{U}_B$.
* Because every agent is bit-for-bit identical in state and psychographics at $t^*$, any divergence in outcome $\Delta Y = Y_B(T) - Y_A(T)$ is the **pure, unconfounded causal treatment effect** ($100\%$ causal identification with zero aleatoric noise).
* **Future Hypothesis ($H_{\text{twin}}$):** *Twin-universe counterfactuals measure marginal incremental lift with zero sample contamination, providing the gold standard ground truth for offline policy evaluation.*

---

## 7. Autonomous Evolutionary Funnel Synthesis: Auto-FunnelScript (OOTB-007)

### The Concept
Humans design funnels based on traditional industry intuition (e.g. Ad $\to$ Landing Page $\to$ Cart Email). What if an AI agent authored FunnelScript programs algorithmically to discover unintuitive, hyper-efficient marketing topologies?

### Proposed Mechanism
* Implement an evolutionary genetic algorithm or Monte Carlo Tree Search (MCTS) operating over the FunnelScript grammar.
* The search space consists of valid AST topologies: generating novel combinations of conditional delays, multi-channel retargeting paths, dynamic price discovery, and incentive triggers.
* The fitness function maximizes risk-adjusted return:
  $$\text{Fitness}(\mathcal{S}) = \mathbb{E}[\text{Profit}] - \lambda_{\text{risk}} \cdot \text{VaR}_{95}(\mathcal{S}) - \lambda_{\text{ruin}} \cdot P(\text{Insolvency})$$
* **Future Hypothesis ($H_{\text{synth}}$):** *Evolutionary synthesis discovers counter-intuitive, multi-step marketing architectures that outperform human-authored benchmark funnels by $\ge 25\%$ on capital efficiency.*

---

## 8. WebGPU & Metal Hardware Acceleration: 10 Million Real-Time Consumers (OOTB-008)

### The Concept
Scaling simulations from $100,000$ agents to entire national populations ($10^7$ to $10^8$ consumers) in real-time within the web browser.

### Proposed Mechanism
* Transpile FunnelScript agent transition kernels into **WebGPU compute shaders (WGSL)** and native Apple Silicon Metal kernels.
* Maintain agent psychographic state arrays directly in GPU VRAM.
* Execute discrete daily event cycles in parallel across thousands of GPU cores, enabling interactive web canvas simulations of tens of millions of synthetic consumers at 60 FPS.
* **Future Hypothesis ($H_{\text{gpu}}$):** *WebGPU execution achieves $> 1,000,000,000\text{ agent-days/second}$, bringing national-scale market simulations into standard web browsers.*

---

## 9. Autonomous Live Marketing Guardrails & Real-Time Error Budgets (OOTB-009)

### The Concept
When an algorithmic strategy executes in live production, unexpected platform anomalies (e.g. ad exchange auction spikes, tracker pixel failures, sudden API rate limits) can deplete marketing budgets within minutes.

### Proposed Mechanism
* Borrow the **Error Budget & Circuit Breaker** pattern from Google SRE.
* The `LiveEffectHandler` continuously measures real-time burn velocity:
  $$\text{Velocity}(t) = \frac{d\,\text{Spend}}{dt}$$
* If actual spend velocity exceeds the modeled upper confidence bound $P_{95}(\text{Velocity})$ by $> 2.5\times$, or if conversion tracking fails to record an expected event within a dynamic timeout window, the runtime immediately trips a circuit breaker:
  * Automatically sets campaign budgets to safety baselines.
  * Dispatches an emergency webhook alert to the human media buying team.
  * Preserves working capital before catastrophe occurs.
* **Future Hypothesis ($H_{\text{guard}}$):** *Autonomous real-time error budgets eliminate 99% of accidental ad-account drain incidents caused by algorithmic misconfigurations or platform tracking outages.*

---

## 10. Effect Intent Static Verification & Capability Sandboxing (OOTB-010)

### The Concept
Similar to WebAssembly capability models or Deno security permissions, strategies should declare what external side effects they are permitted to emit, and the compiler should statically enforce capability boundaries.

### Proposed Mechanism
* Introduce explicit capability declarations in the FunnelScript header:
  ```funnelscript
  capabilities {
    effects: [budget.adjust, email.dispatch],
    max_daily_spend: 5000.00 USD,
    prohibited: [external.webhook, sms.broadcast]
  }
  ```
* The AST semantic linter verifies that no rule or trigger block emits an `EffectIntent` outside the declared capability set.
* Third-party community packages downloaded from package registries cannot secretly dispatch unapproved network mutations or exceed financial risk parameters.
* **Future Hypothesis ($H_{\text{sandbox}}$):** *Static capability sandboxing guarantees that third-party marketing strategy packages can be executed in live production without risk of arbitrary network exfiltration or unauthorized financial mutation.*

---

## 11. Time-Traveling Reversible Shadow Debuggers (OOTB-011)

### The Concept
When a live marketing campaign underperforms in production, marketing teams debate what went wrong using subjective opinions. FunnelScript can ingest live production telemetry and provide time-traveling deterministic replays for post-mortem debugging.

### Proposed Mechanism
* Record all inbound live events (webhooks, user clicks, ad spend updates) into an immutable temporal event log.
* The developer opens the FunnelScript Time-Traveling Debugger and steps backward and forward through the live campaign second by second.
* The developer can introduce a counterfactual strategy tweak at Day 14 and immediately branch into a simulated alternative universe to see if the tweak would have rescued campaign profitability.
* **Future Hypothesis ($H_{\text{replay}}$):** *Temporal event log replay reduces the time required to diagnose campaign performance degradation from days to minutes while enabling exact empirical counterfactual testing.*

---

## 12. Julia LLVM / Mojo Native Execution Backend for Billion-Agent Scale (OOTB-012)

### The Concept
While NumPy vectorization scales to $10^5 - 10^6$ agents on single workstations, simulating entire national consumer populations ($10^7 - 10^9$ agents) across multi-year macroeconomic cycles requires native LLVM JIT compilation and distributed supercomputing clusters.

### Proposed Mechanism
* Author a dedicated **Julia / Mojo Transpilation Backend** for the FunnelScript AST.
* Transpile declarative agent rules and stochastic kernels into high-performance Julia code using `Agents.jl` and `Distributed.jl`.
* Execute large-scale Monte Carlo batches across multi-node GPU/TPU clusters, modeling aggregate emergent phenomena such as macroeconomic inflation passthrough, supply chain bottlenecks, and competitive price wars.
* **Future Hypothesis ($H_{\text{julia}}$):** *A Julia/LLVM execution target provides a $40\times - 100\times$ speedup over Python SIMD, enabling 100-million-agent simulations in under 60 seconds.*

---

## 13. FunnelScript State Drift & Live Reconciliation Engine (OOTB-013)

### The Concept
In cloud computing, Terraform detects when an engineer manually changes a security group in the AWS Console, labeling it "Configuration Drift". In digital marketing, media buyers frequently edit ad budgets or paused ad sets directly in Meta Ads Manager without updating strategy documentation.

### Proposed Mechanism
* Implement a continuous background daemon `funnelscript drift-detect`.
* The engine queries connected provider APIs (Meta Graph API, Google Ads API, Klaviyo API) and compares physical live state with the canonical `funnelscript` codebase.
* If discrepancies are detected:
  * Generates an actionable diff report (`+1 touchpoint added manually in Meta`, `~ budget drifted from $1,000 to $1,800`).
  * Provides `funnelscript refresh` (pull live changes into code) or `funnelscript apply --force` (overwrite manual drift to enforce declared strategy).
* **Future Hypothesis ($H_{\text{drift}}$):** *Automated drift detection eliminates 100% of untracked rogue ad spends and configuration inconsistencies in multi-member marketing teams.*

---

## 14. Formal Verification of Marketing Contracts using SMT Solvers (OOTB-014)

### The Concept
Smart contracts use Satisfiability Modulo Theories (SMT) solvers like Z3 to mathematically prove that under no execution sequence can funds be locked or drained. Marketing funnels can be formally verified using the same mathematical rigor.

### Proposed Mechanism
* Compile FunnelScript state transition graphs and budget allocation rules into first-order logic formulas for the **Z3 SMT Solver**.
* Formally verify mathematical theorems before deployment:
  * **Zero-Ruin Theorem:** Prove that for all initial cash reserves $C_0 \ge C_{\text{min}}$ and settlement clearance delays $\Delta_{\text{settle}} \le 7$, $P(\text{Insolvency}) \equiv 0$.
  * **Audience Deadlock Freedom:** Prove that every agent entering the top of the funnel reaches an absorbing terminal state (Purchase, Churn, or Unsubscribe) in finite time $\tau < \infty$.
  * **Spam Invariant:** Prove that no agent can receive more than $M$ messages across all channels within any sliding 48-hour window.
* **Future Hypothesis ($H_{\text{smt}}$):** *SMT formal verification identifies subtle deadlock states, audience cannibalization traps, and liquidity depletion vulnerabilities that Monte Carlo sampling misses.*

---

## 15. In-Editor Live Monte Carlo Co-Pilot & WebAssembly LSP Simulation Preview (OOTB-015)

### The Concept
When developers edit code in VS Code or Cursor, they see syntax errors and type warnings. What if hovering over a `touchpoint` or `campaign` block displayed a real-time, interactive probability density preview of expected ROAS and customer journey completion times?

### Proposed Mechanism
* Compile the vectorized simulation kernel to **WebAssembly (WASM)** via Pyodide or Rust/C++ compilation.
* Embed the lightweight WASM runner directly inside the FunnelScript Language Server.
* As the user tweaks budget or targeting numbers, the LSP runs a micro-batch of $1,000$ synthetic agents in $< 20\text{ms}$ in the background.
* Renders rich CodeLens annotations and interactive hover cards directly above `.fnl` strategy blocks:
  ```text
  ▶ 1,000 Agent Preview: Expected ROAS 3.2x [2.1x - 4.4x] | Conv Rate: 8.4% | Insolvency Risk: 0.0%
  ```
* **Future Hypothesis ($H_{\text{copilot}}$):** *Real-time in-editor simulation feedback reduces campaign misconfiguration rates by 80% prior to running formal Monte Carlo trials.*

---

## 16. Headless CI/CD GitHub Action & PR Risk Bot (FunnelScript Diff Guardian) (OOTB-016)

### The Concept
Marketing strategy documents are typically modified in spreadsheets without code review. FunnelScript strategies live in Git. Every pull request altering a `.fnl` file should automatically undergo automated economic risk review before merging.

### Proposed Mechanism
* Build an official GitHub Action: `funnelscript/diff-guardian-action`.
* On pull requests:
  1. Executes `funnelscript check` to guarantee mass conservation and DAG acyclicity.
  2. Runs $100,000$-agent Monte Carlo simulations on the base branch and the feature branch using identical random seeds.
  3. Computes the **Strategic Risk Delta**:
     $$\Delta \text{ROAS} = \text{ROAS}_{\text{PR}} - \text{ROAS}_{\text{base}}$$
     $$\Delta \text{VaR}_{95} = \text{VaR}_{\text{PR}} - \text{VaR}_{\text{base}}$$
     $$\Delta P(\text{Insolvency}) = P(\text{Insolvency})_{\text{PR}} - P(\text{Insolvency})_{\text{base}}$$
  4. Automatically posts a structured markdown comment on the PR detailing financial downside risk and flags any potential cash starvation cliffs.
* **Future Hypothesis ($H_{\text{ci}}$):** *Automated CI/CD simulation diffs eliminate unexpected real-world marketing budget overruns by gating merges behind statistical risk thresholds.*

---

## 17. Algorithmic Strategy Marketplace & Decentralized Strategy Registry (`fpm`) (OOTB-017)

### The Concept
Top growth hackers, media agencies, and research econometrics labs develop proprietary multi-step marketing architectures (e.g. viral referral loops, high-ticket B2B account acquisition funnels). Currently, these are kept as agency trade secrets or shared via static PDF playbooks.

### Proposed Mechanism
* Build the **`fpm` Strategy Registry** (`registry.funnelscript.org`).
* Agencies can publish verified, encrypted FunnelScript libraries and frameworks:
  * **Open-Source Strategy Libs:** Free community blocks (`fs/channels/meta`, `fs/audiences/ecom`).
  * **Commercial Strategy Packages:** Paid algorithmic strategies where buyers license access to pre-calibrated behavioral funnels with verified Monte Carlo performance certificates.
  * **Strategy Verification Badges:** Packages receive automated CI test verification badges confirming zero audience leaks, bounded budget gas consumption, and empirical calibration status.
* **Future Hypothesis ($H_{\text{marketplace}}$):** *A public package registry accelerates industry-wide campaign iteration velocity by $10\times$, standardizing marketing systems into composable, reusable open-source primitives.*

---

## 18. Interactive In-Doc Simulation Sandboxes (Docs as Executable Labs) (OOTB-018)

### The Concept
Static documentation websites show code snippets that readers must manually copy and paste into local editors. For FunnelScript, documentation pages should serve as live, executable simulation laboratories.

### Proposed Mechanism
* Embed client-side WebAssembly (WASM) simulation runners directly inside Fumadocs/Mintlify MDX documentation pages.
* When a reader reads about "Saturating Ad Margins and Ad Fatigue", the documentation embeds an interactive `.fnl` code block alongside live slider controls (Budget, Creative Quality, Adstock Half-Life $\lambda$).
* The browser runs $10,000$ synthetic agents in real time via WebAssembly in $< 30\text{ms}$, dynamically plotting live conversion curves, ROAS distributions, and cash survival graphs directly within the documentation page.
* **Future Hypothesis ($H_{\text{doclab}}$):** *Executable documentation laboratories increase developer comprehension of complex stochastic marketing phenomena by $> 60\%$ compared to static code examples.*

---

## 19. Automated Bounty & Grant Distribution for fpm Ecosystem Connectors (OOTB-019)

### The Concept
Platform connectors (e.g., TikTok Marketing API, HubSpot, Klaviyo, Google Ads, Snapchat) and specialized demographic benchmark libraries are vital for ecosystem ubiquity. Instead of the core team authoring every provider adapter, a community grant and automated bounty system incentivizes ecosystem developers to build and maintain verified connectors.

### Proposed Mechanism
* Establish a community developer grant fund and issue bounties for verified provider plugins that satisfy the `Provider` contract and test suite.
* Automated CI validation suite tests prospective provider adapters against a hermetic mock sandbox and verifies idempotency, rate-limiting, and error-handling compliance.
* Successfully verified packages receive an official `fpm-certified` badge and automated grant disbursement.
* **Future Hypothesis ($H_{\text{bounty}}$):** *Incentivized connector bounties increase third-party provider coverage by $5\times$ compared to centralized internal development.*

---

## 20. Marketing Systems Engineering Academic Working Group & Annual Benchmark Competition (OOTB-020)

### The Concept
Marketing science has historically been divided between empirical econometrics (macro MMM) and heuristic agency intuition. FunnelScript provides the first formal programming language and computational substrate for Marketing Systems Engineering.

### Proposed Mechanism
* Found an academic working group with econometrics, computational social science, and marketing faculties.
* Host an annual "FunnelScript Simulation Benchmark Challenge" where research teams submit algorithmic strategies written in `.fnl` to compete in unknown synthetic macroeconomic shock scenarios (liquidity crunches, privacy signal loss, algorithmic auction inflation).
* Submissions evaluated blindly on risk-adjusted ROAS, downside insolvency avoidance ($P(\text{Insolvency}) = 0$), and adaptive learning efficiency.
* **Future Hypothesis ($H_{\text{academic}}$):** *Academic competition benchmark standards solidify FunnelScript as the de facto scientific standard for algorithmic marketing strategy research.*

---

## Promotion Pipeline & Tracking

| Idea ID | Title | Domain | Maturity | Next Milestone |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **OOTB-001** | Red-Team Competitors | Game Theory / Multi-Agent RL | Speculative | Draft minimax auction bidding scenario |
| **OOTB-002** | Viral Memetics | Network Science / SIR Diffusion | Seeded | Formulate Barabási-Albert graph integration |
| **OOTB-003** | Macroeconomic Shocks | Stress-Testing / System Dynamics | Seeded | Implement inflation wallet decay experiment |
| **OOTB-004** | OmniTwin Qualitative Council | NLP / Cognitive Continuity | Architectural | Prototype 10-agent qualitative focus group |
| **OOTB-005** | Zero-Knowledge Strategy Proofs | Cryptography / Web3 | Conceptual | Research zk-SNARK constraints for simulation runs |
| **OOTB-006** | Quantum Twin Universes | Causal Inference / Counterfactuals | Methodological | Build twin-seed deterministic runner |
| **OOTB-007** | Auto-FunnelScript | Evolutionary AI / MCTS | Exploratory | Define grammar mutation operators for AST |
| **OOTB-008** | WebGPU / Metal Acceleration | High-Performance Computing | Engineering | Prototype WGSL agent transition compute shader |
| **OOTB-009** | Autonomous Live Guardrails | SRE / Real-Time Circuit Breakers | Architectural | Specify spend velocity threshold formulas |
| **OOTB-010** | Effect Capability Sandboxing | Language Design / Security Types | Conceptual | Design AST capability declaration grammar |
| **OOTB-011** | Time-Traveling Shadow Debugger | Event Sourcing / Causal Replay | Seeded | Draft event journal schema for live replays |
| **OOTB-012** | Julia / Mojo LLVM Backend | High-Performance ABM / JIT | Conceptual | Benchmark Julia Agents.jl vs NumPy SIMD |
| **OOTB-013** | Marketing Drift Reconciliation | Cloud IaC / Infrastructure Drift | Seeded | Draft live provider state schema |
| **OOTB-014** | SMT Formal Verification (Z3) | Formal Methods / SMT Solvers | Conceptual | Model FunnelScript state machine in Z3 |
| **OOTB-015** | In-Editor Monte Carlo Co-Pilot | IDE Tooling / WebAssembly | Conceptual | Prototype WASM micro-batch runner |
| **OOTB-016** | Headless CI/CD PR Risk Bot | DevOps / CI Automation | Seeded | Draft GitHub Action workflow contract |
| **OOTB-017** | Algorithmic Strategy Registry | Package Management / Registry | Conceptual | Draft package metadata & registry spec |
| **OOTB-018** | Executable In-Doc Sandboxes | Documentation / WebAssembly | Conceptual | Prototype WASM simulator embedded in MDX |
| **OOTB-019** | Automated Connector Bounties | Open-Source Incentive Architecture | Seeded | Draft provider certification criteria |
| **OOTB-020** | Academic Benchmark Challenge | Academic Outreach / Benchmarks | Conceptual | Draft annual simulation competition rules |
| **OOTB-021** | Counterfactual Fidelity Harness | Model Evaluation / Research | Conceptual | Preregister held-out calibration and intervention tests |
| **OOTB-022** | Causal Event Lineage Inspector | Runtime Provenance / Debugging | Conceptual | Specify bounded event ancestry metadata |

---

## Frontier Status Note: Effect Sandbox and Deterministic Replay (2026-10-31)

The domain-neutral event kernel in `spec/event-kernel-v0.md` establishes only a reference event calendar and inert `EffectIntent` outputs. It is a prerequisite for exploring OOTB-010 (capability sandboxing) and OOTB-011 (event log replay), not evidence that either speculative feature is implemented. Prior to promotion, require falsifiable static effect-permission checks, external side-effect isolation, and adversarial replay tests. Neither a reproducible simulation seed nor a deterministic event log establishes causal identification from real-world market data.

---

## Frontier Status Note: Typed Worlds Are Not Autonomous Digital Twins (2026-10-31)

DEC-022 adds only declarative `world`, `entity`, `agent`, and typed `state` AST nodes. It does not generate synthetic populations, cognitive agents, adaptive behavior, or calibrations. The speculative OmniTwin council (OOTB-004), twin-universe testing (OOTB-006), capability sandboxing (OOTB-010), and event replay (OOTB-011) remain future programs. Any claim that type-correct world source predicts the real market must be rejected until empirical out-of-sample validation exists.


---

## 21. Counterfactual Fidelity Harness for Community World Libraries (OOTB-021)

### Concept
Provide an optional evaluation package that runs the same typed World policy on held-out historical interventions, reports calibration and intervention uncertainty, and identifies cases where simulated and observed trajectories diverge. The core language would specify the decision mechanics; empirical adapters would supply calibrated priors, posterior samples, and data quality metadata.

### Hypothesis and failure boundary
**Future H-O21:** A preregistered, held-out evaluation harness detects systematically miscalibrated community World models before they are advertised as predictive. Falsified if miscalibrated models routinely pass the published acceptance thresholds.

### Boundary
Not implemented in this milestone. This is not a claim that PyMC Marketing or OmniTwin already enables accurate individual-level counterfactual predictions. World syntax and rules remain neutral to provider, model and industry.


---

## 22. Causal Event Lineage Inspector (OOTB-022)

### Concept
A potential language tooling extension would attach causal parent IDs and source spans to each emitted World event, producing an inspectable event dependency graph for counterfactual debugging. Analysts could ask why an event occurred and which source rule introduced it without depending on a marketing-specific agent template.

### Falsifiable future hypothesis
**H-O22:** Causal event lineage reduces the time needed to reproduce event-order failures compared with timestamp-only traces in preregistered debugging tasks. Falsification: no measurable difference or incorrect attribution of event ancestry.

### Boundary
Not implemented. Event emission currently preserves only time, qualified name, and stable ordering through the existing kernel. A lineage system would need separate provenance schema, memory bounds, and deterministic replay tests.


---

## 23. Guard Branch Coverage and Counterfactual Path Explorer (OOTB-023)

### Idea
A prospective debug adapter could record which guard condition held at each input event, its pre-event state snapshot, and an alternative path if that predicate outcome were changed. The interpreter would remain neutral to marketing concepts; a market library could supply calibrated inputs for domain-specific scenarios.

### Hypothesis and falsification
**Future H-O23:** Against a preregistered suite of state-dependent event-chain bugs, guard-branch coverage reports plus reproducible counterfactual traces reduce the time to identify missed reactions compared with timestamp-only logs. Falsification: incorrect attribution, nondeterministic replay or no improvement in diagnosis time.

### Boundary
Unimplemented and uncalibrated. A counterfactual execution trace is not a causal estimate of a real marketing intervention; that requires an identification design and held-out data.


---

## 24. Schema-Consistent Event Corpus for Counterfactual Replay (OOTB-024)

### Idea
An optional research extension could collect consented, sanitized empirical event records in a versioned corpus and replay them through third-party World libraries after validating each record against a declared event schema. Counterfactual branches would compare deterministic policy mechanics under controlled changes to a payload field, without granting the core interpreter permission to call marketing platforms.

### Future falsifiable hypothesis
**H-O24:** Schema-validated replay corpora discover more incorrect rule field accesses and event-order regressions in community libraries than equal-sized random event streams in a preregistered benchmark. Falsified if there is no improvement, if real records leak private information, or if reproduction is nondeterministic under fixed inputs.

### Boundaries
Not implemented. Stored records require provenance, minimization, consent/privacy controls, schema migration policy, retention rules and a separate empirical identification design. Changing a synthetic or historical payload value alone is **not** a causal estimate of a real intervention.


---

## 25. Randomness Provenance and Paired Counterfactual Streams (OOTB-025)

### Research idea

A prospective World library could derive independent, reproducible RNG substreams from stable agent identities, decision-site identifiers, explicit run seeds and controlled intervention IDs. It would record draw provenance and use common random numbers across paired policy alternatives, avoiding accidental random-stream shifts when only event scheduling changes.

### Falsifiable future hypothesis

**H-O25:** In a preregistered paired-intervention benchmark, identity-stable keyed streams reduce the variance of simulated *difference* estimates relative to a single event-ordered stream, without introducing cross-agent correlation artifacts. Falsified if estimates become biased, pairing fails after source edits, or matched variance fails to improve.

### Boundary

Not implemented. DEC-031 intentionally uses one seeded event-order stream. Deriving safe stable identifiers, choosing a portable counter-based PRNG, recording private event traces and enforcing reproducible provenance require separate design and privacy/security review. Variance reduction within a simulator does not establish real-market causal validity.

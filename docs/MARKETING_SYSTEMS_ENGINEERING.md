# Marketing Systems Engineering: The Discipline, Persona & Mental Models

> Foundational manifesto on the convergence of systems engineering, Bayesian econometrics, and digital marketing.

---

## 1. The Emergence of the Marketing Systems Engineer

Modern performance marketing has reached an inflection point. As customer acquisition costs rise, attribution tracking degrades, and ad auction dynamics become increasingly automated, traditional heuristic marketing practices fail.

A new practitioner has emerged at the intersection of business strategy and software engineering: the **Marketing Systems Engineer (MSE)** (often titled *Growth Data Scientist*, *Marketing Infrastructure Engineer*, or *Quantitative Media Director*).

```
                      ┌───────────────────────────────┐
                      │    Marketing Systems Engineer │
                      │              (MSE)            │
                      └───────────────┬───────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
│ Performance Marketing │ │ Bayesian Econometrics │ │  Systems Programming  │
│  - Media Buying       │ │  - Adstock Decay (λ)  │ │  - Declarative DSLs   │
│  - CAC / ROAS Goals   │ │  - Hill Saturation (K)│ │  - Discrete-Event Sim │
│  - Creative Fatigue   │ │  - Posterior Priors   │ │  - Static AST Linting │
└───────────────────────┘ └───────────────────────┘ └───────────────────────┘
```

---

## 2. The Core Operational Friction

Marketing Systems Engineers currently operate in an environment characterized by fragile tooling:

| Current Tooling | Core Failure Mode | Consequence |
| :--- | :--- | :--- |
| **Spreadsheets (Excel / Sheets)** | No version control, untyped cells, silent formula errors, manual copy-paste | Undetected financial miscalculations costing millions in wasted spend |
| **Ad-Hoc Python / Jupyter Notebooks** | Fragile glue scripts, unvectorized slow loops, lack of production contracts | Simulation code remains trapped on local laptops; cannot be integrated into CI/CD |
| **Ad Platform Dashboards (Meta, Google)** | Black-box reporting, post-hoc vanity metrics, conflicting attribution claims | Strategies are tested live with real enterprise capital under catastrophic risk |

FunnelScript replaces this fragmented workflow with a unified standard: **Marketing as Code (MaC)**.

---

## 3. Foundational Mental Models (Behavioral & Psychological Foundations)

Marketing Systems Engineering applies rigorous psychological principles and mental models to marketing architecture:

### 3.1 Inversion (Carl Jacobi / Charlie Munger)
* **The Heuristic:** *"Invert, always invert. Instead of asking how to achieve a $5\times$ ROAS, ask: What would guarantee total financial ruin?"*
* **FunnelScript Application:** The simulation engine prioritizes downside catastrophe stress-testing over point forecasts. It calculates the Cash Insolvency Probability:
  $$P(\text{Insolvency}) = \mathbb{P}\left(\min_{t \in [0, T]} \text{Cash}(t) < 0\right)$$
  If settlement latency ($\Delta_{\text{settle}}$) causes cash balance to cross zero during an aggressive scaling sprint, the strategy is rejected before launch.

### 3.2 Jobs to Be Done (Clayton Christensen)
* **The Heuristic:** Customers do not buy software features; they "hire" an artifact to complete a high-stakes job.
* **FunnelScript Application:** The MSE hires FunnelScript to eliminate downside risk and establish mathematical proof of strategy viability before presenting marketing budgets to the CFO.

### 3.3 Second-Order Thinking (Howard Marks)
* **The Heuristic:** First-order thinking asks: *"What if we offer a 20% discount on cart abandonment?"* Second-order thinking asks: *"If consumers learn that abandoning a cart triggers a 20% discount, how will that alter aggregate baseline purchasing behavior?"*
* **FunnelScript Application:** Virtual agents track historical discount exposure. The engine detects behavioral cannibalization, proving when automated cart-abandonment discounts erode net margins rather than driving incremental revenue.

### 3.4 Local vs. Global Optima
* **The Heuristic:** Optimizing micro-variables (e.g., button colors or email subject lines) is futile if the overall funnel architecture suffers from a structural bottleneck (Theory of Constraints).
* **FunnelScript Application:** FunnelScript models the entire multi-touchpoint directed graph, identifying structural traffic leaks, audience saturation thresholds, and attribution dead-ends.

---

## 4. The Marketing Advisory Council Synthesis

Synthesizing historical marketing discipline through the lens of computational systems:

### Seth Godin: Permission & Smallest Viable Audience
* **Principle:** Interruption marketing is a tax. Scaled broadcast spam degrades audience trust over time.
* **FunnelScript Implementation:** The compiler enforces audience conservation and tracks audience fatigue vectors. Strategies that repeatedly hammer cold audiences without progressive permission transitions are flagged by the linter.

### Byron Sharp: Empirical Brand Science & Mental Availability
* **Principle:** Consumer behavior obeys empirical laws of repeat buying (Dirichlet multinomial models) and physical/mental availability. Fictional, highly detailed customer "personas" are uncalibrated illusions.
* **FunnelScript Implementation:** FunnelScript rejects arbitrary LLM-generated narrative personas in favor of parsimonious, mathematically calibrated micro-foundations (10–15 measurable state variables calibrated against historical Bayesian posteriors).

### April Dunford: Positioning Against Competitive Alternatives
* **Principle:** Positioning is defined by what the customer would do if your product did not exist.
* **FunnelScript Implementation:** FunnelScript positions itself not as another BI visualization dashboard or analytics tracker, but as the compiler and static safety verification layer for marketing execution.

### Rory Sutherland: Psycho-Logic & Behavioral Economics
* **Principle:** Human decision-making does not obey neat classical economic rationality. Context, framing, and perceived fairness dictate purchase thresholds.
* **FunnelScript Implementation:** The agent mind incorporates non-linear psychographic functions, modeling loss aversion, ad fatigue decay ($\lambda$), and dynamic threshold barriers.

---

## 5. The Day-in-the-Life Workflow of a Marketing Systems Engineer

```
1. Author Strategy (.fnl)  ──>  2. Static Verification  ──>  3. Stochastic Simulation  ──>  4. Deployment Plan
   [Declarative Code]            [funnelscript check]         [funnelscript simulate]        [funnelscript plan]
   - Audiences                   - Mass Conservation          - 100,000 Virtual Agents       - Provider Dags
   - Touchpoints                 - Acyclic Graphs             - ROAS Distribution            - Idempotent Sync
   - Budget Caps                 - Budget Gas Ceilings        - Insolvency Risk P(Ruin)      - Bounded Spend
```

1. **Author:** Strategy written as declarative `.fnl` code in VS Code with syntax highlighting and LSP error checking.
2. **Verify:** `funnelscript check campaign.fnl` validates DAG topology, guarantees mass conservation ($\sum P(\text{state}) = 1.0$), and verifies bounded spend limits in $< 30\text{ms}$.
3. **Simulate:** `funnelscript simulate campaign.fnl --agents 100000` evaluates 100,000 virtual agents across 100 Monte Carlo trials, computing Value at Risk ($\text{VaR}_{95}$) and liquidity ruin probability.
4. **Deploy:** Strategy is committed to Git, reviewed via Pull Request diffs, and executed with cryptographic idempotency keys across platform APIs.

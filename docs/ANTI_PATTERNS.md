# Marketing Systems Anti-Patterns Catalog

This catalog outlines structural, behavioral, and financial anti-patterns detected and guarded against by the FunnelScript Compiler and Simulation Runtime.

---

## 1. The Discount Cannibalization Trap (Defect Code: FS-RISK-01)

### Pattern Description
An e-commerce business deploys an aggressive 15%–20% cart abandonment discount email triggering within 1–2 hours of cart abandonment. 

### Mechanism of Failure
A significant percentage of prospective buyers who abandoned the cart were already high-affinity brand advocates ($\alpha_i > 0.75$) with high purchase intent who merely got distracted or intended to complete purchase on their desktop. 

The immediate discount does not generate incremental net-new customers; instead, it subsidizes purchases that would have occurred at full price, eroding gross margin without lifting unit volume.

### Mathematical Representation
Let $\chi$ be the cannibalization rate:
$$\chi = \frac{\sum_{i \in \text{ConvertedWithDiscount}} \mathbb{I}(\alpha_i \ge 0.75)}{N_{\text{converted}}}$$

If $\chi > 0.10$ ($10\%$), the strategy is flagged by FunnelScript Telemetry as margin-eroding.

### Remediation
1. Introduce dynamic segmentation: Restrict discount vouchers exclusively to high-elasticity, low-affinity cohorts ($\beta_i > 0.65, \alpha_i < 0.40$).
2. Increase time delay $\Delta t$ before discount issuance (e.g. from 2 hours to 24 hours).
3. Use non-monetary incentives (free shipping, extended warranty) instead of price slashing.

---

## 2. The Settlement Liquidity Mirage (Defect Code: FS-RISK-02 / FS501)

### Pattern Description
A high-growth direct-to-consumer brand models a campaign forecasting a $3.0\times$ ROAS. Based on this projection, marketing scales daily ad spend from $\$500/\text{day}$ to $\$5,000/\text{day}$. 

Three weeks later, the business runs out of cash and the credit line is maxed out, despite "profitable" dashboard metrics.

### Mechanism of Failure
Ad platforms (Meta, Google) bill ad spend immediately or within 24–48 hours. Conversely, payment gateways (Stripe, Shopify Payments, PayPal, Klarna) enforce clearance lags $\Delta_{\text{settle}} \in [2, 7]$ days, with rolling reserves held up to 90 days.

If initial working capital $C(0)$ cannot buffer the settlement deficit:
$$C(t) = C(t-1) - \text{Spend}(t) + \text{SettledRevenue}(t - \Delta_{\text{settle}})$$
$$C(t) \le 0 \implies \text{Ad Auction Halts (Insolvency)}$$

Even with infinite prospective ROAS, the merchant halts ad spend mid-cycle due to technical insolvency.

### Remediation
1. Adjust `initial_cash` or `settlement_delay_days` in the `budgets` entity to reflect true merchant accounts.
2. Pace campaign ramp-up linearly matching the cash settlement velocity $\frac{\partial C}{\partial t}$.

---

## 3. The Recurrent Attribution Deadlock (Defect Code: FS202)

### Pattern Description
In complex multi-channel marketing stacks, remarketing rules frequently route users into cycles:
- User clicks Google Ad $\to$ Visits Landing Page $\to$ Retargeted via Meta Ad $\to$ Retargeted back to Google Search $\to \dots$

### Mechanism of Failure
This forms a directed cyclic graph in the attribution network. In production, this causes:
1. Double-counting attribution across ad platforms.
2. Ad fatigue compounding ($e^{-\kappa \cdot \text{exposures}}$) until conversion probability drops to near zero.
3. Wasteful capital expenditure as platforms bid against each other for the identical user identity.

### Mathematical Invariant
The state transition network of touchpoints must form a Directed Acyclic Graph (DAG) for forward steps:
$$\mathcal{G} = (\mathcal{V}, \mathcal{E}), \quad \text{TarjanSCC}(\mathcal{G}) = \emptyset$$

### Remediation
Enforce explicit absorbing terminal states (`CONVERTED`, `CHURNED`) and prohibit cyclic ad-to-ad routing without an intervening conversion surface.

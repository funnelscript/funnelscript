# `leadgen/sales_capacity` (v0.1.0)

**Flagship High-Ticket Lead Generation & Sales Capacity Constraint Package for FunnelScript.**

Models the operational breakdown that static spreadsheets miss: doubling ad spend when a human sales team is near full capacity causes lead backlogs to accumulate, dragging `speed_to_lead` from minutes to hours. This delay triggers exponential lead cooling, collapsing contact and close rates and sending **Effective CAC** skyrocketing even when ad platform CPL appears healthy.

---

## 1. The Capacity-Decay Feedback Loop

```
Ad Spend Ramp ──> Inbound Leads Spike ──> Exceeds Rep Capacity (4 reps x 12/day)
                                                  │
                                                  ▼
                                           Queue Backlog Builds
                                                  │
                                                  ▼
                                      Speed-to-Lead: 15m ──> 6+ Hours
                                                  │
                                                  ▼
                                     Lead Cooling: CVR(t) = CVR_0 * 2^(-t / t_half)
                                                  │
                                                  ▼
                                      Contact & Close Rates Collapse
                                                  │
                                                  ▼
                                    Effective CAC Spikes | Net Margin Turns Negative
```

### Operational Accounting Invariant
$$\text{Starting Cash} + \text{Collected Inflows} - (\text{Ad Spend} + \text{Payroll} + \text{Commissions} + \text{Hiring Fees}) = \text{Ending Settled Cash}$$
Every cash movement reconciles to the exact cent ($0.00$ float drift) against `funnelscript.stdlib.marketing.ledger.MarketingLedger`.

---

## 2. Parameter Reference Table

| Parameter | Type / Unit | Default | Valid Range | Operational Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `base_daily_ad_spend` | Currency (`USD`) | `$2,000.00` | $\ge 0$ | Baseline daily advertising spend |
| `scale_daily_ad_spend`| Currency (`USD`) | `$5,000.00` | $\ge 0$ | Scaled daily spend during growth push |
| `deal_value` | Currency (`USD`) | `$4,500.00` | $> 0$ | Average high-ticket deal revenue per closed customer |
| `active_reps` | Count (`reps`) | `4` | $> 0$ | Active sales reps available at $t=0$ |
| `max_leads_per_rep_per_day` | Count (`leads/rep/day`) | `12` | $> 0$ | Maximum new qualified outreach capacity per rep |
| `baseline_response_minutes` | Duration (`minutes`) | `15.0` | $> 0$ | Nominal speed-to-lead under zero queue backlog |
| `lead_decay_half_life_minutes` | Duration (`minutes`)| `45.0` | $> 0$ | Elapsed time causing 50% drop in contact probability |
| `baseline_contact_rate` | Ratio | `0.70` | `(0, 1]` | Maximum reachable contact rate under prompt SLA |
| `qualified_appointment_rate` | Ratio | `0.40` | `(0, 1]` | Conversion of contacted leads into qualified meetings |
| `deal_close_rate` | Ratio | `0.25` | `(0, 1]` | Conversion of qualified appointments into closed deals |
| `sales_cycle_days` | Duration (`days`) | `14` | $\ge 0$ | Average days from first contact to deal signing |
| `invoice_collection_days` | Duration (`days`) | `7` | $\ge 0$ | Collection delay before signed deal cash hits bank |
| `monthly_rep_salary` | Currency (`USD`) | `$4,000.00` | $\ge 0$ | Fixed base compensation per representative |
| `sales_commission_rate`| Ratio | `0.08` | `[0, 0.50]` | Variable commission paid on collected deal revenue |
| `hiring_cost_per_rep` | Currency (`USD`) | `$2,500.00` | $\ge 0$ | Recruiting, onboarding, and seat provisioning cost |
| `planned_new_hires` | Count (`reps`) | `0` | $\ge 0$ | Additional reps hired during the campaign |
| `onboarding_ramp_days` | Duration (`days`) | `14` | $\ge 0$ | Days required for new hires to achieve 100% capacity |
| `ramp_productivity_rate` | Ratio | `0.40` | `[0, 1]` | Productive throughput fraction during onboarding |

---

## 3. Minimal 15-Line Usage Snippet

```funnelscript
world SalesCapacityStressRun {
  // Import the flagship leadgen/sales_capacity package from fpm
  import "leadgen/sales_capacity" as SalesCap;

  // The imported SalesCap entity tracks:
  // - active_reps, daily_rep_capacity, total_team_capacity
  // - backlog_depth, effective_speed_to_lead, total_leads_generated
  // - total_leads_contacted, qualified_appointments, closed_won_deals
  // - cash_balance, booked_revenue, collected_revenue, accounts_receivable
  //
  // Driven by discrete events:
  // DailyAdSpend, ServiceQueue, ScheduleDeal, WinDeals, CollectDeals, PayDailyPayroll, ExpandTeam
}
```

---

## 4. Python Simulation Execution

```python
from packages.leadgen.sales_capacity.engine import SalesCapacitySimulator, SalesCapacityConfig
from decimal import Decimal

# Run a 30-day capacity stress test scaling spend from $2,000 to $5,000 with 4 fixed reps
config = SalesCapacityConfig(
    base_daily_ad_spend=Decimal("2000.00"),
    scale_daily_ad_spend=Decimal("5000.00"),
    active_reps=4,
    max_leads_per_rep_per_day=12,
    lead_decay_half_life_minutes=45.0,
)
result = SalesCapacitySimulator(config).run(seed=42)

print(f"Blended CPL: ${result.blended_cpl}")
print(f"Peak Queue Backlog: {result.peak_queue_backlog} leads")
print(f"Avg Speed-to-Lead: {result.avg_speed_to_lead_minutes} minutes")
print(f"Effective Close Rate: {result.effective_close_rate:.2%}")
print(f"Effective CAC: ${result.effective_cac:,.2f}")
print(f"Net Margin: ${result.net_contribution_margin:,.2f}")
```

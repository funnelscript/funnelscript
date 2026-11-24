# `ecommerce/d2c_scale` (v0.1.0)

**Flagship Direct-to-Consumer (D2C) E-Commerce & Working Capital Scale Package for FunnelScript.**

Models the critical failure mode that static spreadsheets (Excel/Sheets) miss: a scaling brand achieving strong nominal advertising ROAS ($>3.0\times$) that still experiences catastrophic cash insolvency due to immediate daily ad spend velocity, deferred Cash-on-Delivery (COD) remittance cycles ($\Delta_{\text{settle}} = 7\text{--}21\text{ days}$), gateway rolling reserves, and Return-to-Origin (RTO) round-trip shipping drag.

---

## 1. Accounting & Cash Flow Mechanics

In static models, $\text{Revenue} = \text{Ad Spend} \times \text{ROAS}$ is treated as immediate. In physical reality:

```
[Ad Networks] ──(Immediate Daily Outflow)──> Cash Balance
                                                   ▲
[Prepaid Gateway] ──(3-Day Lag - 5% Reserve)───────┤
                                                   │
[COD Couriers] ──(4-Day Transit + 7-Day Remittance)┘
        │
        └──[RTO: 18%] ──(Return Loss: Forward + Reverse Shipping)──> Cash Bleed
```

### Cash Realization Invariant
$$\text{Starting Cash} + \text{Settled Inflows} - \text{Paid Outflows} = \text{Ending Settled Cash}$$
Every transaction reconciles with $0.00$ float drift against `funnelscript.stdlib.marketing.ledger.MarketingLedger`.

---

## 2. Parameter Reference Table

| Parameter | Type / Unit | Default | Valid Range | Business Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `base_daily_ad_spend` | Currency (`USD`) | `$5,000.00` | $\ge 0$ | Baseline daily advertising expenditure |
| `scale_daily_ad_spend`| Currency (`USD`) | `$10,000.00`| $\ge 0$ | Scaled daily spend during seasonal push |
| `order_value` | Currency (`USD`) | `$85.00` | $> 0$ | Average Order Value (AOV) |
| `hill_k` | Currency (`USD`) | `$12,000.00`| $> 0$ | Half-saturation spend level |
| `hill_alpha` | Scalar | `0.85` | `(0, 2.5]` | Curvature governing diminishing returns |
| `adstock_decay` | Ratio | `0.40` | `[0, 1)` | Daily advertising carryover memory |
| `cogs_rate` | Ratio | `0.35` | `[0, 1)` | Cost of Goods Sold percentage |
| `cod_share_rate` | Ratio | `0.65` | `[0, 1]` | Proportion of orders selecting COD |
| `cod_confirmation_rate`| Ratio | `0.88` | `(0, 1]` | Rate of pre-dispatch customer confirmation |
| `cod_rto_rate` | Ratio | `0.18` | `[0, 1)` | Shipped COD Return-to-Origin rate |
| `forward_shipping_cost`| Currency (`USD`) | `$4.50` | $\ge 0$ | Outbound delivery fee per dispatched order |
| `return_shipping_cost` | Currency (`USD`) | `$3.50` | $\ge 0$ | Inbound reverse logistics fee per RTO |
| `delivery_delay_days` | Duration (`days`)| `4` | $\ge 0$ | Transit duration before delivery attempt |
| `cod_remittance_days` | Duration (`days`)| `7` | $\ge 0$ | Courier remittance delay after delivery |
| `gateway_settle_days` | Duration (`days`)| `3` | $\ge 0$ | Payment gateway deposit delay |
| `rolling_reserve_rate`| Ratio | `0.05` | `[0, 0.5)` | Gateway holdback for dispute reserve |
| `initial_cash` | Currency (`USD`) | `$15,000.00`| $\ge 0$ | Starting liquid bank balance |
| `min_safety_cash` | Currency (`USD`) | `$5,000.00` | $\ge 0$ | Liquidity floor triggering runway breach |

---

## 3. Minimal 15-Line Usage Snippet

```funnelscript
world D2CSeasonalScaleStress {
  // Import the flagship d2c_scale package from fpm
  import "ecommerce/d2c_scale" as D2C;

  // The imported D2C entity tracks:
  // - cash_balance, accounts_receivable, rolling_reserve
  // - booked_gmv, settled_cash, total_ad_spend, total_shipping_cost
  // - orders_count, delivered_count, rto_count, cash_runway_breached
  //
  // Driven by events:
  // DailyAdSpend, NewOrder, OrderDelivered, OrderRTO, GatewaySettlement, CODRemittance
}
```

---

## 4. Simulation Execution Example

```python
from packages.ecommerce.d2c_scale.engine import D2CScaleSimulator, D2CScaleConfig
from decimal import Decimal

# Run a 30-day liquidity stress test doubling spend from $5,000 to $10,000
config = D2CScaleConfig(
    base_daily_ad_spend=Decimal("5000.00"),
    scale_daily_ad_spend=Decimal("10000.00"),
    cod_share_rate=Decimal("0.65"),
    cod_rto_rate=Decimal("0.18"),
    cod_remittance_days=7,
)
result = D2CScaleSimulator(config).run(seed=42)

print(f"Paper ROAS: {result.paper_roas}x")
print(f"Min Cash Trough: ${result.min_cash_trough:,.2f} on Day {result.min_cash_trough_day}")
print(f"Cash Runway Breached: {result.cash_runway_breached}")
print(f"Double-Entry Ledger Conserved: {result.ledger_conserved}")
```

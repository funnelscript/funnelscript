# FunnelScript Specification (Schema Draft 2020-12)

FunnelScript documents (`.fnl.json` or `.fnl`) encode marketing architectures as declarative, executable State Transition Networks.

---

## 1. Document Structure

```json
{
  "$schema": "https://marketing-lang.org",
  "strategy_name": "<string>",
  "metadata": {
    "author": "<string>",
    "industry": "<string>",
    "currency": "<string>"
  },
  "environment": {
    "market_volatility": "low" | "moderate" | "high",
    "competitor_activity": "passive" | "moderate" | "aggressive"
  },
  "entities": {
    "budgets": { ... },
    "audiences": [ ... ],
    "touchpoints": [ ... ]
  },
  "logic_flow": [ ... ],
  "simulation_engine": { ... }
}
```

---

## 2. Entities Specification

### `budgets`
| Field | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `total_budget` | `float` | Yes | Global ad spend ceiling ($) over the simulation horizon. |
| `max_cpc_limit` | `float` | Yes | Maximum cost-per-click willing to pay at auction. |
| `initial_cash` | `float` | No (default: 10,000) | Liquid cash available at day 0 before receivables settle. |
| `settlement_delay_days` | `int` | No (default: 3) | Payment processor clearance lag ($\Delta_{\text{settle}}$ days). |

### `audiences`
Ensembles of synthetic agents initialized from psychographic priors:
| Field | Type | Description |
| :--- | :---: | :--- |
| `id` | `string` | Unique identifier (e.g. `aud_cold`). |
| `name` | `string` | Human-readable name. |
| `type` | `"cold" \| "warm" \| "retargeting"` | Cold audiences begin in `COLD` state; warm in `AWARE`. |
| `estimated_size` | `int` | Physical TAM size. |
| `attributes.brand_affinity` | `float [0.0, 1.0]` | Baseline goodwill and trust toward the brand ($\alpha$). |
| `attributes.price_sensitivity` | `float [0.0, 1.0]` | Resistance to price and friction ($\beta$). |
| `attributes.fomo_index` | `float [0.0, 1.0]` | Receptivity to urgency, scarcity, and social proof ($\gamma$). |

### `touchpoints`
Surfaces where consumers interact with marketing assets:
- **`paid_traffic`**: Incurs cost per click; governed by `base_cpc` and `ad_creative_score`.
- **`conversion_surface`**: Landing pages or checkout steps governed by `base_conversion_rate`.
- **`retargeting_channel`**: Owned media (Email, SMS) governed by `base_open_rate`.

---

## 3. Logic Flow Statements

Sequential and conditional nodes evaluated across the multi-day timeline:

### `TriggerTraffic`
Directs audience flow through an ad surface to a destination landing page:
```json
{
  "step": 1,
  "action": "TriggerTraffic",
  "source": "aud_01",
  "via": "tp_meta_ads",
  "destination": "tp_landing_page"
}
```

### `ConditionalBranch`
Routes consumers depending on dynamic behavioral outcomes (e.g., cart abandonment):
```json
{
  "step": 2,
  "type": "ConditionalBranch",
  "condition": {
    "user_action": "AbandonCart",
    "time_elapsed": "2h"
  },
  "true_branch": [
    {
      "action": "ExecuteRetargeting",
      "channel": "tp_cart_email",
      "payload": {
        "offer_type": "Discount_15",
        "discount_percentage": 15
      },
      "expected_impact": {
        "conversion_boost": 0.021
      }
    }
  ],
  "false_branch": [
    {
      "action": "DoNothing"
    }
  ]
}
```

---

## 4. Simulation Engine Parameters

| Parameter | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `virtual_agents_count` | `int` | `10000` | Sample size for the Monte Carlo agent cohort. |
| `timeframe_days` | `int` | `14` | Duration of the campaign horizon. |
| `randomness_factor_sigma` | `float` | `0.15` | Market volatility standard deviation for ad auction price shocks. |
| `historical_data_weight` | `float` | `0.70` | Blending weight between historical priors and agent dynamics. |

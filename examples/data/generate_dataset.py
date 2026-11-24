"""Generates realistic 30-day multi-channel e-commerce campaign telemetry."""

import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

# Parameters
SEED = 42
random.seed(SEED)

START_DATE = datetime(2026, 10, 1)
DAYS = 30
AOV = 125.0  # Average Order Value
DELAY_DAYS = 3
GATEWAY_FEE = 0.029

# Channels: Meta Ads (V_max=12000, K_sat=3500, alpha=0.82), Google Search (V_max=15000, K_sat=4000, alpha=0.80)
# Days 1-15: Baseline spend (~$1200 on Meta, ~$1000 on Google)
# Days 16-30: Scaling spend (~$3500 on Meta, ~$3000 on Google) -> Demonstrates Saturation & Liquidity Crash

campaign_rows = []
settlement_rows = []
tx_id_counter = 10001

for d in range(DAYS):
    cur_date = START_DATE + timedelta(days=d)
    date_str = cur_date.strftime("%Y-%m-%d")
    is_scaling = d >= 15

    for channel, base_spend_mean, cpc_base, v_max, k_sat, alpha in [
        ("meta_ads", 3500.0 if is_scaling else 1200.0, 1.25, 12000.0, 3500.0, 0.82),
        ("google_search", 3000.0 if is_scaling else 1000.0, 1.85, 15000.0, 4000.0, 0.80),
    ]:
        # Spend with small day-to-day noise
        noise = random.gauss(0, 0.05)
        spend = round(base_spend_mean * (1.0 + noise), 2)
        cpc = round(cpc_base * (1.0 + random.gauss(0, 0.04) + (0.25 if is_scaling else 0.0)), 2)
        clicks = int(spend / cpc)
        impr = int(clicks / (0.022 + random.uniform(-0.003, 0.003)))

        # True non-linear Hill saturation response
        hill_rev = v_max * (math.pow(spend, alpha) / (math.pow(k_sat, alpha) + math.pow(spend, alpha)))
        # Conversions
        expected_conv = hill_rev / AOV
        conv = max(1, int(round(expected_conv * (1.0 + random.gauss(0, 0.06)))))
        rev = round(conv * AOV * (1.0 + random.gauss(0, 0.02)), 2)

        campaign_rows.append({
            "date": date_str,
            "channel": channel,
            "impressions": impr,
            "clicks": clicks,
            "spend": spend,
            "conversions": conv,
            "revenue": rev,
        })

        # Generate transaction settlement records
        settle_date = cur_date + timedelta(days=DELAY_DAYS)
        settle_str = settle_date.strftime("%Y-%m-%d")
        
        # Split daily revenue into individual transactions
        for _ in range(conv):
            tx_gross = round(rev / conv, 2)
            tx_fee = round(tx_gross * GATEWAY_FEE, 2)
            tx_net = round(tx_gross - tx_fee, 2)
            settlement_rows.append({
                "transaction_id": f"tx_{tx_id_counter}",
                "transaction_date": date_str,
                "settlement_date": settle_str,
                "gross_amount": tx_gross,
                "fee_amount": tx_fee,
                "net_amount": tx_net,
                "refund_amount": 0.0,
                "status": "settled",
            })
            tx_id_counter += 1

out_dir = Path("examples/data")
out_dir.mkdir(parents=True, exist_ok=True)

with open(out_dir / "ecommerce_campaign_30d.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "channel", "impressions", "clicks", "spend", "conversions", "revenue"])
    writer.writeheader()
    writer.writerows(campaign_rows)

with open(out_dir / "payment_settlement_logs.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["transaction_id", "transaction_date", "settlement_date", "gross_amount", "fee_amount", "net_amount", "refund_amount", "status"])
    writer.writeheader()
    writer.writerows(settlement_rows)

print(f"Generated {len(campaign_rows)} campaign rows and {len(settlement_rows)} settlement rows.")

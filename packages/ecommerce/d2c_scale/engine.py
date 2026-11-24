"""D2C Scale Flagship Simulation & Double-Entry Treasury Engine.

Models multi-channel acquisition, dual-track payment (Prepaid vs. COD),
courier logistics transit, RTO losses, and dual settlement lags.
Integrates directly with MarketingLedger to guarantee exact double-entry conservation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from funnelscript.stdlib.marketing.kernels import HillSaturation
from funnelscript.stdlib.marketing.ledger import (
    LedgerEntry,
    LedgerSnapshot,
    MarketingLedger,
)


def _to_decimal(val: float | Decimal | str) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


@dataclass(frozen=True)
class D2CScaleConfig:
    """Strictly bounded, dimensionally sound parameters for D2C Scale."""
    
    # Acquisition Parameters
    base_daily_ad_spend: Decimal = field(default_factory=lambda: Decimal("5000.00"))
    scale_daily_ad_spend: Decimal = field(default_factory=lambda: Decimal("10000.00"))
    scale_start_day: int = 1
    horizon_days: int = 30
    hill_v_max: float = 800.0  # Max daily orders ceiling
    hill_k: float = 12000.0   # Half-saturation spend
    hill_alpha: float = 0.85  # Curvature
    adstock_decay: float = 0.40  # Daily carryover memory
    cpc_base: Decimal = field(default_factory=lambda: Decimal("1.20"))
    order_value: Decimal = field(default_factory=lambda: Decimal("85.00"))

    # Unit Economics & Cohort Splits
    cogs_rate: Decimal = field(default_factory=lambda: Decimal("0.35"))
    cod_share_rate: Decimal = field(default_factory=lambda: Decimal("0.65"))
    cod_confirmation_rate: Decimal = field(default_factory=lambda: Decimal("0.88"))
    cod_rto_rate: Decimal = field(default_factory=lambda: Decimal("0.18"))
    prepaid_refund_rate: Decimal = field(default_factory=lambda: Decimal("0.03"))

    # Logistics & Costs
    forward_shipping_cost: Decimal = field(default_factory=lambda: Decimal("4.50"))
    return_shipping_cost: Decimal = field(default_factory=lambda: Decimal("3.50"))
    packaging_cost: Decimal = field(default_factory=lambda: Decimal("1.00"))
    delivery_delay_days: int = 4
    rto_restock_days: int = 7

    # Treasury & Settlement Lags (Delta_settle)
    gateway_fee_rate: Decimal = field(default_factory=lambda: Decimal("0.029"))
    gateway_settle_days: int = 3
    rolling_reserve_rate: Decimal = field(default_factory=lambda: Decimal("0.05"))
    reserve_release_days: int = 90
    cod_fee_rate: Decimal = field(default_factory=lambda: Decimal("0.020"))
    cod_remittance_days: int = 7

    # Working Capital & Solvency Safety
    initial_cash: Decimal = field(default_factory=lambda: Decimal("15000.00"))
    min_safety_cash: Decimal = field(default_factory=lambda: Decimal("5000.00"))
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate parameter boundaries and economic sanity."""
        if self.base_daily_ad_spend < Decimal("0.00"):
            raise ValueError(f"base_daily_ad_spend must be >= 0, got {self.base_daily_ad_spend}")
        if self.scale_daily_ad_spend < Decimal("0.00"):
            raise ValueError(f"scale_daily_ad_spend must be >= 0, got {self.scale_daily_ad_spend}")
        if self.horizon_days <= 0 or self.horizon_days > 365:
            raise ValueError(f"horizon_days must be in [1, 365], got {self.horizon_days}")
        if self.hill_v_max <= 0:
            raise ValueError(f"hill_v_max must be > 0, got {self.hill_v_max}")
        if self.hill_k <= 0:
            raise ValueError(f"hill_k must be > 0, got {self.hill_k}")
        if not (0.0 < self.hill_alpha <= 2.5):
            raise ValueError(f"hill_alpha must be in (0, 2.5], got {self.hill_alpha}")
        if not (0.0 <= self.adstock_decay < 1.0):
            raise ValueError(f"adstock_decay must be in [0, 1), got {self.adstock_decay}")
        if self.order_value <= Decimal("0.00"):
            raise ValueError(f"order_value must be > 0, got {self.order_value}")
        if not (Decimal("0.00") <= self.cogs_rate < Decimal("1.00")):
            raise ValueError(f"cogs_rate must be in [0, 1), got {self.cogs_rate}")
        if not (Decimal("0.00") <= self.cod_share_rate <= Decimal("1.00")):
            raise ValueError(f"cod_share_rate must be in [0, 1], got {self.cod_share_rate}")
        if not (Decimal("0.00") < self.cod_confirmation_rate <= Decimal("1.00")):
            raise ValueError(f"cod_confirmation_rate must be in (0, 1], got {self.cod_confirmation_rate}")
        if not (Decimal("0.00") <= self.cod_rto_rate < Decimal("1.00")):
            raise ValueError(f"cod_rto_rate must be in [0, 1), got {self.cod_rto_rate}")
        if self.forward_shipping_cost < Decimal("0.00"):
            raise ValueError(f"forward_shipping_cost must be >= 0, got {self.forward_shipping_cost}")
        if self.return_shipping_cost < Decimal("0.00"):
            raise ValueError(f"return_shipping_cost must be >= 0, got {self.return_shipping_cost}")
        if self.delivery_delay_days < 0:
            raise ValueError(f"delivery_delay_days must be >= 0, got {self.delivery_delay_days}")
        if self.gateway_settle_days < 0:
            raise ValueError(f"gateway_settle_days must be >= 0, got {self.gateway_settle_days}")
        if self.cod_remittance_days < 0:
            raise ValueError(f"cod_remittance_days must be >= 0, got {self.cod_remittance_days}")
        if not (Decimal("0.00") <= self.gateway_fee_rate < Decimal("0.50")):
            raise ValueError(f"gateway_fee_rate must be in [0, 0.50), got {self.gateway_fee_rate}")
        if not (Decimal("0.00") <= self.rolling_reserve_rate < Decimal("0.50")):
            raise ValueError(f"rolling_reserve_rate must be in [0, 0.50), got {self.rolling_reserve_rate}")
        if not (Decimal("0.00") <= self.cod_fee_rate < Decimal("0.50")):
            raise ValueError(f"cod_fee_rate must be in [0, 0.50), got {self.cod_fee_rate}")
        if self.initial_cash < Decimal("0.00"):
            raise ValueError(f"initial_cash cannot be negative, got {self.initial_cash}")


@dataclass
class DailyMetrics:
    day: int
    ad_spend: Decimal
    effective_spend: float
    orders_booked: int
    booked_gmv: Decimal
    settled_cash_inflow: Decimal
    outflow_ad_spend: Decimal
    outflow_shipping_cogs: Decimal
    ending_settled_cash: Decimal
    accounts_receivable: Decimal
    cumulative_ad_spend: Decimal
    cumulative_booked_gmv: Decimal
    cumulative_settled_cash: Decimal
    cash_runway_breached: bool


@dataclass
class SimulationResult:
    config: D2CScaleConfig
    daily_timeline: list[DailyMetrics]
    ledger: MarketingLedger
    ledger_snapshot: LedgerSnapshot
    total_ad_spend: Decimal
    total_booked_gmv: Decimal
    total_settled_cash: Decimal
    ending_cash: Decimal
    min_cash_trough: Decimal
    min_cash_trough_day: int
    cash_runway_breached: bool
    breach_day: int | None
    paper_roas: Decimal
    net_mer: Decimal
    total_orders_booked: int
    total_cod_orders: int
    total_prepaid_orders: int
    total_rto_orders: int
    total_rto_loss: Decimal
    total_cogs: Decimal
    total_shipping_costs: Decimal
    total_fees: Decimal
    ledger_conserved: bool


class D2CScaleSimulator:
    """Full-fidelity DEVS and double-entry treasury simulation for D2C scale."""

    def __init__(self, config: D2CScaleConfig | None = None) -> None:
        self.config = config or D2CScaleConfig()
        self.hill = HillSaturation(
            v_max=self.config.hill_v_max,
            k_sat=self.config.hill_k,
            alpha=self.config.hill_alpha,
        )

    def run(self, seed: int = 42) -> SimulationResult:
        rng = random.Random(seed)
        cfg = self.config
        trial_id = f"d2c_scale_s{seed}"

        # Adstock state tracking
        adstock_state: float = 0.0

        # Pending settlement queues: (due_day, net_payout, gross_gmv, source_tx_id, kind)
        gateway_settlement_queue: list[tuple[int, Decimal, Decimal, str]] = []
        cod_remittance_queue: list[tuple[int, Decimal, Decimal, str]] = []
        delivery_queue: list[dict[str, Any]] = []

        daily_timeline: list[DailyMetrics] = []
        tx_counter = 0

        total_orders_booked = 0
        total_cod_orders = 0
        total_prepaid_orders = 0
        total_rto_orders = 0
        total_rto_loss = Decimal("0.00")
        total_cogs = Decimal("0.00")
        total_shipping_costs = Decimal("0.00")
        total_fees = Decimal("0.00")
        cum_ad_spend = Decimal("0.00")
        cum_booked_gmv = Decimal("0.00")
        cum_settled_cash = Decimal("0.00")

        min_cash = cfg.initial_cash
        min_cash_day = 0
        runway_breached = False
        breach_day: int | None = None

        current_cash = cfg.initial_cash
        open_receivables = Decimal("0.00")

        # Ordered entries accumulator for MarketingLedger
        journal_entries: list[LedgerEntry] = []

        for day in range(1, cfg.horizon_days + 1):
            day_tx_prefix = f"d{day}_"

            # 1. Determine daily ad spend (scaling policy)
            if day >= cfg.scale_start_day:
                daily_spend = cfg.scale_daily_ad_spend
            else:
                daily_spend = cfg.base_daily_ad_spend

            tx_counter += 1
            ad_tx_id = f"{day_tx_prefix}ad_{tx_counter}"
            journal_entries.append(LedgerEntry(trial_id, ad_tx_id, "ad_spend", day, daily_spend, cfg.currency))
            current_cash -= daily_spend
            cum_ad_spend += daily_spend

            # 2. Adstock carryover + Hill Saturation for orders
            spend_float = float(daily_spend)
            adstock_state = spend_float + cfg.adstock_decay * adstock_state
            expected_orders_float = self.hill.evaluate(adstock_state)
            
            # Poisson/Binomial discrete orders using seed
            noise = rng.gauss(0.0, max(1.0, math.sqrt(expected_orders_float) * 0.5))
            num_orders = max(1, round(expected_orders_float + noise))
            total_orders_booked += num_orders

            day_gmv = Decimal(str(num_orders)) * cfg.order_value
            cum_booked_gmv += day_gmv

            day_outflow_shipping_cogs = Decimal("0.00")
            day_settled_inflow = Decimal("0.00")

            # 3. Process individual orders for the day
            for ord_idx in range(num_orders):
                tx_counter += 1
                order_tx_id = f"{day_tx_prefix}ord_{tx_counter}"
                
                # Book sale into ledger (recognized revenue + receivable)
                journal_entries.append(LedgerEntry(trial_id, order_tx_id, "sale", day, cfg.order_value, cfg.currency))
                open_receivables += cfg.order_value

                # Determine payment cohort
                is_cod = rng.random() < float(cfg.cod_share_rate)
                unit_cogs = (cfg.order_value * cfg.cogs_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                unit_fwd_ship = cfg.forward_shipping_cost
                unit_pkg = cfg.packaging_cost

                if is_cod:
                    total_cod_orders += 1
                    # COD Confirmation Step
                    is_confirmed = rng.random() < float(cfg.cod_confirmation_rate)
                    if not is_confirmed:
                        # Cancelled before dispatch: zero revenue, zero shipping/cogs
                        # Writeoff receivable
                        tx_counter += 1
                        wo_tx_id = f"{day_tx_prefix}cnl_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, wo_tx_id, "writeoff", day, cfg.order_value, cfg.currency, source_tx_id=order_tx_id))
                        open_receivables -= cfg.order_value
                        continue

                    # Confirmed COD: incur COGS + forward shipping immediately
                    tx_counter += 1
                    cogs_tx = f"{day_tx_prefix}cogs_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, cogs_tx, "other_cost", day, unit_cogs, cfg.currency))
                    tx_counter += 1
                    ship_tx = f"{day_tx_prefix}fwd_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, ship_tx, "other_cost", day, unit_fwd_ship + unit_pkg, cfg.currency))
                    
                    current_cash -= (unit_cogs + unit_fwd_ship + unit_pkg)
                    day_outflow_shipping_cogs += (unit_cogs + unit_fwd_ship + unit_pkg)
                    total_cogs += unit_cogs
                    total_shipping_costs += (unit_fwd_ship + unit_pkg)

                    # Schedule courier delivery attempt
                    deliv_day = day + cfg.delivery_delay_days
                    delivery_queue.append({
                        "delivery_day": deliv_day,
                        "order_tx_id": order_tx_id,
                        "is_cod": True,
                        "value": cfg.order_value,
                    })

                else:
                    # Prepaid (Credit Card / Payment Gateway)
                    total_prepaid_orders += 1
                    is_refund = rng.random() < float(cfg.prepaid_refund_rate)
                    
                    # Incur COGS + shipping
                    tx_counter += 1
                    cogs_tx = f"{day_tx_prefix}cogs_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, cogs_tx, "other_cost", day, unit_cogs, cfg.currency))
                    tx_counter += 1
                    ship_tx = f"{day_tx_prefix}fwd_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, ship_tx, "other_cost", day, unit_fwd_ship + unit_pkg, cfg.currency))
                    
                    current_cash -= (unit_cogs + unit_fwd_ship + unit_pkg)
                    day_outflow_shipping_cogs += (unit_cogs + unit_fwd_ship + unit_pkg)
                    total_cogs += unit_cogs
                    total_shipping_costs += (unit_fwd_ship + unit_pkg)

                    if is_refund:
                        # Writeoff receivable
                        tx_counter += 1
                        wo_tx_id = f"{day_tx_prefix}ref_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, wo_tx_id, "writeoff", day, cfg.order_value, cfg.currency, source_tx_id=order_tx_id))
                        open_receivables -= cfg.order_value
                    else:
                        # Gateway settlement calculation
                        gw_fee = (cfg.order_value * cfg.gateway_fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        reserve = (cfg.order_value * cfg.rolling_reserve_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        net_gw_payout = cfg.order_value - gw_fee - reserve
                        total_fees += gw_fee
                        
                        tx_counter += 1
                        fee_tx = f"{day_tx_prefix}gwfee_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, fee_tx, "other_cost", day, gw_fee, cfg.currency))
                        current_cash -= gw_fee
                        day_outflow_shipping_cogs += gw_fee

                        gw_payout_day = day + cfg.gateway_settle_days
                        gateway_settlement_queue.append((gw_payout_day, net_gw_payout, cfg.order_value, order_tx_id))

            # 4. Process Courier Deliveries arriving on this day
            remaining_deliveries = []
            for item in delivery_queue:
                if item["delivery_day"] == day:
                    order_tx_id = item["order_tx_id"]
                    val = item["value"]
                    # Determine Delivered vs. RTO
                    is_rto = rng.random() < float(cfg.cod_rto_rate)
                    if is_rto:
                        total_rto_orders += 1
                        # Incur return shipping cost (loss)
                        tx_counter += 1
                        ret_ship_tx = f"{day_tx_prefix}rto_ship_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, ret_ship_tx, "other_cost", day, cfg.return_shipping_cost, cfg.currency))
                        current_cash -= cfg.return_shipping_cost
                        day_outflow_shipping_cogs += cfg.return_shipping_cost
                        total_shipping_costs += cfg.return_shipping_cost
                        total_rto_loss += (cfg.forward_shipping_cost + cfg.return_shipping_cost + cfg.packaging_cost)

                        # Write off the sale receivable
                        tx_counter += 1
                        wo_tx_id = f"{day_tx_prefix}rto_wo_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, wo_tx_id, "writeoff", day, val, cfg.currency, source_tx_id=order_tx_id))
                        open_receivables -= val
                    else:
                        # Delivered! Courier collected cash from customer.
                        cod_fee = (val * cfg.cod_fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        net_cod = val - cod_fee
                        total_fees += cod_fee

                        tx_counter += 1
                        fee_tx = f"{day_tx_prefix}codfee_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, fee_tx, "other_cost", day, cod_fee, cfg.currency))
                        current_cash -= cod_fee
                        day_outflow_shipping_cogs += cod_fee

                        remit_day = day + cfg.cod_remittance_days
                        cod_remittance_queue.append((remit_day, net_cod, val, order_tx_id))
                else:
                    remaining_deliveries.append(item)
            delivery_queue = remaining_deliveries

            # 5. Process Gateway Payouts due today
            remaining_gw = []
            for gw_day, net_payout, gross_val, ord_tx_id in gateway_settlement_queue:
                if gw_day == day:
                    tx_counter += 1
                    stl_tx = f"{day_tx_prefix}gw_stl_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, stl_tx, "settlement", day, gross_val, cfg.currency, source_tx_id=ord_tx_id))
                    current_cash += gross_val
                    day_settled_inflow += gross_val
                    cum_settled_cash += gross_val
                    open_receivables -= gross_val
                else:
                    remaining_gw.append((gw_day, net_payout, gross_val, ord_tx_id))
            gateway_settlement_queue = remaining_gw

            # 6. Process Courier Remittances due today
            remaining_cod = []
            for c_day, net_remit, gross_val, ord_tx_id in cod_remittance_queue:
                if c_day == day:
                    tx_counter += 1
                    stl_tx = f"{day_tx_prefix}cod_stl_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, stl_tx, "settlement", day, gross_val, cfg.currency, source_tx_id=ord_tx_id))
                    current_cash += gross_val
                    day_settled_inflow += gross_val
                    cum_settled_cash += gross_val
                    open_receivables -= gross_val
                else:
                    remaining_cod.append((c_day, net_remit, gross_val, ord_tx_id))
            cod_remittance_queue = remaining_cod

            # 7. Checkpoint liquid cash and runway health
            if current_cash < min_cash:
                min_cash = current_cash
                min_cash_day = day

            if current_cash < cfg.min_safety_cash and not runway_breached:
                runway_breached = True
                breach_day = day

            daily_timeline.append(DailyMetrics(
                day=day,
                ad_spend=daily_spend,
                effective_spend=adstock_state,
                orders_booked=num_orders,
                booked_gmv=day_gmv,
                settled_cash_inflow=day_settled_inflow,
                outflow_ad_spend=daily_spend,
                outflow_shipping_cogs=day_outflow_shipping_cogs,
                ending_settled_cash=current_cash,
                accounts_receivable=open_receivables,
                cumulative_ad_spend=cum_ad_spend,
                cumulative_booked_gmv=cum_booked_gmv,
                cumulative_settled_cash=cum_settled_cash,
                cash_runway_breached=(current_cash < cfg.min_safety_cash),
            ))

        # Close ledger and evaluate snapshot
        ledger = MarketingLedger(
            trial_id=trial_id,
            currency=cfg.currency,
            cash_initial=cfg.initial_cash,
            horizon=cfg.horizon_days,
            settlement_delay=0,
            entries=tuple(journal_entries),
        )
        snapshot = ledger.evaluate()

        # Exact double-entry conservation verification:
        # Starting Cash + Settled Inflows - Paid Outflows == Ending Cash
        expected_cash = cfg.initial_cash + snapshot.settled_receipts - snapshot.paid_ad_spend - snapshot.paid_other_costs
        ledger_conserved = (snapshot.cash == expected_cash) and (snapshot.cash == current_cash)

        paper_roas = (cum_booked_gmv / cum_ad_spend).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if cum_ad_spend else Decimal("0.00")
        net_mer = (cum_settled_cash / cum_ad_spend).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if cum_ad_spend else Decimal("0.00")

        return SimulationResult(
            config=cfg,
            daily_timeline=daily_timeline,
            ledger=ledger,
            ledger_snapshot=snapshot,
            total_ad_spend=cum_ad_spend,
            total_booked_gmv=cum_booked_gmv,
            total_settled_cash=cum_settled_cash,
            ending_cash=current_cash,
            min_cash_trough=min_cash,
            min_cash_trough_day=min_cash_day,
            cash_runway_breached=runway_breached,
            breach_day=breach_day,
            paper_roas=paper_roas,
            net_mer=net_mer,
            total_orders_booked=total_orders_booked,
            total_cod_orders=total_cod_orders,
            total_prepaid_orders=total_prepaid_orders,
            total_rto_orders=total_rto_orders,
            total_rto_loss=total_rto_loss,
            total_cogs=total_cogs,
            total_shipping_costs=total_shipping_costs,
            total_fees=total_fees,
            ledger_conserved=ledger_conserved,
        )

"""Lead Generation & Sales Team Capacity Constraint Simulation Engine.

Models the critical interaction between:
- Promotion: Multi-channel ad spend with Hill saturation & Adstock
- People: Finite sales headcount, daily rep capacity, hiring & onboarding ramp
- Process: Queue backlog, response-time degradation (speed-to-lead SLA), and lead cooling
- Price: Deal value, fixed payroll, hiring fees, commissions, and invoice collection lag

Directly bound to MarketingLedger to guarantee exact double-entry accounting conservation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from funnelscript.stdlib.marketing.kernels import HillSaturation
from funnelscript.stdlib.marketing.ledger import (
    LedgerEntry,
    LedgerSnapshot,
    MarketingLedger,
)


@dataclass(frozen=True)
class SalesCapacityConfig:
    """Strictly bounded, dimensionally sound parameters for Sales Capacity."""

    # Acquisition Parameters
    base_daily_ad_spend: Decimal = field(default_factory=lambda: Decimal("2000.00"))
    scale_daily_ad_spend: Decimal = field(default_factory=lambda: Decimal("5000.00"))
    scale_start_day: int = 1
    horizon_days: int = 30
    hill_v_max: float = 120.0
    hill_k: float = 6000.0
    hill_alpha: float = 0.85
    adstock_decay: float = 0.30
    deal_value: Decimal = field(default_factory=lambda: Decimal("4500.00"))

    # Sales Team Capacity & SLA Parameters
    active_reps: int = 4
    max_leads_per_rep_per_day: int = 12
    baseline_response_minutes: float = 15.0
    lead_decay_half_life_minutes: float = 45.0
    baseline_contact_rate: float = 0.70
    qualified_appointment_rate: float = 0.40
    deal_close_rate: float = 0.25

    # Pipeline & Hiring Levers
    sales_cycle_days: int = 14
    invoice_collection_days: int = 7
    monthly_rep_salary: Decimal = field(default_factory=lambda: Decimal("4000.00"))
    sales_commission_rate: Decimal = field(default_factory=lambda: Decimal("0.08"))
    hiring_cost_per_rep: Decimal = field(default_factory=lambda: Decimal("2500.00"))
    planned_new_hires: int = 0
    hire_start_day: int = 15
    onboarding_ramp_days: int = 14
    ramp_productivity_rate: float = 0.40

    # Working Capital
    initial_cash: Decimal = field(default_factory=lambda: Decimal("30000.00"))
    min_safety_cash: Decimal = field(default_factory=lambda: Decimal("10000.00"))
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate parameter boundaries and economic sanity."""
        if self.base_daily_ad_spend < Decimal("0.00"):
            raise ValueError(f"base_daily_ad_spend must be >= 0, got {self.base_daily_ad_spend}")
        if self.scale_daily_ad_spend < Decimal("0.00"):
            raise ValueError(f"scale_daily_ad_spend must be >= 0, got {self.scale_daily_ad_spend}")
        if self.horizon_days <= 0 or self.horizon_days > 365:
            raise ValueError(f"horizon_days must be in [1, 365], got {self.horizon_days}")
        if self.deal_value <= Decimal("0.00"):
            raise ValueError(f"deal_value must be > 0, got {self.deal_value}")
        if self.active_reps <= 0:
            raise ValueError(f"active_reps must be > 0, got {self.active_reps}")
        if self.max_leads_per_rep_per_day <= 0:
            raise ValueError(f"max_leads_per_rep_per_day must be > 0, got {self.max_leads_per_rep_per_day}")
        if self.baseline_response_minutes <= 0.0:
            raise ValueError(f"baseline_response_minutes must be > 0, got {self.baseline_response_minutes}")
        if self.lead_decay_half_life_minutes <= 0.0:
            raise ValueError(f"lead_decay_half_life_minutes must be > 0, got {self.lead_decay_half_life_minutes}")
        if not (0.0 < self.baseline_contact_rate <= 1.0):
            raise ValueError(f"baseline_contact_rate must be in (0, 1], got {self.baseline_contact_rate}")
        if not (0.0 < self.qualified_appointment_rate <= 1.0):
            raise ValueError(f"qualified_appointment_rate must be in (0, 1], got {self.qualified_appointment_rate}")
        if not (0.0 < self.deal_close_rate <= 1.0):
            raise ValueError(f"deal_close_rate must be in (0, 1], got {self.deal_close_rate}")
        if self.sales_cycle_days < 0:
            raise ValueError(f"sales_cycle_days must be >= 0, got {self.sales_cycle_days}")
        if self.invoice_collection_days < 0:
            raise ValueError(f"invoice_collection_days must be >= 0, got {self.invoice_collection_days}")
        if not (Decimal("0.00") <= self.sales_commission_rate <= Decimal("0.50")):
            raise ValueError(f"sales_commission_rate must be in [0, 0.50], got {self.sales_commission_rate}")
        if self.planned_new_hires < 0:
            raise ValueError(f"planned_new_hires cannot be negative, got {self.planned_new_hires}")
        if self.onboarding_ramp_days < 0:
            raise ValueError(f"onboarding_ramp_days cannot be negative, got {self.onboarding_ramp_days}")
        if not (0.0 <= self.ramp_productivity_rate <= 1.0):
            raise ValueError(f"ramp_productivity_rate must be in [0, 1], got {self.ramp_productivity_rate}")
        if self.initial_cash < Decimal("0.00"):
            raise ValueError(f"initial_cash cannot be negative, got {self.initial_cash}")


@dataclass
class DailySalesMetrics:
    day: int
    ad_spend: Decimal
    leads_generated: int
    active_capacity: int
    backlog_queue_depth: int
    speed_to_lead_minutes: float
    leads_contacted: int
    appointments_booked: int
    deals_closed: int
    deals_booked_revenue: Decimal
    cash_collected: Decimal
    payroll_paid: Decimal
    commissions_paid: Decimal
    hiring_cost_paid: Decimal
    ending_cash: Decimal
    accounts_receivable: Decimal


@dataclass
class SalesCapacityResult:
    config: SalesCapacityConfig
    daily_timeline: list[DailySalesMetrics]
    ledger: MarketingLedger
    ledger_snapshot: LedgerSnapshot
    total_leads_generated: int
    total_leads_contacted: int
    total_appointments_booked: int
    total_deals_closed: int
    total_ad_spend: Decimal
    total_payroll: Decimal
    total_hiring_costs: Decimal
    total_commissions: Decimal
    total_booked_revenue: Decimal
    total_collected_revenue: Decimal
    ending_cash: Decimal
    min_cash_trough: Decimal
    min_cash_trough_day: int
    peak_queue_backlog: int
    avg_speed_to_lead_minutes: float
    capacity_utilization_pct: float
    blended_cpl: Decimal
    effective_close_rate: Decimal
    effective_cac: Decimal
    net_contribution_margin: Decimal
    ledger_conserved: bool


class SalesCapacitySimulator:
    """Quantitative DEVS and double-entry treasury simulator for sales team constraints."""

    def __init__(self, config: SalesCapacityConfig | None = None) -> None:
        self.config = config or SalesCapacityConfig()
        self.hill = HillSaturation(
            v_max=self.config.hill_v_max,
            k_sat=self.config.hill_k,
            alpha=self.config.hill_alpha,
        )

    def run(self, seed: int = 42) -> SalesCapacityResult:
        rng_leads = random.Random(seed)
        rng_sales = random.Random(seed + 54321)
        cfg = self.config
        trial_id = f"sales_cap_s{seed}"

        adstock_state: float = 0.0
        backlog_queue = 0
        current_cash = cfg.initial_cash
        open_receivables = Decimal("0.00")

        cum_ad_spend = Decimal("0.00")
        cum_payroll = Decimal("0.00")
        cum_hiring = Decimal("0.00")
        cum_commissions = Decimal("0.00")
        cum_booked_rev = Decimal("0.00")
        cum_collected_rev = Decimal("0.00")

        total_leads = 0
        total_contacted = 0
        total_appts = 0
        total_closed = 0
        peak_backlog = 0
        all_speeds: list[float] = []
        total_capacity_available = 0
        total_leads_serviced = 0

        # Pipeline queues:
        # closing_deals: list of (close_day, count)
        closing_deals_queue: list[tuple[int, int]] = []
        # invoice_collections: list of (collect_day, amount, commission, sale_tx_id)
        invoice_queue: list[tuple[int, Decimal, Decimal, str]] = []

        journal_entries: list[LedgerEntry] = []
        daily_timeline: list[DailySalesMetrics] = []
        tx_counter = 0

        min_cash = cfg.initial_cash
        min_cash_day = 0

        for day in range(1, cfg.horizon_days + 1):
            day_prefix = f"d{day}_"

            # 1. Determine Headcount & Capacity on this day
            effective_reps = float(cfg.active_reps)
            active_hired_count = 0
            if day >= cfg.hire_start_day and cfg.planned_new_hires > 0:
                active_hired_count = cfg.planned_new_hires
                ramp_elapsed = day - cfg.hire_start_day
                if ramp_elapsed < cfg.onboarding_ramp_days and cfg.onboarding_ramp_days > 0:
                    effective_reps += cfg.planned_new_hires * cfg.ramp_productivity_rate
                else:
                    effective_reps += cfg.planned_new_hires

                # One-time recruitment cost on the hire day
                if day == cfg.hire_start_day:
                    hiring_total = cfg.hiring_cost_per_rep * Decimal(str(cfg.planned_new_hires))
                    tx_counter += 1
                    h_tx = f"{day_prefix}hire_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, h_tx, "other_cost", day, hiring_total, cfg.currency))
                    current_cash -= hiring_total
                    cum_hiring += hiring_total

            daily_capacity = max(1, round(effective_reps * float(cfg.max_leads_per_rep_per_day)))
            total_capacity_available += daily_capacity

            # 2. Fixed Payroll for active + hired headcount
            total_reps_on_payroll = Decimal(str(cfg.active_reps + active_hired_count))
            daily_payroll = ((total_reps_on_payroll * cfg.monthly_rep_salary) / Decimal("30.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            tx_counter += 1
            pay_tx = f"{day_prefix}pay_{tx_counter}"
            journal_entries.append(LedgerEntry(trial_id, pay_tx, "other_cost", day, daily_payroll, cfg.currency))
            current_cash -= daily_payroll
            cum_payroll += daily_payroll

            # 3. Ad Spend & Lead Generation
            daily_spend = cfg.scale_daily_ad_spend if day >= cfg.scale_start_day else cfg.base_daily_ad_spend
            tx_counter += 1
            ad_tx = f"{day_prefix}ad_{tx_counter}"
            journal_entries.append(LedgerEntry(trial_id, ad_tx, "ad_spend", day, daily_spend, cfg.currency))
            current_cash -= daily_spend
            cum_ad_spend += daily_spend

            spend_float = float(daily_spend)
            adstock_state = spend_float + cfg.adstock_decay * adstock_state
            exp_leads = self.hill.evaluate(adstock_state)
            noise = rng_leads.gauss(0.0, max(0.5, math.sqrt(exp_leads) * 0.4))
            leads_today = max(1, round(exp_leads + noise))
            total_leads += leads_today

            # 4. Queue Ingestion & Speed-to-Lead
            total_available_leads = backlog_queue + leads_today
            leads_serviced_today = min(total_available_leads, daily_capacity)
            backlog_queue = total_available_leads - leads_serviced_today
            total_leads_serviced += leads_serviced_today

            peak_backlog = max(peak_backlog, backlog_queue)

            # Speed-to-lead expands non-linearly with backlog depth
            if backlog_queue == 0:
                speed_to_lead = cfg.baseline_response_minutes
            else:
                # 480 minutes (8-hour working shift delay proportional to backlog)
                delay_minutes = (float(backlog_queue) / float(daily_capacity)) * 480.0
                speed_to_lead = cfg.baseline_response_minutes + delay_minutes

            all_speeds.append(speed_to_lead)

            # 5. Lead Contact Decay & Pipeline Conversion
            # Half-life decay: CVR(t) = CVR_0 * 2^(-t / t_half)
            decay_factor = math.pow(2.0, -speed_to_lead / cfg.lead_decay_half_life_minutes)
            effective_contact_p = max(0.01, cfg.baseline_contact_rate * decay_factor)

            # Binomial contact draws
            contacted_today = sum(1 for _ in range(leads_serviced_today) if rng_sales.random() < effective_contact_p)
            total_contacted += contacted_today

            # Appointments
            appts_today = sum(1 for _ in range(contacted_today) if rng_sales.random() < cfg.qualified_appointment_rate)
            total_appts += appts_today

            # Deals closed (to close after sales_cycle_days)
            deals_from_appts = sum(1 for _ in range(appts_today) if rng_sales.random() < cfg.deal_close_rate)
            if deals_from_appts > 0:
                close_day = day + cfg.sales_cycle_days
                closing_deals_queue.append((close_day, deals_from_appts))

            # 6. Process Closed Deals due today
            rem_closing = []
            deals_closed_today = 0
            day_booked_revenue = Decimal("0.00")
            for c_day, d_count in closing_deals_queue:
                if c_day == day:
                    deals_closed_today += d_count
                    deal_gmv = Decimal(str(d_count)) * cfg.deal_value
                    day_booked_revenue += deal_gmv
                    cum_booked_rev += deal_gmv
                    open_receivables += deal_gmv

                    tx_counter += 1
                    sale_tx = f"{day_prefix}deal_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, sale_tx, "sale", day, deal_gmv, cfg.currency))

                    # Commission and invoice collection scheduled
                    comm = (deal_gmv * cfg.sales_commission_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    collect_day = day + cfg.invoice_collection_days
                    invoice_queue.append((collect_day, deal_gmv, comm, sale_tx))
                else:
                    rem_closing.append((c_day, d_count))
            closing_deals_queue = rem_closing
            total_closed += deals_closed_today

            # 7. Process Invoice Collections due today
            rem_invoices = []
            day_collected_cash = Decimal("0.00")
            day_commissions = Decimal("0.00")
            for inv_day, gmv_amt, comm_amt, sale_ref in invoice_queue:
                if inv_day == day:
                    tx_counter += 1
                    stl_tx = f"{day_prefix}inv_{tx_counter}"
                    journal_entries.append(LedgerEntry(trial_id, stl_tx, "settlement", day, gmv_amt, cfg.currency, source_tx_id=sale_ref))
                    current_cash += gmv_amt
                    day_collected_cash += gmv_amt
                    cum_collected_rev += gmv_amt
                    open_receivables -= gmv_amt

                    # Commission paid upon collection
                    if comm_amt > Decimal("0.00"):
                        tx_counter += 1
                        comm_tx = f"{day_prefix}comm_{tx_counter}"
                        journal_entries.append(LedgerEntry(trial_id, comm_tx, "other_cost", day, comm_amt, cfg.currency))
                        current_cash -= comm_amt
                        day_commissions += comm_amt
                        cum_commissions += comm_amt
                else:
                    rem_invoices.append((inv_day, gmv_amt, comm_amt, sale_ref))
            invoice_queue = rem_invoices

            # 8. Checkpoint metrics
            if current_cash < min_cash:
                min_cash = current_cash
                min_cash_day = day

            daily_timeline.append(DailySalesMetrics(
                day=day,
                ad_spend=daily_spend,
                leads_generated=leads_today,
                active_capacity=daily_capacity,
                backlog_queue_depth=backlog_queue,
                speed_to_lead_minutes=speed_to_lead,
                leads_contacted=contacted_today,
                appointments_booked=appts_today,
                deals_closed=deals_closed_today,
                deals_booked_revenue=day_booked_revenue,
                cash_collected=day_collected_cash,
                payroll_paid=daily_payroll,
                commissions_paid=day_commissions,
                hiring_cost_paid=cfg.hiring_cost_per_rep * Decimal(str(cfg.planned_new_hires)) if day == cfg.hire_start_day else Decimal("0.00"),
                ending_cash=current_cash,
                accounts_receivable=open_receivables,
            ))

        # Evaluate Double-Entry Ledger
        ledger = MarketingLedger(
            trial_id=trial_id,
            currency=cfg.currency,
            cash_initial=cfg.initial_cash,
            horizon=cfg.horizon_days,
            settlement_delay=0,
            entries=tuple(journal_entries),
        )
        snapshot = ledger.evaluate()

        expected_cash = cfg.initial_cash + snapshot.settled_receipts - snapshot.paid_ad_spend - snapshot.paid_other_costs
        ledger_conserved = (snapshot.cash == expected_cash) and (snapshot.cash == current_cash)

        avg_speed = sum(all_speeds) / len(all_speeds) if all_speeds else 0.0
        utilization = (total_leads_serviced / total_capacity_available * 100.0) if total_capacity_available else 0.0
        blended_cpl = (cum_ad_spend / Decimal(str(total_leads))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_leads else Decimal("0.00")
        effective_close_rate = (Decimal(str(total_closed)) / Decimal(str(total_leads))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if total_leads else Decimal("0.0000")
        
        total_costs = cum_ad_spend + cum_payroll + cum_hiring + cum_commissions
        effective_cac = (total_costs / Decimal(str(total_closed))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_closed else Decimal("0.00")
        net_contrib = cum_collected_rev - total_costs

        return SalesCapacityResult(
            config=cfg,
            daily_timeline=daily_timeline,
            ledger=ledger,
            ledger_snapshot=snapshot,
            total_leads_generated=total_leads,
            total_leads_contacted=total_contacted,
            total_appointments_booked=total_appts,
            total_deals_closed=total_closed,
            total_ad_spend=cum_ad_spend,
            total_payroll=cum_payroll,
            total_hiring_costs=cum_hiring,
            total_commissions=cum_commissions,
            total_booked_revenue=cum_booked_rev,
            total_collected_revenue=cum_collected_rev,
            ending_cash=current_cash,
            min_cash_trough=min_cash,
            min_cash_trough_day=min_cash_day,
            peak_queue_backlog=peak_backlog,
            avg_speed_to_lead_minutes=round(avg_speed, 1),
            capacity_utilization_pct=round(utilization, 1),
            blended_cpl=blended_cpl,
            effective_close_rate=effective_close_rate,
            effective_cac=effective_cac,
            net_contribution_margin=net_contrib,
            ledger_conserved=ledger_conserved,
        )

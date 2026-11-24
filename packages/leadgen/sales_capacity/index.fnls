world SalesCapacityPackage {
  entity SalesCapacity {
    state cash_balance: float = 30000.0;
    state min_safety_cash: float = 10000.0;
    state active_reps: int = 4;
    state daily_rep_capacity: int = 12;
    state total_team_capacity: int = 48;
    state backlog_depth: int = 0;
    state effective_speed_to_lead: float = 15.0;
    state total_leads_generated: int = 0;
    state total_leads_contacted: int = 0;
    state qualified_appointments: int = 0;
    state closed_won_deals: int = 0;
    state booked_revenue: float = 0.0;
    state collected_revenue: float = 0.0;
    state accounts_receivable: float = 0.0;
    state total_ad_spend: float = 0.0;
    state total_payroll: float = 0.0;
    state total_commissions: float = 0.0;
    state total_hiring_costs: float = 0.0;
    state total_writeoffs: float = 0.0;
    state queue_overflow_breached: bool = false;
    state cash_runway_breached: bool = false;
    state active: bool = true;

    event DailyAdSpend(spend: float, leads: int);
    event ProcessBacklog(processed: int, speed_to_lead: float, contacted: int);
    event ScheduleDeal(appointments: int);
    event CloseDeals(deals_count: int, deal_value: float);
    event CollectDeals(net_cash: float, gross_collected: float, commission: float);
    event DeductDailyPayroll(payroll_amount: float);
    event AddNewHires(new_reps: int, hiring_cost: float, new_capacity: int);
    event CheckSafetyThreshold(day: int);

    rule SpendAds on event DailyAdSpend when (active == true) {
      transition cash_balance = cash_balance - payload.spend;
      transition total_ad_spend = total_ad_spend + payload.spend;
      transition total_leads_generated = total_leads_generated + payload.leads;
      transition backlog_depth = backlog_depth + payload.leads;
    }

    rule ServiceQueue on event ProcessBacklog when (active == true) {
      transition backlog_depth = backlog_depth - payload.processed;
      transition effective_speed_to_lead = payload.speed_to_lead;
      transition total_leads_contacted = total_leads_contacted + payload.contacted;
    }

    rule SetAppointments on event ScheduleDeal when (active == true) {
      transition qualified_appointments = qualified_appointments + payload.appointments;
    }

    rule WinDeals on event CloseDeals when (active == true) {
      transition closed_won_deals = closed_won_deals + payload.deals_count;
      transition booked_revenue = booked_revenue + payload.deal_value;
      transition accounts_receivable = accounts_receivable + payload.deal_value;
    }

    rule CollectCash on event CollectDeals when (active == true) {
      transition cash_balance = cash_balance + payload.net_cash;
      transition collected_revenue = collected_revenue + payload.gross_collected;
      transition total_commissions = total_commissions + payload.commission;
      transition accounts_receivable = accounts_receivable - payload.gross_collected;
    }

    rule PayDailyPayroll on event DeductDailyPayroll when (active == true) {
      transition cash_balance = cash_balance - payload.payroll_amount;
      transition total_payroll = total_payroll + payload.payroll_amount;
    }

    rule ExpandTeam on event AddNewHires when (active == true) {
      transition active_reps = active_reps + payload.new_reps;
      transition total_team_capacity = total_team_capacity + payload.new_capacity;
      transition cash_balance = cash_balance - payload.hiring_cost;
      transition total_hiring_costs = total_hiring_costs + payload.hiring_cost;
    }

    rule CheckSafety on event CheckSafetyThreshold when (cash_balance < 10000.0) {
      transition cash_runway_breached = true;
    }
  }
}

world SalesEconomicsModule {
  entity SalesEconomicsEngine {
    state cash_balance: float = 30000.0;
    state accounts_receivable: float = 0.0;
    state booked_deal_revenue: float = 0.0;
    state collected_deal_revenue: float = 0.0;
    state total_ad_spend: float = 0.0;
    state total_base_payroll: float = 0.0;
    state total_hiring_costs: float = 0.0;
    state total_commissions: float = 0.0;
    state total_writeoffs: float = 0.0;
    state min_cash_trough: float = 30000.0;
    state min_safety_cash: float = 10000.0;
    state cash_runway_breached: bool = false;
    state active: bool = true;

    event DeductAdSpend(amount: float);
    event DeductPayroll(amount: float);
    event DeductHiringCost(amount: float);
    event BookDeal(deal_id: int, deal_amount: float);
    event CollectInvoice(deal_id: int, net_cash_inflow: float, collected_amount: float, commission_amount: float);
    event WriteoffLostDeal(deal_amount: float);
    event EvaluateSolvency(day: int);

    rule PayAdSpend on event DeductAdSpend when (active == true) {
      transition cash_balance = cash_balance - payload.amount;
      transition total_ad_spend = total_ad_spend + payload.amount;
    }

    rule PayPayroll on event DeductPayroll when (active == true) {
      transition cash_balance = cash_balance - payload.amount;
      transition total_base_payroll = total_base_payroll + payload.amount;
    }

    rule PayHiring on event DeductHiringCost when (active == true) {
      transition cash_balance = cash_balance - payload.amount;
      transition total_hiring_costs = total_hiring_costs + payload.amount;
    }

    rule BookSignedDeal on event BookDeal when (active == true) {
      transition booked_deal_revenue = booked_deal_revenue + payload.deal_amount;
      transition accounts_receivable = accounts_receivable + payload.deal_amount;
    }

    rule ReceiveCash on event CollectInvoice when (active == true) {
      transition cash_balance = cash_balance + payload.net_cash_inflow;
      transition collected_deal_revenue = collected_deal_revenue + payload.collected_amount;
      transition total_commissions = total_commissions + payload.commission_amount;
      transition accounts_receivable = accounts_receivable - payload.collected_amount;
    }

    rule ExpireLostDeal on event WriteoffLostDeal when (active == true) {
      transition accounts_receivable = accounts_receivable - payload.deal_amount;
      transition total_writeoffs = total_writeoffs + payload.deal_amount;
    }

    rule CheckSafety on event EvaluateSolvency when (cash_balance < 10000.0) {
      transition cash_runway_breached = true;
    }
  }
}

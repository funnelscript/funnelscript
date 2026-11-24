world LeadAcquisitionModule {
  entity LeadAcquisitionEngine {
    state daily_budget: float = 2000.0;
    state cumulative_spend: float = 0.0;
    state total_impressions: int = 0;
    state total_leads_generated: int = 0;
    state current_cpl: float = 35.0;
    state active: bool = true;

    event DailySpendTick(spend: float, cpl: float, lead_intent: string);
    event LeadGenerated(lead_id: int, channel: string, intent_tier: string, cpl: float);

    rule ProcessDailySpend on event DailySpendTick when (active == true) {
      transition cumulative_spend = cumulative_spend + payload.spend;
      transition total_impressions = total_impressions + 1;
      emit LeadGenerated(lead_id = total_leads_generated, channel = "paid_inbound", intent_tier = payload.lead_intent, cpl = payload.cpl) after 0;
    }

    rule RecordLead on event LeadGenerated when (active == true) {
      transition total_leads_generated = total_leads_generated + 1;
    }
  }
}

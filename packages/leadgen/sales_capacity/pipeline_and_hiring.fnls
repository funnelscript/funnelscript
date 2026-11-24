world SalesPipelineAndHiringModule {
  entity PipelineHiringEngine {
    state current_reps: int = 4;
    state ramping_reps: int = 0;
    state qualified_appointments: int = 0;
    state closed_won_deals: int = 0;
    state closed_lost_deals: int = 0;
    state sales_cycle_days: int = 14;
    state active: bool = true;

    event ScheduleAppointment(lead_id: int);
    event ResolveDeal(lead_id: int, won: bool, deal_amount: float);
    event RecruitNewHire(num_hires: int, hiring_cost: float);
    event CompleteRamp(num_reps: int);

    rule BookAppointment on event ScheduleAppointment when (active == true) {
      transition qualified_appointments = qualified_appointments + 1;
      emit ResolveDeal(lead_id = payload.lead_id, won = true, deal_amount = 4500.0) after 14;
    }

    rule FinalizeDeal on event ResolveDeal when (active == true) {
      transition closed_won_deals = closed_won_deals + 1;
    }

    rule HireRep on event RecruitNewHire when (active == true) {
      transition ramping_reps = ramping_reps + payload.num_hires;
      emit CompleteRamp(num_reps = payload.num_hires) after 14;
    }

    rule FinishRamp on event CompleteRamp when (active == true) {
      transition current_reps = current_reps + payload.num_reps;
      transition ramping_reps = ramping_reps - payload.num_reps;
    }
  }
}

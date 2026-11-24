world LeadQueueSLAModule {
  entity SalesQueueEngine {
    state active_reps: int = 4;
    state daily_rep_capacity: int = 12;
    state total_team_capacity: int = 48;
    state backlog_depth: int = 0;
    state processed_today: int = 0;
    state baseline_sla_minutes: float = 15.0;
    state effective_speed_to_lead: float = 15.0;
    state decay_half_life_minutes: float = 45.0;
    state total_contacted: int = 0;
    state total_decayed_uncontacted: int = 0;
    state queue_overflow_alert: bool = false;
    state active: bool = true;

    event IntakeLead(lead_id: int, channel: string);
    event DispatchOutreach(lead_id: int, response_delay_minutes: float);
    event ContactOutcome(lead_id: int, contacted: bool);
    event EvaluateQueueHealth(day: int);

    rule EnqueueLead on event IntakeLead when (active == true) {
      transition backlog_depth = backlog_depth + 1;
      emit DispatchOutreach(lead_id = payload.lead_id, response_delay_minutes = effective_speed_to_lead) after 0;
    }

    rule AttemptOutreach on event DispatchOutreach when (active == true) {
      transition processed_today = processed_today + 1;
      transition backlog_depth = backlog_depth - 1;
      emit ContactOutcome(lead_id = payload.lead_id, contacted = true) after 0;
    }

    rule RecordContact on event ContactOutcome when (active == true) {
      transition total_contacted = total_contacted + 1;
    }

    rule CheckQueue on event EvaluateQueueHealth when (backlog_depth > 20) {
      transition queue_overflow_alert = true;
    }
  }
}

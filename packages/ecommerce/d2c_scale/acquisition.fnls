world D2CAcquisitionModule {
  entity AcquisitionEngine {
    state daily_budget: float = 5000.0;
    state cumulative_spend: float = 0.0;
    state total_clicks: int = 0;
    state total_orders: int = 0;
    state current_cpa: float = 25.0;
    state active: bool = true;

    event DailySpendTick(spend: float, cpc: float, order_value: float, is_cod: bool);
    event OrderIntent(order_id: int, channel: string, order_value: float, is_cod: bool, cpa: float);

    rule ProcessDailySpend on event DailySpendTick when (active == true) {
      transition cumulative_spend = cumulative_spend + payload.spend;
      transition total_clicks = total_clicks + 1;
      emit OrderIntent(order_id = total_clicks, channel = "paid_growth", order_value = payload.order_value, is_cod = payload.is_cod, cpa = current_cpa) after 0;
    }

    rule RecordOrderIntent on event OrderIntent when (active == true) {
      transition total_orders = total_orders + 1;
    }
  }
}

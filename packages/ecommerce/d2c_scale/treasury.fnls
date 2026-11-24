world D2CTreasuryModule {
  entity TreasuryLedger {
    state cash_balance: float = 15000.0;
    state accounts_receivable: float = 0.0;
    state rolling_reserve: float = 0.0;
    state booked_revenue: float = 0.0;
    state settled_revenue: float = 0.0;
    state total_ad_spend: float = 0.0;
    state total_shipping_cost: float = 0.0;
    state total_cogs: float = 0.0;
    state total_gateway_fees: float = 0.0;
    state total_cod_fees: float = 0.0;
    state total_writeoffs: float = 0.0;
    state min_cash_trough: float = 15000.0;
    state min_safety_cash: float = 5000.0;
    state cash_runway_breached: bool = false;
    state active: bool = true;

    event RecordAdSpend(amount: float);
    event BookSale(amount: float, is_cod: bool);
    event SettleGateway(gross_amount: float, net_payout: float, fee: float, reserve: float);
    event SettleCOD(gross_amount: float, net_payout: float, courier_fee: float);
    event WriteoffRTO(gmv_amount: float, return_shipping: float, packaging_loss: float);
    event ReleaseReserve(amount: float);
    event EvaluateCash(day: int);

    rule DeductAdSpend on event RecordAdSpend when (active == true) {
      transition cash_balance = cash_balance - payload.amount;
      transition total_ad_spend = total_ad_spend + payload.amount;
    }

    rule RecordSale on event BookSale when (active == true) {
      transition booked_revenue = booked_revenue + payload.amount;
      transition accounts_receivable = accounts_receivable + payload.amount;
    }

    rule GatewayPayout on event SettleGateway when (active == true) {
      transition cash_balance = cash_balance + payload.net_payout;
      transition settled_revenue = settled_revenue + payload.net_payout;
      transition accounts_receivable = accounts_receivable - payload.gross_amount;
      transition rolling_reserve = rolling_reserve + payload.reserve;
      transition total_gateway_fees = total_gateway_fees + payload.fee;
    }

    rule CODRemittance on event SettleCOD when (active == true) {
      transition cash_balance = cash_balance + payload.net_payout;
      transition settled_revenue = settled_revenue + payload.net_payout;
      transition accounts_receivable = accounts_receivable - payload.gross_amount;
      transition total_cod_fees = total_cod_fees + payload.courier_fee;
    }

    rule RTOExpense on event WriteoffRTO when (active == true) {
      transition accounts_receivable = accounts_receivable - payload.gmv_amount;
      transition total_writeoffs = total_writeoffs + payload.gmv_amount;
      transition cash_balance = cash_balance - payload.return_shipping;
      transition total_shipping_cost = total_shipping_cost + payload.return_shipping;
    }

    rule ReservePayout on event ReleaseReserve when (active == true) {
      transition cash_balance = cash_balance + payload.amount;
      transition rolling_reserve = rolling_reserve - payload.amount;
    }

    rule CheckRunway on event EvaluateCash when (cash_balance < 5000.0) {
      transition cash_runway_breached = true;
    }
  }
}

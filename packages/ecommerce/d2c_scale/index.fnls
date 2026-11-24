world D2CScalePackage {
  entity D2CScale {
    state cash_balance: float = 15000.0;
    state min_safety_cash: float = 5000.0;
    state min_cash_trough: float = 15000.0;
    state accounts_receivable: float = 0.0;
    state booked_gmv: float = 0.0;
    state settled_cash: float = 0.0;
    state total_ad_spend: float = 0.0;
    state total_shipping_cost: float = 0.0;
    state total_cogs: float = 0.0;
    state total_fees: float = 0.0;
    state total_writeoffs: float = 0.0;
    state rolling_reserve: float = 0.0;
    state orders_count: int = 0;
    state delivered_count: int = 0;
    state rto_count: int = 0;
    state cash_runway_breached: bool = false;
    state active: bool = true;

    event DailyAdSpend(spend: float);
    event NewOrder(order_id: int, order_value: float, is_cod: bool, cogs: float, shipping: float);
    event OrderDelivered(order_id: int, order_value: float, is_cod: bool, fee: float, net_cash: float);
    event OrderRTO(order_id: int, order_value: float, return_shipping: float);
    event GatewaySettlement(gross: float, net: float, fee: float, reserve: float);
    event CODRemittance(gross: float, net: float, fee: float);
    event CheckSafetyThreshold(day: int);

    rule SpendAds on event DailyAdSpend when (active == true) {
      transition cash_balance = cash_balance - payload.spend;
      transition total_ad_spend = total_ad_spend + payload.spend;
    }

    rule PlaceOrder on event NewOrder when (active == true) {
      transition orders_count = orders_count + 1;
      transition booked_gmv = booked_gmv + payload.order_value;
      transition accounts_receivable = accounts_receivable + payload.order_value;
      transition total_cogs = total_cogs + payload.cogs;
      transition total_shipping_cost = total_shipping_cost + payload.shipping;
      transition cash_balance = cash_balance - payload.shipping;
    }

    rule DeliverOrder on event OrderDelivered when (active == true) {
      transition delivered_count = delivered_count + 1;
    }

    rule ReturnToOrigin on event OrderRTO when (active == true) {
      transition rto_count = rto_count + 1;
      transition accounts_receivable = accounts_receivable - payload.order_value;
      transition total_writeoffs = total_writeoffs + payload.order_value;
      transition cash_balance = cash_balance - payload.return_shipping;
      transition total_shipping_cost = total_shipping_cost + payload.return_shipping;
    }

    rule SettleOnline on event GatewaySettlement when (active == true) {
      transition cash_balance = cash_balance + payload.net;
      transition settled_cash = settled_cash + payload.net;
      transition accounts_receivable = accounts_receivable - payload.gross;
      transition total_fees = total_fees + payload.fee;
      transition rolling_reserve = rolling_reserve + payload.reserve;
    }

    rule SettleCourier on event CODRemittance when (active == true) {
      transition cash_balance = cash_balance + payload.net;
      transition settled_cash = settled_cash + payload.net;
      transition accounts_receivable = accounts_receivable - payload.gross;
      transition total_fees = total_fees + payload.fee;
    }

    rule CheckSafety on event CheckSafetyThreshold when (cash_balance < 5000.0) {
      transition cash_runway_breached = true;
    }
  }
}

world D2CFulfillmentModule {
  entity FulfillmentPipeline {
    state orders_received: int = 0;
    state orders_confirmed: int = 0;
    state orders_dispatched: int = 0;
    state orders_delivered: int = 0;
    state orders_rto: int = 0;
    state orders_refunded: int = 0;
    state shipping_paid: float = 0.0;
    state cogs_incurred: float = 0.0;
    state active: bool = true;

    event OrderIntake(order_id: int, order_value: float, is_cod: bool);
    event ConfirmOrder(order_id: int, order_value: float, is_cod: bool);
    event DispatchOrder(order_id: int, order_value: float, is_cod: bool, shipping_cost: float, cogs: float);
    event DeliveryResult(order_id: int, order_value: float, is_cod: bool, delivered: bool, return_shipping_cost: float);
    event ProcessRefund(order_id: int, refund_amount: float);

    rule ReceiveOrder on event OrderIntake when (active == true) {
      transition orders_received = orders_received + 1;
      emit ConfirmOrder(order_id = payload.order_id, order_value = payload.order_value, is_cod = payload.is_cod) after 0;
    }

    rule ConfirmCOD on event ConfirmOrder when (active == true) {
      transition orders_confirmed = orders_confirmed + 1;
      emit DispatchOrder(order_id = payload.order_id, order_value = payload.order_value, is_cod = payload.is_cod, shipping_cost = 4.5, cogs = 29.75) after 1;
    }

    rule ShipPackage on event DispatchOrder when (active == true) {
      transition orders_dispatched = orders_dispatched + 1;
      transition shipping_paid = shipping_paid + payload.shipping_cost;
      transition cogs_incurred = cogs_incurred + payload.cogs;
      emit DeliveryResult(order_id = payload.order_id, order_value = payload.order_value, is_cod = payload.is_cod, delivered = true, return_shipping_cost = 3.5) after 4;
    }

    rule ResolveDelivery on event DeliveryResult when (active == true) {
      transition orders_delivered = orders_delivered + 1;
    }

    rule RefundPrepaid on event ProcessRefund when (active == true) {
      transition orders_refunded = orders_refunded + 1;
    }
  }
}

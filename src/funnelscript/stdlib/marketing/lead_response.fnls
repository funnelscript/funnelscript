world LeadResponseLibrary {
  agent Lead {
    state exposed: bool = false;
    state converted: bool = false;
    state spend: float = 0.0;
    state revenue: float = 0.0;

    event Impression(
      cpc: float,
      conversion_probability: float,
      order_value: float
    );
    event Checkout(order_value: float);

    rule ShowAd on event Impression when (exposed == false) {
      transition exposed = true;
      transition converted = sample bernoulli(payload.conversion_probability);
      transition spend = payload.cpc;
      emit Checkout(order_value = payload.order_value) after 1;
    }

    rule Purchase on event Checkout when (converted == true) {
      transition revenue = revenue + payload.order_value;
    }
  }
}

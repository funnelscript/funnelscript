world MarketTrial {
  agent Shopper {
    state converted: bool = false;
    state engagement_score: float = 0.0;
    event Impression(conversion_probability: float);

    rule Respond on event Impression {
      transition converted = sample bernoulli(payload.conversion_probability);
      transition engagement_score = sample uniform(0.0, 1.0);
    }
  }
}

strategy ECommerce_Black_Friday_2026 {
  metadata {
    author = "Marketing Engineer";
    industry = "Consumer Electronics";
    currency = "USD";
  }

  environment {
    market_volatility = "high";
    competitor_activity = "aggressive";
  }

  entities {
    budget main_budget {
      total = 25000;
      max_cpc = 1.20;
    }

    audience aud_01 {
      type = "cold";
      size = 500000;
      affinity = 0.55;
      price_sensitivity = 0.40;
      fomo = 0.70;
    }

    touchpoint tp_meta_ads {
      type = "paid_traffic";
      platform = "Meta";
      base_cpc = 0.45;
      creative_score = 0.85;
    }

    touchpoint tp_landing_page {
      type = "conversion_surface";
      conversion_rate = 0.045;
    }

    touchpoint tp_cart_email {
      type = "retargeting_channel";
      medium = "Email";
    }
  }

  flow {
    trigger TrafficDrive from aud_01 via tp_meta_ads to tp_landing_page;
  }

  simulate {
    agents = 50000;
    duration = 14days;
    trials = 100;
  }
}

import pytest
import numpy as np
from funnelscript.core.agent import Agent, ConsumerState, PsychographicProfile


def test_agent_profile_clamping():
    profile = PsychographicProfile(
        brand_affinity=1.5,  # should clamp to 1.0
        price_sensitivity=-0.2,  # should clamp to 0.0
        fomo_index=0.8,
        wallet_balance=-10.0,  # should clamp to 0.0
    )
    assert profile.brand_affinity == 1.0
    assert profile.price_sensitivity == 0.0
    assert profile.wallet_balance == 0.0


def test_wallet_insolvency_prevents_purchase():
    # Agent with only $50 cannot buy a $120 product
    agent = Agent(
        "poor_agent",
        PsychographicProfile(brand_affinity=0.9, price_sensitivity=0.1, fomo_index=0.9, wallet_balance=50.0),
    )
    converted, prob = agent.evaluate_purchase(product_price=120.0)
    assert converted is False
    assert prob == 0.0
    assert agent.state == ConsumerState.CHURNED
    assert "Insolvency bounce" in agent.decision_log[-1]


def test_ad_fatigue_decays_click_probability():
    agent = Agent.create_loyal_vip("vip_decay_test")
    # Repeated ad exposures should cause decay
    _, p1 = agent.evaluate_ad_exposure(base_ctr=0.10, fatigue_decay=0.20)
    _, p2 = agent.evaluate_ad_exposure(base_ctr=0.10, fatigue_decay=0.20)
    _, p3 = agent.evaluate_ad_exposure(base_ctr=0.10, fatigue_decay=0.20)

    assert p1 > p2 > p3
    assert agent.ad_exposures == 3


def test_discount_increases_purchase_probability():
    rng = np.random.default_rng(42)
    # Compare identical agents with 0% vs 30% discount
    a1 = Agent.create_skeptic_bargain_hunter("bh_full_price")
    a2 = Agent.create_skeptic_bargain_hunter("bh_discounted")

    _, p_no_discount = a1.evaluate_purchase(product_price=50.0, discount_percentage=0.0, rng=rng)
    _, p_discounted = a2.evaluate_purchase(product_price=50.0, discount_percentage=30.0, rng=rng)

    assert p_discounted > p_no_discount

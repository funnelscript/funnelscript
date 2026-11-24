"""Verification tests for Phase 4: Numerical Stability and Guardrails in Marketing Science Kernels.

Validates:
1. HillSaturation overflow-safe piecewise formulation across extreme domains [0, 1e30].
2. Exact analytical inflection f(K_sat) == 0.5 * V_max and gradient verification.
3. Adstock steady-state conservation A_inf = S / (1 - lambda) and Weibull convolution.
4. Discrete time-delay distributions (Gamma, Log-Normal, Negative Binomial) exact mass conservation sum(p) == 1.0.
5. Cohort retention (sBG, Weibull) and cumulative LTV payback periods.
6. Creative fatigue, frequency decay, and audience market exhaustion.
7. Cross-channel brand halo and competitive cannibalization.
8. Keyed-RNG stochastic auction shock reproducibility.
"""

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from funnelscript.stdlib.marketing.kernels import (
    Adstock,
    AuctionEnvironment,
    CohortRetention,
    CreativeFatigue,
    CrossChannelInteraction,
    DelayDistribution,
    HillSaturation,
)


class TestHillSaturationNumericalStability:
    def test_half_saturation_exact_inflection(self):
        v_max = 50000.0
        k_sat = 12500.0
        hill = HillSaturation(v_max=v_max, k_sat=k_sat, alpha=1.2)
        response = hill.evaluate(k_sat)
        assert pytest.approx(response, rel=1e-9) == 0.5 * v_max

    def test_zero_spend_exact_zero(self):
        hill = HillSaturation(v_max=10000.0, k_sat=2000.0, alpha=0.9)
        assert hill.evaluate(0.0) == 0.0
        assert hill.evaluate(-50.0) == 0.0

    def test_extreme_astronomical_spend_does_not_overflow_or_nan(self):
        hill = HillSaturation(v_max=1000.0, k_sat=100.0, alpha=4.0)
        # Even with spend 1e30, response must cleanly asymptote to v_max without overflow or NaN
        resp = hill.evaluate(1e30)
        assert not math.isnan(resp)
        assert not math.isinf(resp)
        assert pytest.approx(resp, rel=1e-5) == 1000.0

    def test_marginal_gradient_finite_difference(self):
        hill = HillSaturation(v_max=20000.0, k_sat=5000.0, alpha=1.5)
        spend = 6000.0
        analytical_grad = hill.marginal_response(spend)

        eps = 1e-5
        numerical_grad = (hill.evaluate(spend + eps) - hill.evaluate(spend - eps)) / (2.0 * eps)
        assert pytest.approx(analytical_grad, rel=1e-3) == numerical_grad

    def test_inverse_response_monotonicity(self):
        hill = HillSaturation(v_max=15000.0, k_sat=3500.0, alpha=0.85)
        for target in [1000.0, 5000.0, 7500.0, 12000.0, 14500.0]:
            s_req = hill.inverse(target)
            actual_resp = hill.evaluate(s_req)
            assert pytest.approx(actual_resp, rel=1e-4) == target

    @given(
        spend=st.floats(min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False),
        alpha=st.floats(min_value=0.2, max_value=4.0, allow_nan=False, allow_infinity=False),
        k_sat=st.floats(min_value=10.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_hypothesis_hill_bounds(self, spend, alpha, k_sat):
        hill = HillSaturation(v_max=10000.0, k_sat=k_sat, alpha=alpha)
        resp = hill.evaluate(spend)
        assert 0.0 <= resp <= 10000.0
        assert not math.isnan(resp)
        assert not math.isinf(resp)


class TestAdstockConservation:
    def test_steady_state_geometric_conservation(self):
        spend_rate = 100.0
        decay = 0.8
        expected_steady_state = Adstock.steady_state_geometric(spend_rate, decay)
        assert pytest.approx(expected_steady_state, rel=1e-6) == 500.0

        # Run 50 daily periods of constant spend
        sim_spend = np.full(50, spend_rate)
        adstocked = Adstock.geometric(sim_spend, decay)
        # Final period should closely approach 500.0
        assert pytest.approx(adstocked[-1], rel=1e-2) == expected_steady_state

    def test_geometric_normalized_energy_conservation(self):
        spend = np.array([500.0, 0.0, 0.0, 0.0, 0.0])
        decay = 0.5
        norm_adstocked = Adstock.geometric_normalized(spend, decay)
        # In normalized mode, A_0 = (1 - lambda) * S_0 = 250, A_1 = 125, etc.
        assert norm_adstocked[0] == 250.0
        assert norm_adstocked[1] == 125.0

    def test_weibull_normalization_and_convolution(self):
        spend = np.array([1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        weibull = Adstock.weibull(spend, shape=2.0, scale=3.0, max_lag=7, normalize=True)
        assert len(weibull) == len(spend)
        assert np.all(weibull >= 0.0)
        assert pytest.approx(float(np.sum(weibull)), rel=1e-5) == 1000.0


class TestDelayDistributionMassConservation:
    def test_discrete_gamma_kernel_sums_exactly_to_one(self):
        kernel = DelayDistribution.discretize_gamma(mean_days=4.5, std_days=2.0, max_days=30)
        assert len(kernel) == 31
        assert pytest.approx(float(np.sum(kernel)), abs=1e-12) == 1.0
        assert all(p >= 0.0 for p in kernel)

    def test_discrete_lognormal_kernel_sums_exactly_to_one(self):
        kernel = DelayDistribution.discretize_lognormal(mean_days=3.0, std_days=1.5, max_days=20)
        assert len(kernel) == 21
        assert pytest.approx(float(np.sum(kernel)), abs=1e-12) == 1.0
        assert all(p >= 0.0 for p in kernel)

    def test_discrete_negative_binomial_sums_exactly_to_one(self):
        kernel = DelayDistribution.discretize_negative_binomial(r=5.0, p=0.4, max_days=25)
        assert len(kernel) == 26
        assert pytest.approx(float(np.sum(kernel)), abs=1e-12) == 1.0


class TestCohortRetentionAndMarketingScience:
    def test_sbg_and_weibull_survival_curves(self):
        sbg = CohortRetention.shifted_beta_geometric(12, alpha=1.0, beta=4.0)
        assert sbg[0] == 1.0
        assert all(sbg[t] < sbg[t - 1] for t in range(1, len(sbg)))

        weib = CohortRetention.weibull_survival(12, shape=1.2, scale=8.0)
        assert weib[0] == 1.0
        assert all(weib[t] < weib[t - 1] for t in range(1, len(weib)))

    def test_cumulative_ltv_and_payback(self):
        survival = np.array([1.0, 0.8, 0.6, 0.5, 0.4])
        arpu = 50.0  # 50 USD/month
        ltv = CohortRetention.project_cumulative_ltv(survival, arpu, discount_rate_per_period=0.0)
        # Period 0: 50. Period 1: 50 + 40 = 90. Period 2: 90 + 30 = 120
        assert ltv[0] == 50.0
        assert ltv[1] == 90.0
        assert ltv[2] == 120.0

        # CAC = 85 -> payback achieved at month 1 (90 >= 85)
        payback = CohortRetention.compute_payback_period(ltv, cac=85.0)
        assert payback == 1

    def test_creative_fatigue_and_audience_exhaustion(self):
        # CTR drops exponentially when frequency exceeds cap of 3.0
        ctr_low_freq = CreativeFatigue.frequency_decay_ctr(2.5, base_ctr=0.03, frequency_cap=3.0)
        ctr_high_freq = CreativeFatigue.frequency_decay_ctr(5.0, base_ctr=0.03, frequency_cap=3.0)
        assert ctr_low_freq == 0.03
        assert ctr_high_freq < 0.03

        # Audience saturation
        reached, inc_rate = CreativeFatigue.audience_exhaustion(cumulative_impressions=500_000, market_size=1_000_000)
        assert 0.0 < reached < 1_000_000
        assert 0.0 < inc_rate < 1.0

    def test_cross_channel_brand_halo_and_cannibalization(self):
        # Upper funnel brand adstock reduces required half-saturation spend K
        base_k = 5000.0
        k_boosted = CrossChannelInteraction.brand_halo_k_sat(base_k, brand_adstock=100.0, halo_coefficient=0.02)
        assert k_boosted < base_k
        assert pytest.approx(k_boosted, rel=1e-5) == base_k / (1.0 + 2.0)

        # Cannibalization
        base_organic = 1000.0
        d_cannibalized = CrossChannelInteraction.channel_cannibalization(base_organic, competing_channel_adstock=50.0, cannibalization_coefficient=0.01)
        assert d_cannibalized < base_organic

    def test_keyed_auction_shock_reproducibility(self):
        base_cpm = 20.0
        # Same seed, tick, channel produces bit-exact identical CPM shock across calls
        s1 = AuctionEnvironment.keyed_lognormal_cpm_shock(base_cpm, seed=42, day_tick=7, channel_name="MetaFeed")
        s2 = AuctionEnvironment.keyed_lognormal_cpm_shock(base_cpm, seed=42, day_tick=7, channel_name="MetaFeed")
        assert s1 == s2
        assert s1 > 0.0

        # Different day tick produces different shock
        s3 = AuctionEnvironment.keyed_lognormal_cpm_shock(base_cpm, seed=42, day_tick=8, channel_name="MetaFeed")
        assert s1 != s3

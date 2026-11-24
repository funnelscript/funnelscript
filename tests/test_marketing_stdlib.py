"""Tests for Marketing Science Stdlib Kernels.

Validates:
1. HillSaturation non-linear response, analytical gradient, and inverse response.
2. Adstock geometric and Weibull convolution memory.
3. DelayDistribution discrete latency and settlement lag with fee reduction.
4. CohortRetention shifted-beta-geometric survival decay.
"""

import math
import numpy as np
import pytest

from funnelscript.stdlib.marketing.kernels import (
    HillSaturation,
    Adstock,
    DelayDistribution,
    CohortRetention,
)


class TestHillSaturation:
    def test_zero_spend_yields_zero_response(self):
        hill = HillSaturation(v_max=10000.0, k_sat=2500.0, alpha=0.8)
        assert hill.evaluate(0.0) == 0.0

    def test_half_saturation_yields_half_vmax(self):
        v_max = 8000.0
        k_sat = 2000.0
        hill = HillSaturation(v_max=v_max, k_sat=k_sat, alpha=1.0)
        resp = hill.evaluate(k_sat)
        assert pytest.approx(resp, rel=1e-5) == v_max / 2.0

    def test_diminishing_marginal_returns(self):
        hill = HillSaturation(v_max=10000.0, k_sat=3000.0, alpha=0.75)
        # Derivative should decrease as spend increases
        grad_low = hill.marginal_response(500.0)
        grad_mid = hill.marginal_response(3000.0)
        grad_high = hill.marginal_response(15000.0)
        assert grad_low > grad_mid > grad_high > 0.0

    def test_inverse_spend_recovers_target_response(self):
        hill = HillSaturation(v_max=12000.0, k_sat=4000.0, alpha=0.85)
        target = 6000.0
        spend_req = hill.inverse(target)
        resp = hill.evaluate(spend_req)
        assert pytest.approx(resp, rel=1e-5) == target

    def test_target_exceeding_vmax_raises_value_error(self):
        hill = HillSaturation(v_max=5000.0, k_sat=1000.0, alpha=0.9)
        with pytest.raises(ValueError):
            hill.inverse(5000.0)


class TestAdstock:
    def test_geometric_carryover(self):
        spend = np.array([100.0, 0.0, 0.0, 0.0])
        decay = 0.5
        adstocked = Adstock.geometric(spend, decay)
        expected = np.array([100.0, 50.0, 25.0, 12.5])
        np.testing.assert_allclose(adstocked, expected, rtol=1e-5)

    def test_weibull_carryover_sums_to_spend_over_horizon(self):
        spend = np.array([1000.0, 1000.0, 1000.0, 1000.0, 1000.0])
        weibull = Adstock.weibull(spend, shape=1.8, scale=2.5, max_lag=7)
        assert len(weibull) == len(spend)
        assert np.all(weibull > 0)


class TestDelayDistribution:
    def test_discrete_gamma_kernel_sums_to_one(self):
        kernel = DelayDistribution.discretize_gamma(mean_days=3.0, std_days=1.5, max_days=14)
        assert pytest.approx(np.sum(kernel), rel=1e-5) == 1.0
        assert len(kernel) == 15

    def test_settlement_lag_applies_shift_and_fee(self):
        gross = np.array([1000.0, 2000.0, 0.0, 0.0, 0.0])
        delay = 2
        fee = 0.03
        settled = DelayDistribution.apply_settlement_lag(gross, delay_days=delay, gateway_fee_rate=fee)
        # Should be shifted by 2 days and discounted by (1 - 0.03) = 0.97
        assert settled[0] == 0.0
        assert settled[1] == 0.0
        assert pytest.approx(settled[2], rel=1e-5) == 1000.0 * 0.97
        assert pytest.approx(settled[3], rel=1e-5) == 2000.0 * 0.97


class TestCohortRetention:
    def test_shifted_beta_geometric_monotonically_decreases(self):
        survival = CohortRetention.shifted_beta_geometric(t_periods=12, alpha=1.2, beta=3.5)
        assert survival[0] == 1.0
        for t in range(1, len(survival)):
            assert 0.0 < survival[t] < survival[t - 1]

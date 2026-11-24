"""Marketing Science Kernels and Domain Operators.

Provides fundamental quantitative marketing operators for:
1. Hill Function Diminishing Returns & Saturation (overflow-safe formulation)
2. Geometric and Weibull Adstock Carryover Memory (exact energy conservation)
3. Discrete Latency Delay Queues (Gamma, Log-Normal, Negative Binomial with mass conservation)
4. Cohort Retention Survival Curves (sBG, Weibull, and LTV projections)
5. Creative Fatigue, Frequency Capping & Finite Audience Exhaustion
6. Cross-Channel Interaction & Halo Effects
7. Auction Seasonality & Keyed-RNG Stochastic Volatility
8. Multi-Touch Attribution (MTA) & Incrementality Bridge (Shapley, Markov Chain, Heuristics)
"""

from __future__ import annotations

import hashlib
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


class HillSaturation:
    """Non-linear diminishing returns operator based on the Hill function.

    Response(S) = (V_max * S^alpha) / (K_sat^alpha + S^alpha)

    Uses a normalized, piecewise log-space formulation to eliminate floating-point
    overflow across the entire real domain [0, Inf).

    Attributes:
        v_max: Maximum asymptotic response ceiling.
        k_sat: Half-saturation spend parameter (spend where response reaches 50% of v_max).
        alpha: Hill shape parameter controlling curvature.
    """

    def __init__(self, v_max: float, k_sat: float, alpha: float = 0.8) -> None:
        if v_max <= 0:
            raise ValueError(f"v_max must be positive, got {v_max}")
        if k_sat <= 0:
            raise ValueError(f"k_sat must be positive, got {k_sat}")
        if alpha <= 0 or alpha > 10.0:
            raise ValueError(f"alpha must be in (0, 10.0], got {alpha}")

        self.v_max = float(v_max)
        self.k_sat = float(k_sat)
        self.alpha = float(alpha)

    def evaluate(self, spend: float | np.ndarray) -> float | np.ndarray:
        """Evaluates marketing response for a given spend level with overflow safety."""
        is_scalar = np.isscalar(spend)
        s = np.asarray(spend, dtype=float)
        s_safe = np.maximum(0.0, s)

        with np.errstate(divide="ignore", invalid="ignore"):
            # When s > k_sat: v_max / (1 + (k_sat / s)^alpha), where k_sat / s < 1
            ratio_high = np.where(s_safe > self.k_sat, self.k_sat / np.maximum(1e-12, s_safe), 0.0)
            resp_high = self.v_max / (1.0 + np.power(ratio_high, self.alpha))

            # When s <= k_sat: v_max * (s / k_sat)^alpha / (1 + (s / k_sat)^alpha), where s / k_sat <= 1
            ratio_low = np.where(s_safe <= self.k_sat, s_safe / self.k_sat, 0.0)
            u_alpha = np.power(ratio_low, self.alpha)
            resp_low = np.where(s_safe <= 0.0, 0.0, self.v_max * (u_alpha / (1.0 + u_alpha)))

            response = np.where(s_safe > self.k_sat, resp_high, resp_low)

        return float(response) if is_scalar else response

    def marginal_response(self, spend: float | np.ndarray) -> float | np.ndarray:
        """Computes analytical first derivative d(Response)/d(Spend) safely.

        d(Response)/dS = (V_max * alpha * K^alpha * S^(alpha - 1)) / (K^alpha + S^alpha)^2
        """
        is_scalar = np.isscalar(spend)
        s = np.asarray(spend, dtype=float)

        with np.errstate(divide="ignore", invalid="ignore"):
            s_pos = np.maximum(1e-12, s)

            # High region: s > k_sat
            ratio_k_s = self.k_sat / s_pos
            pow_k_s = np.power(ratio_k_s, self.alpha)
            grad_high = (self.v_max * self.alpha / s_pos) * (pow_k_s / np.square(1.0 + pow_k_s))

            # Low region: 0 < s <= k_sat
            ratio_s_k = s_pos / self.k_sat
            pow_s_k = np.power(ratio_s_k, self.alpha)
            denom_low = np.square(1.0 + pow_s_k)
            pow_s_k_minus_1 = np.power(ratio_s_k, self.alpha - 1.0)
            grad_low = (self.v_max * self.alpha / self.k_sat) * (pow_s_k_minus_1 / denom_low)

            grad = np.where(s <= 0.0, 0.0, np.where(s > self.k_sat, grad_high, grad_low))

        return float(grad) if is_scalar else grad

    def inverse(self, target_response: float) -> float:
        """Computes required spend to achieve a desired response level.

        S = K_sat * (R / (V_max - R))^(1 / alpha)
        """
        if target_response <= 0.0:
            return 0.0
        if target_response >= self.v_max:
            raise ValueError(
                f"Target response {target_response} exceeds asymptotic ceiling V_max={self.v_max}"
            )
        ratio = target_response / (self.v_max - target_response)
        return self.k_sat * math.pow(ratio, 1.0 / self.alpha)


class Adstock:
    """Carryover decay operators modeling consumer memory and advertising lag."""

    @staticmethod
    def geometric(spend: np.ndarray | list[float], decay_rate: float) -> np.ndarray:
        """Applies geometric carryover decay: A_t = S_t + decay_rate * A_{t-1}."""
        if not (0.0 <= decay_rate < 1.0):
            raise ValueError(f"decay_rate must be in [0, 1), got {decay_rate}")

        s = np.asarray(spend, dtype=float)
        if len(s) == 0:
            return np.array([], dtype=float)

        adstocked = np.zeros_like(s)
        accum = 0.0
        for t in range(len(s)):
            accum = s[t] + decay_rate * accum
            adstocked[t] = accum

        return adstocked

    @staticmethod
    def geometric_normalized(spend: np.ndarray | list[float], decay_rate: float) -> np.ndarray:
        """Geometric carryover with weights normalized so sum of weights equals 1.0 (energy conserving).

        w_k = (1 - decay_rate) * decay_rate^k
        """
        if not (0.0 <= decay_rate < 1.0):
            raise ValueError(f"decay_rate must be in [0, 1), got {decay_rate}")

        s = np.asarray(spend, dtype=float)
        if len(s) == 0:
            return np.array([], dtype=float)

        if decay_rate == 0.0:
            return np.copy(s)

        adstocked = np.zeros_like(s)
        accum = 0.0
        for t in range(len(s)):
            accum = (1.0 - decay_rate) * s[t] + decay_rate * accum
            adstocked[t] = accum
        return adstocked

    @staticmethod
    def steady_state_geometric(daily_spend: float, decay_rate: float) -> float:
        """Computes steady-state equilibrium carryover A_inf = S / (1 - lambda)."""
        if not (0.0 <= decay_rate < 1.0):
            raise ValueError(f"decay_rate must be in [0, 1), got {decay_rate}")
        return daily_spend / (1.0 - decay_rate)

    @staticmethod
    def weibull(
        spend: np.ndarray | list[float],
        shape: float = 2.0,
        scale: float = 3.0,
        max_lag: int = 14,
        normalize: bool = True,
    ) -> np.ndarray:
        """Applies Weibull adstock convolution modeling peak-delay and delayed decay.

        Normalized weights ensure exact spend energy conservation.
        """
        if shape <= 0 or scale <= 0:
            raise ValueError("Weibull shape and scale must be positive")
        if max_lag <= 0:
            raise ValueError("max_lag must be a positive integer")

        s = np.asarray(spend, dtype=float)
        if len(s) == 0:
            return np.array([], dtype=float)

        lags = np.arange(max_lag, dtype=float)
        weights = np.zeros(max_lag, dtype=float)
        for i, x in enumerate(lags):
            if x == 0:
                weights[i] = 1.0
            else:
                weights[i] = (shape / scale) * math.pow(x / scale, shape - 1.0) * math.exp(-math.pow(x / scale, shape))

        if normalize:
            w_sum = np.sum(weights)
            if w_sum > 0:
                weights /= w_sum

        padded = np.convolve(s, weights, mode="full")
        return padded[: len(s)]


class DelayDistribution:
    """Models temporal latency between marketing touchpoints and financial settlement.

    Enforces exact discrete probability mass conservation: sum(probs) == 1.0.
    """

    @staticmethod
    def discretize_gamma(mean_days: float, std_days: float, max_days: int = 30) -> np.ndarray:
        """Constructs a discrete daily delay kernel using Gamma CDF with exact mass conservation."""
        if mean_days <= 0 or std_days <= 0:
            raise ValueError("mean_days and std_days must be positive")
        if max_days <= 0:
            raise ValueError("max_days must be positive")

        from scipy.stats import gamma

        k = (mean_days / std_days) ** 2
        theta = (std_days ** 2) / mean_days

        days = np.arange(max_days + 1, dtype=float)
        cdfs = gamma.cdf(np.maximum(0.0, days + 0.5), a=k, scale=theta)
        cdfs[0] = gamma.cdf(0.5, a=k, scale=theta)

        probs = np.zeros(max_days + 1, dtype=float)
        probs[0] = cdfs[0]
        probs[1:] = np.diff(cdfs)
        # Fold upper tail mass into the final bin so no mass is lost
        tail = max(0.0, 1.0 - float(np.sum(probs)))
        probs[-1] += tail
        probs = np.maximum(0.0, probs)
        probs /= np.sum(probs)
        return probs

    @staticmethod
    def discretize_lognormal(mean_days: float, std_days: float, max_days: int = 30) -> np.ndarray:
        """Constructs a discrete daily delay kernel using Log-Normal distribution with exact mass conservation."""
        if mean_days <= 0 or std_days <= 0:
            raise ValueError("mean_days and std_days must be positive")
        if max_days <= 0:
            raise ValueError("max_days must be positive")

        from scipy.stats import lognorm

        var = std_days**2
        mu = math.log((mean_days**2) / math.sqrt(mean_days**2 + var))
        sigma = math.sqrt(math.log(1.0 + var / (mean_days**2)))

        days = np.arange(max_days + 1, dtype=float)
        cdfs = lognorm.cdf(np.maximum(0.0, days + 0.5), s=sigma, scale=math.exp(mu))
        probs = np.zeros(max_days + 1, dtype=float)
        probs[0] = cdfs[0]
        probs[1:] = np.diff(cdfs)
        tail = max(0.0, 1.0 - float(np.sum(probs)))
        probs[-1] += tail
        probs = np.maximum(0.0, probs)
        probs /= np.sum(probs)
        return probs

    @staticmethod
    def discretize_negative_binomial(r: float, p: float, max_days: int = 30) -> np.ndarray:
        """Constructs discrete daily delay kernel from Negative Binomial distribution."""
        if r <= 0 or not (0 < p <= 1.0):
            raise ValueError("r must be positive and p in (0, 1]")

        from scipy.stats import nbinom

        days = np.arange(max_days + 1, dtype=int)
        pmf = nbinom.pmf(days, n=r, p=p)
        pmf = np.maximum(0.0, pmf)
        tail = max(0.0, 1.0 - float(np.sum(pmf)))
        pmf[-1] += tail
        pmf /= np.sum(pmf)
        return pmf

    @staticmethod
    def apply_settlement_lag(
        gross_revenue: np.ndarray,
        delay_days: int,
        gateway_fee_rate: float = 0.029,
        reserve_rate: float = 0.0,
    ) -> np.ndarray:
        """Applies discrete settlement delay and merchant processing fees to gross revenue."""
        if delay_days < 0:
            raise ValueError("delay_days cannot be negative")

        rev = np.asarray(gross_revenue, dtype=float)
        n = len(rev)
        settled = np.zeros(n, dtype=float)
        net_multiplier = max(0.0, 1.0 - gateway_fee_rate - reserve_rate)

        for t in range(n):
            target_day = t + delay_days
            if target_day < n:
                settled[target_day] += rev[t] * net_multiplier

        return settled


class CohortRetention:
    """Models cohort survival and recurring customer lifetime value (LTV) decay."""

    @staticmethod
    def shifted_beta_geometric(t_periods: int, alpha: float = 1.0, beta: float = 3.0) -> np.ndarray:
        """Shifted-Beta-Geometric survival function for contractual customer retention.

        S(t) = P(T > t) = B(alpha, beta + t) / B(alpha, beta)
        """
        if alpha <= 0 or beta <= 0:
            raise ValueError("alpha and beta must be positive")
        if t_periods <= 0:
            return np.array([], dtype=float)

        survival = np.zeros(t_periods, dtype=float)
        survival[0] = 1.0

        for t in range(1, t_periods):
            survival[t] = survival[t - 1] * (beta + t - 1.0) / (alpha + beta + t - 1.0)

        return survival

    @staticmethod
    def weibull_survival(t_periods: int, shape: float = 1.5, scale: float = 12.0) -> np.ndarray:
        """Weibull survival curve: S(t) = exp(-(t / scale)^shape)."""
        if shape <= 0 or scale <= 0:
            raise ValueError("shape and scale must be positive")
        if t_periods <= 0:
            return np.array([], dtype=float)

        t = np.arange(t_periods, dtype=float)
        return np.exp(-np.power(t / scale, shape))

    @staticmethod
    def project_cumulative_ltv(
        retention_curve: np.ndarray | list[float],
        arpu: float,
        discount_rate_per_period: float = 0.0,
    ) -> np.ndarray:
        """Computes cumulative discounted LTV stream across cohort lifetime periods."""
        s = np.asarray(retention_curve, dtype=float)
        ltv = np.zeros_like(s)
        cum = 0.0
        for t, surv in enumerate(s):
            discount = 1.0 / math.pow(1.0 + discount_rate_per_period, t)
            cum += arpu * surv * discount
            ltv[t] = cum
        return ltv

    @staticmethod
    def compute_payback_period(cumulative_ltv: np.ndarray | list[float], cac: float) -> int | None:
        """Finds first period where cumulative LTV exceeds CAC, or None if never within horizon."""
        ltv = np.asarray(cumulative_ltv, dtype=float)
        for t, val in enumerate(ltv):
            if val >= cac:
                return t
        return None


class CreativeFatigue:
    """Models creative fatigue, ad frequency saturation, and addressable audience exhaustion."""

    @staticmethod
    def frequency_decay_ctr(
        frequency: float | np.ndarray,
        base_ctr: float = 0.025,
        decay_rate: float = 0.15,
        frequency_cap: float = 3.0,
    ) -> float | np.ndarray:
        """CTR(f) = base_ctr * exp(-decay_rate * max(0, f - frequency_cap))."""
        if base_ctr <= 0:
            raise ValueError("base_ctr must be positive")
        is_scalar = np.isscalar(frequency)
        f = np.asarray(frequency, dtype=float)
        excess = np.maximum(0.0, f - frequency_cap)
        decayed = base_ctr * np.exp(-decay_rate * excess)
        return float(decayed) if is_scalar else decayed

    @staticmethod
    def frequency_decay_cvr(
        frequency: float | np.ndarray,
        base_cvr: float = 0.02,
        decay_rate: float = 0.10,
        frequency_cap: float = 3.0,
    ) -> float | np.ndarray:
        """CVR(f) = base_cvr * exp(-decay_rate * max(0, f - frequency_cap))."""
        if base_cvr <= 0:
            raise ValueError("base_cvr must be positive")
        is_scalar = np.isscalar(frequency)
        f = np.asarray(frequency, dtype=float)
        excess = np.maximum(0.0, f - frequency_cap)
        decayed = base_cvr * np.exp(-decay_rate * excess)
        return float(decayed) if is_scalar else decayed

    @staticmethod
    def audience_exhaustion(
        cumulative_impressions: float | np.ndarray,
        market_size: float = 1_000_000.0,
    ) -> tuple[float | np.ndarray, float | np.ndarray]:
        """Models finite audience pool saturation.

        Reached = market_size * (1 - exp(-impressions / market_size))
        IncrementalReachRate = exp(-impressions / market_size)
        """
        if market_size <= 0:
            raise ValueError("market_size must be positive")
        is_scalar = np.isscalar(cumulative_impressions)
        imps = np.maximum(0.0, np.asarray(cumulative_impressions, dtype=float))
        frac = imps / market_size
        exp_decay = np.exp(-frac)
        reached = market_size * (1.0 - exp_decay)
        inc_rate = exp_decay

        if is_scalar:
            return float(reached), float(inc_rate)
        return reached, inc_rate


class CrossChannelInteraction:
    """Models upper-funnel halo effects and cross-channel cannibalization."""

    @staticmethod
    def brand_halo_k_sat(
        base_k_sat: float,
        brand_adstock: float,
        halo_coefficient: float = 0.05,
    ) -> float:
        """Modulates lower-funnel half-saturation spend K based on upper-funnel brand adstock:

        K_eff = base_k_sat / (1 + halo_coefficient * brand_adstock)
        Brand adstock makes performance channels reach 50% saturation with less spend.
        """
        if base_k_sat <= 0:
            raise ValueError("base_k_sat must be positive")
        if halo_coefficient < 0:
            raise ValueError("halo_coefficient cannot be negative")
        return base_k_sat / (1.0 + halo_coefficient * max(0.0, brand_adstock))

    @staticmethod
    def channel_cannibalization(
        base_demand: float | np.ndarray,
        competing_channel_adstock: float | np.ndarray,
        cannibalization_coefficient: float = 0.03,
    ) -> float | np.ndarray:
        """Reduces organic/baseline demand due to paid cannibalization:

        Demand_eff = max(0, base_demand * (1 - cannibalization_coefficient * competing_adstock))
        """
        is_scalar = np.isscalar(base_demand) and np.isscalar(competing_channel_adstock)
        d = np.asarray(base_demand, dtype=float)
        a = np.maximum(0.0, np.asarray(competing_channel_adstock, dtype=float))
        eff = np.maximum(0.0, d * (1.0 - cannibalization_coefficient * a))
        return float(eff) if is_scalar else eff


class AuctionEnvironment:
    """Models deterministic calendar seasonality and keyed-RNG auction volatility."""

    DAY_OF_WEEK_FACTORS = (1.05, 1.02, 1.00, 0.98, 0.95, 0.92, 1.08)  # Mon - Sun

    @classmethod
    def day_of_week_multiplier(cls, day_index: int) -> float:
        """Deterministic day-of-week CPM seasonality multiplier."""
        return cls.DAY_OF_WEEK_FACTORS[day_index % 7]

    @staticmethod
    def keyed_lognormal_cpm_shock(
        base_cpm: float,
        seed: int,
        day_tick: int,
        channel_name: str,
        sigma: float = 0.2,
    ) -> float:
        """Keyed-RNG deterministic Log-Normal auction shock with zero global RNG dependency.

        Guarantees 100% bit-exact reproducibility across independent Python processes.
        """
        if base_cpm <= 0:
            raise ValueError("base_cpm must be positive")

        key_bytes = f"{seed}:{day_tick}:{channel_name}".encode()
        digest = hashlib.sha256(key_bytes).digest()
        val_u1 = int.from_bytes(digest[:4], "big") / 4294967296.0
        val_u2 = int.from_bytes(digest[4:8], "big") / 4294967296.0
        u1 = max(1e-12, min(0.999999999999, val_u1))
        u2 = max(1e-12, min(0.999999999999, val_u2))
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        shock = math.exp(sigma * z - 0.5 * (sigma**2))
        return base_cpm * shock


@dataclass(frozen=True)
class Touchpoint:
    channel: str
    timestamp: float
    cost: float = 0.0


@dataclass(frozen=True)
class ConversionPath:
    user_id: str
    touches: tuple[Touchpoint, ...]
    converted: bool
    conversion_value: float = 0.0


class AttributionEngine:
    """Read-only Multi-Touch Attribution (MTA) overlay strictly decoupled from simulation state.

    Supports:
    - First-Touch Attribution
    - Last-Touch Attribution
    - Linear Attribution
    - Time-Decay Attribution
    - Position-Based (U-Shaped: 40/40/20) Attribution
    - Shapley Value Attribution (Cooperative game theory)
    - First-Order Markov Chain Attribution (Removal effect)
    - Platform Over-Reporting Factor vs Incrementality
    """

    @staticmethod
    def first_touch(paths: Sequence[ConversionPath]) -> dict[str, float]:
        credits: dict[str, float] = {}
        for path in paths:
            if path.converted and path.touches:
                first = path.touches[0].channel
                credits[first] = credits.get(first, 0.0) + (path.conversion_value or 1.0)
        return credits

    @staticmethod
    def last_touch(paths: Sequence[ConversionPath]) -> dict[str, float]:
        credits: dict[str, float] = {}
        for path in paths:
            if path.converted and path.touches:
                last = path.touches[-1].channel
                credits[last] = credits.get(last, 0.0) + (path.conversion_value or 1.0)
        return credits

    @staticmethod
    def linear(paths: Sequence[ConversionPath]) -> dict[str, float]:
        credits: dict[str, float] = {}
        for path in paths:
            if path.converted and path.touches:
                val = path.conversion_value or 1.0
                n = len(path.touches)
                share = val / n
                for t in path.touches:
                    credits[t.channel] = credits.get(t.channel, 0.0) + share
        return credits

    @staticmethod
    def time_decay(
        paths: Sequence[ConversionPath],
        half_life_days: float = 7.0,
    ) -> dict[str, float]:
        if half_life_days <= 0:
            raise ValueError("half_life_days must be positive")
        credits: dict[str, float] = {}
        decay_constant = math.log(2.0) / half_life_days

        for path in paths:
            if path.converted and path.touches:
                conv_time = path.touches[-1].timestamp
                weights = [math.exp(-decay_constant * max(0.0, conv_time - t.timestamp)) for t in path.touches]
                total_w = sum(weights)
                val = path.conversion_value or 1.0
                for t, w in zip(path.touches, weights):
                    share = (w / total_w) * val if total_w > 0 else 0.0
                    credits[t.channel] = credits.get(t.channel, 0.0) + share
        return credits

    @staticmethod
    def position_based(
        paths: Sequence[ConversionPath],
        first_weight: float = 0.40,
        last_weight: float = 0.40,
    ) -> dict[str, float]:
        credits: dict[str, float] = {}
        middle_weight = max(0.0, 1.0 - first_weight - last_weight)

        for path in paths:
            if path.converted and path.touches:
                val = path.conversion_value or 1.0
                n = len(path.touches)
                if n == 1:
                    c = path.touches[0].channel
                    credits[c] = credits.get(c, 0.0) + val
                elif n == 2:
                    w1 = first_weight / (first_weight + last_weight)
                    w2 = last_weight / (first_weight + last_weight)
                    c1 = path.touches[0].channel
                    c2 = path.touches[1].channel
                    credits[c1] = credits.get(c1, 0.0) + val * w1
                    credits[c2] = credits.get(c2, 0.0) + val * w2
                else:
                    c_first = path.touches[0].channel
                    c_last = path.touches[-1].channel
                    credits[c_first] = credits.get(c_first, 0.0) + val * first_weight
                    credits[c_last] = credits.get(c_last, 0.0) + val * last_weight
                    mid_share = (val * middle_weight) / (n - 2)
                    for t in path.touches[1:-1]:
                        credits[t.channel] = credits.get(t.channel, 0.0) + mid_share
        return credits

    @staticmethod
    def shapley(
        channels: Sequence[str],
        coalition_values: dict[frozenset[str], float],
    ) -> dict[str, float]:
        """Calculates exact Shapley values for channels across coalition conversion values."""
        n = len(channels)
        if n == 0:
            return {}

        ch_list = list(channels)
        shapley_values: dict[str, float] = {ch: 0.0 for ch in ch_list}

        for ch in ch_list:
            other_channels = [c for c in ch_list if c != ch]
            for s_size in range(n):
                coeff = (math.factorial(s_size) * math.factorial(n - s_size - 1)) / math.factorial(n)
                for subset in itertools.combinations(other_channels, s_size):
                    s = frozenset(subset)
                    s_with_i = frozenset(subset + (ch,))
                    v_without = coalition_values.get(s, 0.0)
                    v_with = coalition_values.get(s_with_i, 0.0)
                    marginal = v_with - v_without
                    shapley_values[ch] += coeff * marginal

        return shapley_values

    @staticmethod
    def markov_chain(paths: Sequence[ConversionPath]) -> dict[str, float]:
        """Calculates first-order Markov Chain attribution based on the Removal Effect."""
        transitions: dict[tuple[str, str], int] = {}
        channels: set[str] = set()

        for path in paths:
            if not path.touches:
                continue
            prev = "(start)"
            for t in path.touches:
                channels.add(t.channel)
                transitions[(prev, t.channel)] = transitions.get((prev, t.channel), 0) + 1
                prev = t.channel
            final = "(conversion)" if path.converted else "(null)"
            transitions[(prev, final)] = transitions.get((prev, final), 0) + 1

        if not channels:
            return {}

        states = ["(start)"] + sorted(channels) + ["(null)", "(conversion)"]
        state_idx = {s: i for i, s in enumerate(states)}
        num_states = len(states)

        def _build_matrix(excluded_channel: str | None = None) -> np.ndarray:
            t_mat = np.zeros((num_states, num_states), dtype=float)
            for (fr, to), count in transitions.items():
                if excluded_channel and (fr == excluded_channel or to == excluded_channel):
                    continue
                t_mat[state_idx[fr], state_idx[to]] = count

            t_mat[state_idx["(null)"], state_idx["(null)"]] = 1.0
            t_mat[state_idx["(conversion)"], state_idx["(conversion)"]] = 1.0

            for i in range(num_states):
                row_sum = np.sum(t_mat[i])
                if row_sum > 0:
                    t_mat[i] /= row_sum
                else:
                    t_mat[i, state_idx["(null)"]] = 1.0
            return t_mat

        def _conv_prob(t_mat: np.ndarray) -> float:
            m = np.linalg.matrix_power(t_mat, 64)
            return float(m[state_idx["(start)"], state_idx["(conversion)"]])

        baseline_conv = _conv_prob(_build_matrix(None))
        if baseline_conv <= 1e-12:
            return {ch: 0.0 for ch in channels}

        removal_effects: dict[str, float] = {}
        for ch in channels:
            p_removed = _conv_prob(_build_matrix(ch))
            removal_effects[ch] = max(0.0, 1.0 - (p_removed / baseline_conv))

        total_removal = sum(removal_effects.values())
        if total_removal <= 0:
            return {ch: 1.0 / len(channels) for ch in channels}

        return {ch: val / total_removal for ch, val in removal_effects.items()}

    @staticmethod
    def compare_reported_vs_incremental(
        platform_reported: dict[str, float],
        audited_incremental_conversions: float,
    ) -> dict[str, float]:
        """Calculates over-reporting factor: Total Reported / Audited Incremental."""
        total_reported = sum(platform_reported.values())
        over_reporting_factor = (
            total_reported / audited_incremental_conversions
            if audited_incremental_conversions > 0
            else float("inf")
        )
        return {
            "total_reported": total_reported,
            "audited_incremental": audited_incremental_conversions,
            "over_reporting_factor": over_reporting_factor,
        }


__all__ = [
    "Adstock",
    "AttributionEngine",
    "AuctionEnvironment",
    "CohortRetention",
    "ConversionPath",
    "CreativeFatigue",
    "CrossChannelInteraction",
    "DelayDistribution",
    "HillSaturation",
    "Touchpoint",
]

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import numpy as np
from funnelscript.models import AudienceNode


class ConsumerState(Enum):
    COLD = auto()
    AWARE = auto()
    CONSIDERING = auto()
    CART_ABANDONED = auto()
    CONVERTED = auto()
    CHURNED = auto()


@dataclass
class AgentPopulation:
    """Vectorized ensemble of synthetic consumer agents."""

    size: int
    brand_affinity: np.ndarray  # shape: (N,) in [0.0, 1.0]
    price_sensitivity: np.ndarray  # shape: (N,) in [0.0, 1.0]
    fomo_index: np.ndarray  # shape: (N,) in [0.0, 1.0]
    wallet_balance: np.ndarray  # shape: (N,) >= 0
    state: np.ndarray  # shape: (N,) of ConsumerState values

    @classmethod
    def generate_from_audience(cls, audience: AudienceNode, count: int, seed: int = 42) -> AgentPopulation:
        """Samples micro-psychographic vectors from audience baseline parameters."""
        rng = np.random.default_rng(seed)

        # Baseline parameters from audience attributes
        base_affinity = audience.attributes.brand_affinity
        base_price_sens = audience.attributes.price_sensitivity
        base_fomo = audience.attributes.fomo_index

        # Sample psychographics using Beta and Normal distributions with bounds [0, 1]
        affinity = np.clip(rng.normal(loc=base_affinity, scale=0.15, size=count), 0.01, 0.99)
        price_sens = np.clip(rng.normal(loc=base_price_sens, scale=0.15, size=count), 0.01, 0.99)
        fomo = np.clip(rng.normal(loc=base_fomo, scale=0.15, size=count), 0.01, 0.99)

        # Wallet balance: Log-normal distribution with median $150
        wallet = rng.lognormal(mean=5.0, sigma=0.6, size=count)

        # Initial state depends on audience type
        initial_state = ConsumerState.COLD if audience.type == "cold" else ConsumerState.AWARE
        states = np.full(count, initial_state, dtype=object)

        return cls(
            size=count,
            brand_affinity=affinity,
            price_sensitivity=price_sens,
            fomo_index=fomo,
            wallet_balance=wallet,
            state=states,
        )

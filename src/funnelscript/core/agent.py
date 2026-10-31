from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np


class ConsumerState(Enum):
    COLD = "COLD"
    AWARE = "AWARE"
    CONSIDERING = "CONSIDERING"
    CART_ABANDONED = "CART_ABANDONED"
    CONVERTED = "CONVERTED"
    CHURNED = "CHURNED"


@dataclass(frozen=True)
class PsychographicProfile:
    """The micro-psychological state vector governing consumer decision boundaries."""

    brand_affinity: float  # alpha in [0.0, 1.0]: Goodwill and baseline trust toward the merchant
    price_sensitivity: float  # beta in [0.0, 1.0]: Resistance to price, elastic friction
    fomo_index: float  # gamma in [0.0, 1.0]: Vulnerability to urgency, scarcity, and viral proof
    wallet_balance: float  # w >= 0: Available liquid purchasing power for this category

    def __post_init__(self) -> None:
        object.__setattr__(self, "brand_affinity", float(np.clip(self.brand_affinity, 0.0, 1.0)))
        object.__setattr__(self, "price_sensitivity", float(np.clip(self.price_sensitivity, 0.0, 1.0)))
        object.__setattr__(self, "fomo_index", float(np.clip(self.fomo_index, 0.0, 1.0)))
        object.__setattr__(self, "wallet_balance", max(0.0, float(self.wallet_balance)))


@dataclass
class Agent:
    """An individual autonomous consumer entity operating with bounded rationality."""

    id: str
    profile: PsychographicProfile
    state: ConsumerState = ConsumerState.COLD
    ad_exposures: int = 0
    decision_log: list[str] = field(default_factory=list)

    # -------------------------------------------------------------
    # 1. Ad Impression & Click Calculus
    # -------------------------------------------------------------
    def evaluate_ad_exposure(
        self,
        base_ctr: float = 0.03,
        creative_quality: float = 0.75,
        fatigue_decay: float = 0.15,
        rng: np.random.Generator | None = None,
    ) -> tuple[bool, float]:
        """Calculates engagement probability under creative pull and ad fatigue.

        Formula: P(Click) = base_ctr * (1 + fomo * creative_quality) * exp(-fatigue * exposures)
        """
        self.ad_exposures += 1
        gen = rng or np.random.default_rng()

        fatigue_factor = math.exp(-fatigue_decay * (self.ad_exposures - 1))
        p_click = base_ctr * (1.0 + self.profile.fomo_index * creative_quality) * fatigue_factor
        p_click = float(np.clip(p_click, 0.0001, 0.85))

        clicked = bool(gen.random() < p_click)
        if clicked:
            self.state = ConsumerState.AWARE
            self.decision_log.append(f"Clicked ad (P={p_click:.3f}, Exposure #{self.ad_exposures})")
        else:
            self.decision_log.append(f"Ignored ad (P={p_click:.3f}, Exposure #{self.ad_exposures})")

        return clicked, p_click

    # -------------------------------------------------------------
    # 2. Landing Page & Purchase Calculus
    # -------------------------------------------------------------
    def evaluate_purchase(
        self,
        base_cr: float = 0.04,
        product_price: float = 120.0,
        discount_percentage: float = 0.0,
        scarcity_urgency: float = 0.0,
        rng: np.random.Generator | None = None,
    ) -> tuple[bool, float]:
        """Calculates conversion probability against price resistance and brand trust.

        Formula: P(Purchase) = base_cr * (affinity / (price_sens * (1 - discount))) * (1 + fomo * urgency)
        """
        gen = rng or np.random.default_rng()
        effective_price = product_price * (1.0 - (discount_percentage / 100.0))

        # Absolute Wallet Constraint: If the price exceeds available cash, purchase is impossible
        if effective_price > self.profile.wallet_balance:
            self.state = ConsumerState.CHURNED
            self.decision_log.append(
                f"Insolvency bounce: effective price ${effective_price:.2f} > wallet ${self.profile.wallet_balance:.2f}"
            )
            return False, 0.0

        eps = 1e-4
        effective_friction = (self.profile.price_sensitivity * (1.0 - (discount_percentage / 100.0))) + eps
        affinity_term = (self.profile.brand_affinity + eps) / effective_friction
        urgency_multiplier = 1.0 + (self.profile.fomo_index * scarcity_urgency)

        p_purchase = float(np.clip(base_cr * affinity_term * urgency_multiplier, 0.0005, 0.95))
        converted = bool(gen.random() < p_purchase)

        if converted:
            self.state = ConsumerState.CONVERTED
            self.decision_log.append(
                f"Purchased at ${effective_price:.2f} (P={p_purchase:.3f}, Discount={discount_percentage}%)"
            )
        else:
            # Did not purchase: 60% chance to abandon cart, 40% chance to immediately bounce/churn
            if gen.random() < 0.60:
                self.state = ConsumerState.CART_ABANDONED
                self.decision_log.append(f"Abandoned cart (P_purchase={p_purchase:.3f})")
            else:
                self.state = ConsumerState.CHURNED
                self.decision_log.append(f"Bounced from store without cart (P_purchase={p_purchase:.3f})")

        return converted, p_purchase

    # -------------------------------------------------------------
    # 3. Retargeting & Incentive Recovery Calculus
    # -------------------------------------------------------------
    def evaluate_retargeting(
        self,
        base_open_rate: float = 0.30,
        discount_percentage: float = 15.0,
        urgency_boost: float = 0.25,
        rng: np.random.Generator | None = None,
    ) -> tuple[bool, float]:
        """Calculates probability of re-engaging an abandoned cart via retargeting incentive."""
        if self.state != ConsumerState.CART_ABANDONED:
            return False, 0.0

        gen = rng or np.random.default_rng()
        # Email open probability driven by FOMO
        p_open = float(np.clip(base_open_rate * (1.0 + self.profile.fomo_index * 0.5), 0.05, 0.90))
        if gen.random() >= p_open:
            self.decision_log.append(f"Missed retargeting message (P_open={p_open:.3f})")
            return False, 0.0

        # Opened email: Evaluate purchase with discount incentive
        eps = 1e-4
        discount_fraction = discount_percentage / 100.0
        reduced_friction = (self.profile.price_sensitivity * (1.0 - discount_fraction)) + eps
        p_recovery = float(
            np.clip(0.08 * (self.profile.brand_affinity / reduced_friction) * (1.0 + self.profile.fomo_index * urgency_boost), 0.01, 0.90)
        )

        recovered = bool(gen.random() < p_recovery)
        if recovered:
            self.state = ConsumerState.CONVERTED
            self.decision_log.append(
                f"Recovered via retargeting (P_recovery={p_recovery:.3f}, Discount={discount_percentage}%)"
            )
        else:
            self.state = ConsumerState.CHURNED
            self.decision_log.append(f"Ignored retargeting offer (P_recovery={p_recovery:.3f})")

        return recovered, p_recovery

    # -------------------------------------------------------------
    # 4. Archetype Factories for Testing & Profiling
    # -------------------------------------------------------------
    @classmethod
    def create_impulsive_shopper(cls, agent_id: str = "agent_impulsive") -> Agent:
        """High FOMO, low price sensitivity, moderate brand trust."""
        return cls(
            id=agent_id,
            profile=PsychographicProfile(
                brand_affinity=0.50,
                price_sensitivity=0.20,
                fomo_index=0.90,
                wallet_balance=350.0,
            ),
        )

    @classmethod
    def create_loyal_vip(cls, agent_id: str = "agent_loyal_vip") -> Agent:
        """Maximum brand affinity, low price sensitivity, high wallet."""
        return cls(
            id=agent_id,
            profile=PsychographicProfile(
                brand_affinity=0.95,
                price_sensitivity=0.15,
                fomo_index=0.40,
                wallet_balance=1200.0,
            ),
        )

    @classmethod
    def create_skeptic_bargain_hunter(cls, agent_id: str = "agent_bargain_hunter") -> Agent:
        """Low brand trust, extreme price sensitivity, only buys on steep discounts."""
        return cls(
            id=agent_id,
            profile=PsychographicProfile(
                brand_affinity=0.20,
                price_sensitivity=0.90,
                fomo_index=0.60,
                wallet_balance=80.0,
            ),
        )

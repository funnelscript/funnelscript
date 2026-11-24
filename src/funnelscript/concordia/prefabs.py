"""Prefab templates for Concordia Agents in FunnelScript simulations.

Allows rapid instantiation of consumer, business buyer, and sales agents
with standardized components conforming to Google DeepMind Concordia specs.
"""

from __future__ import annotations

from typing import Mapping
from concordia.agents.entity_agent import EntityAgent
from concordia.language_model import language_model, no_language_model

from funnelscript.ledger import FinancialLedger
from funnelscript.concordia.components import (
    FinancialWalletContextComponent,
    PsychographicContextComponent,
    FunnelConsumerActComponent,
)


def make_consumer_entity(
    name: str,
    ledger: FinancialLedger,
    initial_wallet_cents: int = 15_000,
    preferred_product: str = "basic_plan",
    should_refund: bool = False,
    brand_affinity: float = 0.5,
    price_sensitivity: float = 0.5,
    fomo_index: float = 0.3,
    model: language_model.LanguageModel | None = None,
) -> EntityAgent:
    """Build a complete, ready-to-run Concordia EntityAgent for commerce simulation."""
    account_name = f"Customer:{name}"

    wallet_comp = FinancialWalletContextComponent(ledger, account_name)
    psycho_comp = PsychographicContextComponent(
        brand_affinity=brand_affinity,
        price_sensitivity=price_sensitivity,
        fomo_index=fomo_index,
    )
    act_comp = FunnelConsumerActComponent(
        model=model or no_language_model.NoLanguageModel(),
        preferred_product=preferred_product,
        should_refund_after_purchase=should_refund,
    )

    return EntityAgent(
        agent_name=name,
        act_component=act_comp,
        context_components={
            "wallet": wallet_comp,
            "psychographics": psycho_comp,
        },
    )

"""Concordia Entity Components for FunnelScript & Governance Core.

Conforms strictly to Concordia Entity-Component architecture:
- ActionSpecIgnored for context components
- ActingComponent for decision and action generation
"""

from __future__ import annotations

import collections.abc
from typing import Final, Mapping, Sequence, override

from concordia.components.agent import action_spec_ignored
from concordia.document import interactive_document
from concordia.language_model import language_model, no_language_model
from concordia.typing import entity as entity_lib
from concordia.typing import entity_component

from funnelscript.ledger import FinancialLedger, _cents_to_decimal


class FinancialWalletContextComponent(
    action_spec_ignored.ActionSpecIgnored,
    entity_component.ComponentWithLogging,
):
    """Context component exposing live double-entry ledger balance to the agent."""

    def __init__(
        self,
        ledger: FinancialLedger,
        account_name: str,
        pre_act_label: str = "\nFinancial Status & Wallet Balance",
    ) -> None:
        super().__init__(pre_act_label)
        self._ledger = ledger
        self._account_name = account_name

    @override
    def _make_pre_act_value(self) -> str:
        account = self._ledger.get_account(self._account_name)
        if account is not None:
            bal_cents = self._ledger.balance_cents(self._account_name)
            curr = account.currency
            return f"Your current available balance is ${_cents_to_decimal(bal_cents)} {curr}."
        return "No financial account initialized."

    @override
    def get_dynamic_state(self) -> entity_component.ComponentState:
        return {"account_name": self._account_name}


class PsychographicContextComponent(
    action_spec_ignored.ActionSpecIgnored,
    entity_component.ComponentWithLogging,
):
    """Context component modeling consumer psychographics (Affinity, Price Sensitivity, FOMO)."""

    def __init__(
        self,
        brand_affinity: float = 0.5,
        price_sensitivity: float = 0.5,
        fomo_index: float = 0.3,
        pre_act_label: str = "\nConsumer Psychographic Profile",
    ) -> None:
        super().__init__(pre_act_label)
        self.brand_affinity = brand_affinity
        self.price_sensitivity = price_sensitivity
        self.fomo_index = fomo_index

    @override
    def _make_pre_act_value(self) -> str:
        return (
            f"Brand Affinity: {self.brand_affinity:.2f} (0=Hostile, 1=Evangelist)\n"
            f"Price Sensitivity: {self.price_sensitivity:.2f} (0=Inelastic, 1=Budget-Conscious)\n"
            f"FOMO Tendency: {self.fomo_index:.2f} (0=Indifferent, 1=Impulsive)"
        )

    @override
    def get_dynamic_state(self) -> entity_component.ComponentState:
        return {
            "brand_affinity": self.brand_affinity,
            "price_sensitivity": self.price_sensitivity,
            "fomo_index": self.fomo_index,
        }


class FunnelConsumerActComponent(
    entity_component.ActingComponent,
    entity_component.ComponentWithLogging,
):
    """Acting component for consumer agents deciding on commercial transactions."""

    def __init__(
        self,
        model: language_model.LanguageModel | None = None,
        preferred_product: str = "basic_plan",
        should_refund_after_purchase: bool = False,
    ) -> None:
        super().__init__()
        self._model = model or no_language_model.NoLanguageModel()
        self.preferred_product = preferred_product
        self.should_refund_after_purchase = should_refund_after_purchase
        self._has_purchased = False

    @override
    def get_action_attempt(
        self,
        contexts: entity_component.ComponentContextMapping,
        action_spec: entity_lib.ActionSpec,
    ) -> str:
        agent_name = self.get_entity().name

        # If entity already purchased and is configured to test refund
        if self._has_purchased and self.should_refund_after_purchase:
            return f"{agent_name} requests refund for {self.preferred_product}"

        # Otherwise purchase preferred product
        self._has_purchased = True
        return f"{agent_name} buys {self.preferred_product}"

    @override
    def get_state(self) -> entity_component.ComponentState:
        return {
            "preferred_product": self.preferred_product,
            "has_purchased": self._has_purchased,
            "should_refund": self.should_refund_after_purchase,
        }

    @override
    def set_state(self, state: entity_component.ComponentState) -> None:
        if "has_purchased" in state:
            self._has_purchased = bool(state["has_purchased"])

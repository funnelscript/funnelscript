from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, model_validator


class PsychographicAttributes(BaseModel):
    brand_affinity: float = Field(default=0.5, ge=0.0, le=1.0)
    price_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    fomo_index: float = Field(default=0.5, ge=0.0, le=1.0)
    buying_intent_score: float = Field(default=0.5, ge=0.0, le=1.0)


class AudienceNode(BaseModel):
    id: str
    name: str = ""
    type: Literal["cold", "warm", "retargeting"] = "cold"
    estimated_size: int = Field(ge=1)
    attributes: PsychographicAttributes = Field(default_factory=PsychographicAttributes)


class TouchpointNode(BaseModel):
    id: str
    type: Literal["paid_traffic", "conversion_surface", "retargeting_channel"]
    platform: str | None = None
    medium: str | None = None
    base_cpc: float = Field(default=0.50, ge=0.0)
    ad_creative_score: float = Field(default=0.75, ge=0.0, le=1.0)
    base_conversion_rate: float = Field(default=0.03, ge=0.0, le=1.0)
    base_open_rate: float = Field(default=0.25, ge=0.0, le=1.0)
    settlement_delay_days: int = Field(default=3, ge=0, description="Payment processor payout delay in days")


class BudgetsNode(BaseModel):
    total_budget: float = Field(ge=0.0)
    max_cpc_limit: float = Field(default=5.0, ge=0.0)
    initial_cash: float = Field(default=10000.0, ge=0.0, description="Liquid cash available at t=0")
    settlement_delay_days: int = Field(default=3, ge=0, description="Global merchant payout latency")


class EntitiesNode(BaseModel):
    budgets: BudgetsNode
    audiences: list[AudienceNode]
    touchpoints: list[TouchpointNode]


class TrafficTriggerStep(BaseModel):
    step: int
    action: Literal["TriggerTraffic"] = "TriggerTraffic"
    source: str
    via: str
    destination: str


class RetargetingAction(BaseModel):
    action: Literal["ExecuteRetargeting"] = "ExecuteRetargeting"
    channel: str
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_impact: dict[str, float] = Field(default_factory=dict)


class DoNothingAction(BaseModel):
    action: Literal["DoNothing"] = "DoNothing"


BranchAction = Annotated[Union[RetargetingAction, DoNothingAction], Field(discriminator="action")]


class ConditionNode(BaseModel):
    user_action: str
    time_elapsed: str = "2h"


class ConditionalBranchStep(BaseModel):
    step: int
    type: Literal["ConditionalBranch"] = "ConditionalBranch"
    condition: ConditionNode
    true_branch: list[BranchAction] = Field(default_factory=list)
    false_branch: list[BranchAction] = Field(default_factory=list)


LogicStep = Annotated[Union[TrafficTriggerStep, ConditionalBranchStep], Field(discriminator="step")]


class SimulationEngineParams(BaseModel):
    engine_type: str = "Agent-Based_Monte_Carlo"
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {
            "virtual_agents_count": 10000,
            "timeframe_days": 14,
            "randomness_factor_sigma": 0.15,
            "tick_size": "1h",
        }
    )
    historical_data_weight: float = Field(default=0.70, ge=0.0, le=1.0)
    output_metrics_requested: list[str] = Field(
        default_factory=lambda: [
            "ROAS_Distribution",
            "CAC_Probability_Curve",
            "Cash_Ruin_Probability",
            "Inventory_Burn_Rate",
            "Worst_Case_Scenario_Loss",
        ]
    )


class StrategyAST(BaseModel):
    schema_url: str | None = Field(default=None, alias="$schema")
    strategy_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    entities: EntitiesNode
    logic_flow: list[Any] = Field(default_factory=list)
    simulation_engine: SimulationEngineParams = Field(default_factory=SimulationEngineParams)

    @model_validator(mode="after")
    def validate_semantic_integrity(self) -> StrategyAST:
        """Enforces compile-time AST invariants and semantic checks."""
        valid_touchpoint_ids = {tp.id for tp in self.entities.touchpoints}
        valid_audience_ids = {aud.id for aud in self.entities.audiences}

        for step_data in self.logic_flow:
            if isinstance(step_data, dict):
                action = step_data.get("action")
                if action == "TriggerTraffic":
                    src = step_data.get("source")
                    via = step_data.get("via")
                    dest = step_data.get("destination")
                    if src not in valid_audience_ids:
                        raise ValueError(f"CompileError: Undefined audience source '{src}' in logic step")
                    if via not in valid_touchpoint_ids:
                        raise ValueError(f"CompileError: Undefined touchpoint via '{via}' in logic step")
                    if dest not in valid_touchpoint_ids:
                        raise ValueError(f"CompileError: Undefined touchpoint destination '{dest}' in logic step")
                elif step_data.get("type") == "ConditionalBranch":
                    for branch in step_data.get("true_branch", []):
                        ch = branch.get("channel")
                        if ch and ch not in valid_touchpoint_ids:
                            raise ValueError(f"CompileError: Undefined touchpoint channel '{ch}' in branch action")

        # Invariant: Total budget and initial cash must be positive
        if self.entities.budgets.total_budget <= 0:
            raise ValueError("CompileError: Invariant violation: total_budget must be strictly positive")

        return self

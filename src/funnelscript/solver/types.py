from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class RegisteredAction(str, Enum):
    """Machine-actionable next actions originating from the registered capability catalog."""
    REBALANCE_BUDGET = "REBALANCE_BUDGET"
    COLLECT_EMPIRICAL_SPEND = "COLLECT_EMPIRICAL_SPEND"
    RELAX_CHANNEL_CONSTRAINTS = "RELAX_CHANNEL_CONSTRAINTS"
    EXPAND_BUDGET_ENVELOPE = "EXPAND_BUDGET_ENVELOPE"
    ADJUST_CAC_CEILING = "ADJUST_CAC_CEILING"


class SpendSupportClassification(str, Enum):
    """Empirical spend support classifications to avoid prior-dominated claims."""
    EMPIRICALLY_SUPPORTED = "EMPIRICALLY_SUPPORTED"
    INTERPOLATED = "INTERPOLATED"
    EXTRAPOLATED_PRIOR = "EXTRAPOLATED_PRIOR"


class EmpiricalSupportMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_observed_spend: float = Field(ge=0.0)
    max_observed_spend: float = Field(ge=0.0)
    observations_count: int = Field(ge=0)
    classification: SpendSupportClassification = SpendSupportClassification.EMPIRICALLY_SUPPORTED
    extrapolation_ratio: float = Field(default=1.0, ge=0.0)


class ChannelModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_id: str
    v_max: float = Field(gt=0.0, description="Saturation ceiling in revenue")
    k_sat: float = Field(gt=0.0, description="Half-saturation spend constant")
    alpha: float = Field(gt=0.0, le=1.0, description="Hill elasticity (concave for <= 1.0)")
    min_spend: float = Field(default=0.0, ge=0.0)
    max_spend: float = Field(gt=0.0)
    empirical_support: EmpiricalSupportMetadata


class ModelLineage(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_fingerprint: str = Field(description="SHA-256 hash of historical observations")
    currency: str = Field(default="USD", description="Currency code (e.g. USD, EUR)")
    population_hash: str = Field(description="SHA-256 hash of target audience definition")


class OptimizationGoal(str, Enum):
    MAXIMIZE_PROFIT = "maximize_profit"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    MINIMIZE_CAC = "minimize_cac"


class SolverInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_budget: float = Field(description="Total capital to allocate across channels")
    currency: str = Field(default="USD")
    channels: List[ChannelModel] = Field(min_length=1)
    lineage: ModelLineage
    cac_ceiling: Optional[float] = Field(default=None, gt=0.0)
    avg_ticket_value: float = Field(default=100.0, gt=0.0)
    goal: OptimizationGoal = OptimizationGoal.MAXIMIZE_PROFIT


class SolverResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: str
    optimal_weights: np.ndarray
    optimal_allocations: Dict[str, float]
    expected_revenue: float
    expected_net_profit: float
    expected_blended_cac: float
    shadow_prices: Dict[str, float]
    channel_diagnostics: Dict[str, EmpiricalSupportMetadata]
    artifact_checksum: str
    next_actions: List[RegisteredAction]

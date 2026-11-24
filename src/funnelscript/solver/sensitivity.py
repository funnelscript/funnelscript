from __future__ import annotations

from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass(frozen=True)
class FunnelBottleneckSensitivity:
    stage_id: str
    current_conversion_rate: float
    marginal_revenue_lift_per_percent: float
    elasticity_rank: int


def analyze_funnel_bottlenecks(
    stage_conversions: Dict[str, float],
    total_pipeline_revenue: float,
) -> List[FunnelBottleneckSensitivity]:
    """
    Computes sensitivity / shadow elasticity for each funnel stage.
    Identifies the exact conversion surfaces where a 1% uplift in conversion rate
    yields the highest marginal dollar impact across the funnel.
    """
    sensitivities: List[Tuple[str, float, float]] = []

    for stage, cr in stage_conversions.items():
        if cr <= 0.0:
            continue
        # Relative elasticity: d(Rev)/d(CR) ≈ Total Rev / CR
        marginal_lift = total_pipeline_revenue * 0.01 / cr
        sensitivities.append((stage, cr, marginal_lift))

    # Sort descending by marginal revenue lift
    sensitivities.sort(key=lambda x: x[2], reverse=True)

    results: List[FunnelBottleneckSensitivity] = []
    for rank, (stage, cr, lift) in enumerate(sensitivities, start=1):
        results.append(
            FunnelBottleneckSensitivity(
                stage_id=stage,
                current_conversion_rate=cr,
                marginal_revenue_lift_per_percent=lift,
                elasticity_rank=rank,
            )
        )

    return results

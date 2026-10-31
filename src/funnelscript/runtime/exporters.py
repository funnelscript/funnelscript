"""FunnelScript Runtime Exporters.

Provides deterministic serializations of Monte Carlo simulation runs to:
- CSV (summary trial distribution & daily time-series trajectories)
- JSON (complete report with full distributions and VaR metrics)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from funnelscript.runtime.telemetry import SimulationReport


def export_trials_to_csv(report: SimulationReport, output_path: str | Path) -> None:
    """Exports individual Monte Carlo trial outcomes to a CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "trial_id",
        "spend",
        "impressions",
        "clicks",
        "conversions",
        "revenue",
        "roas",
        "cac",
        "cannibalized_conversions",
        "insolvency_triggered",
        "final_liquid_cash",
        "min_cash_observed",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in report.raw_trials:
            writer.writerow(
                {
                    "trial_id": t.trial_id,
                    "spend": round(t.spend, 2),
                    "impressions": t.impressions,
                    "clicks": t.clicks,
                    "conversions": t.conversions,
                    "revenue": round(t.revenue, 2),
                    "roas": round(t.roas, 4),
                    "cac": round(t.cac, 2) if t.cac < float("inf") else -1.0,
                    "cannibalized_conversions": t.cannibalized_conversions,
                    "insolvency_triggered": t.insolvency_triggered,
                    "final_liquid_cash": round(t.final_liquid_cash, 2),
                    "min_cash_observed": round(t.min_cash_observed, 2),
                }
            )


def export_trajectories_to_csv(report: SimulationReport, output_path: str | Path, trial_id: int = 0) -> None:
    """Exports daily timeline snapshots of a selected trial to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not report.raw_trials or trial_id >= len(report.raw_trials):
        raise ValueError(f"Trial {trial_id} not found in report.")

    trial = report.raw_trials[trial_id]
    fieldnames = [
        "day",
        "spend",
        "clicks",
        "conversions",
        "gross_revenue",
        "settled_revenue",
        "liquid_cash",
        "pending_receivables",
        "state_cold",
        "state_aware",
        "state_cart_abandoned",
        "state_converted",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in trial.daily_snapshots:
            writer.writerow(
                {
                    "day": s.day,
                    "spend": round(s.spend, 2),
                    "clicks": s.clicks,
                    "conversions": s.conversions,
                    "gross_revenue": round(s.gross_revenue, 2),
                    "settled_revenue": round(s.settled_revenue, 2),
                    "liquid_cash": round(s.liquid_cash, 2),
                    "pending_receivables": round(s.pending_receivables, 2),
                    "state_cold": s.state_distribution.get("COLD", 0),
                    "state_aware": s.state_distribution.get("AWARE", 0),
                    "state_cart_abandoned": s.state_distribution.get("CART_ABANDONED", 0),
                    "state_converted": s.state_distribution.get("CONVERTED", 0),
                }
            )


def export_report_to_json(report: SimulationReport, output_path: str | Path | None = None) -> str:
    """Serializes the complete SimulationReport into JSON format."""

    def dist_dict(d: Any) -> dict[str, float]:
        return {
            "mean": round(d.mean, 4),
            "std": round(d.std, 4),
            "median": round(d.median, 4),
            "p10": round(d.p10, 4),
            "p25": round(d.p25, 4),
            "p75": round(d.p75, 4),
            "p90": round(d.p90, 4),
        }

    data = {
        "strategy_name": report.strategy_name,
        "trials_count": report.trials_count,
        "agents_per_trial": report.agents_per_trial,
        "timeframe_days": report.timeframe_days,
        "metrics": {
            "roas": dist_dict(report.roas),
            "cac": dist_dict(report.cac),
            "spend": dist_dict(report.spend),
            "revenue": dist_dict(report.revenue),
            "profit": dist_dict(report.profit),
        },
        "risk_telemetry": {
            "probability_of_profit": round(report.probability_of_profit, 4),
            "cash_ruin_probability": round(report.cash_ruin_probability, 4),
            "worst_case_drawdown": round(report.worst_case_drawdown, 2),
            "var_95": round(report.var_95, 2),
            "cvar_95": round(report.cvar_95, 2),
            "cannibalization_rate": round(report.cannibalization_rate, 4),
        },
    }

    serialized = json.dumps(data, indent=2)
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(serialized, encoding="utf-8")

    return serialized

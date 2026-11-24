from __future__ import annotations

from funnelscript.solver.types import RegisteredAction, SolverInput
from funnelscript.solver.errors import PreflightAdmissionError
from funnelscript.solver.lineage import validate_lineage
from funnelscript.solver.simplex import normalize_bounds_to_simplex


class PreflightAdmissionGate:
    """
    Canonical validation implementation for solver admission.
    Enforces all domain invariants before problem compilation or enqueuing.
    """

    def validate(self, input_data: SolverInput) -> SolverInput:
        # 1. Budget Positivity
        if input_data.total_budget <= 0.0:
            raise PreflightAdmissionError(
                code="ERR_ADMISSION_INVALID_BUDGET",
                message=f"Total budget must be strictly positive (> 0), got {input_data.total_budget}",
                remediation="Specify a non-negative, non-zero total budget allocation.",
                remediation_action=RegisteredAction.EXPAND_BUDGET_ENVELOPE,
            )

        # 2. Channels existence
        if not input_data.channels:
            raise PreflightAdmissionError(
                code="ERR_ADMISSION_NO_CHANNELS",
                message="At least one marketing channel model is required.",
                remediation="Configure at least one channel model in solver input.",
                remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
            )

        # 3. Individual channel sanity
        for ch in input_data.channels:
            if ch.min_spend < 0.0:
                raise PreflightAdmissionError(
                    code="ERR_ADMISSION_NEGATIVE_MIN_SPEND",
                    message=f"Channel '{ch.channel_id}' min_spend cannot be negative ({ch.min_spend})",
                    remediation="Set min_spend >= 0.0 for all channels.",
                    remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
                )
            if ch.max_spend <= 0.0:
                raise PreflightAdmissionError(
                    code="ERR_ADMISSION_ZERO_MAX_SPEND",
                    message=f"Channel '{ch.channel_id}' max_spend must be strictly positive",
                    remediation="Set max_spend > 0.0 for all channels.",
                    remediation_action=RegisteredAction.EXPAND_BUDGET_ENVELOPE,
                )
            if ch.min_spend > ch.max_spend:
                raise PreflightAdmissionError(
                    code="ERR_ADMISSION_INVERTED_SPEND",
                    message=f"Channel '{ch.channel_id}' min_spend ({ch.min_spend}) > max_spend ({ch.max_spend})",
                    remediation="Ensure min_spend <= max_spend for each channel.",
                    remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
                )

        # 4. Simplex Feasibility Check
        normalize_bounds_to_simplex(input_data.channels, input_data.total_budget)

        # 5. Lineage Check (fails closed)
        validate_lineage(input_data.lineage, input_data.lineage)

        # 6. CAC Ceiling Sanity
        if input_data.cac_ceiling is not None and input_data.cac_ceiling <= 0.0:
            raise PreflightAdmissionError(
                code="ERR_ADMISSION_INVALID_CAC_CEILING",
                message=f"CAC ceiling must be strictly positive, got {input_data.cac_ceiling}",
                remediation="Specify a positive CAC ceiling or omit the constraint.",
                remediation_action=RegisteredAction.ADJUST_CAC_CEILING,
            )

        return input_data

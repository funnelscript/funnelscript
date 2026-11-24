from __future__ import annotations

from funnelscript.solver.types import ModelLineage, RegisteredAction
from funnelscript.solver.errors import LineageMismatchError


def validate_lineage(expected: ModelLineage, actual: ModelLineage) -> bool:
    """
    Validates model lineage and fails closed.
    Entity ID overlap does not constitute a valid modeling cohort;
    dataset fingerprint, currency, and population hashes must strictly match.
    """
    if expected.dataset_fingerprint != actual.dataset_fingerprint:
        raise LineageMismatchError(
            code="ERR_LINEAGE_FINGERPRINT_MISMATCH",
            message=(
                f"Dataset fingerprint mismatch: expected '{expected.dataset_fingerprint}', "
                f"got '{actual.dataset_fingerprint}'"
            ),
            remediation="Regenerate channel model parameters against the current historical dataset fingerprint.",
            remediation_action=RegisteredAction.COLLECT_EMPIRICAL_SPEND,
        )

    if expected.currency.upper() != actual.currency.upper():
        raise LineageMismatchError(
            code="ERR_LINEAGE_CURRENCY_MISMATCH",
            message=f"Currency mismatch: expected '{expected.currency}', got '{actual.currency}'",
            remediation="Normalize all channel financial curves to the target base currency before solving.",
            remediation_action=RegisteredAction.RELAX_CHANNEL_CONSTRAINTS,
        )

    if expected.population_hash != actual.population_hash:
        raise LineageMismatchError(
            code="ERR_LINEAGE_POPULATION_MISMATCH",
            message=(
                f"Population hash mismatch: expected '{expected.population_hash}', "
                f"got '{actual.population_hash}'"
            ),
            remediation="Re-evaluate audience psychographics and recompute audience population hash.",
            remediation_action=RegisteredAction.COLLECT_EMPIRICAL_SPEND,
        )

    return True

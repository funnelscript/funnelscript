"""Opt-in domain-owned marketing reference accounting.

No automatic compiler or World runtime policy.
"""

from .ledger import LedgerEntry, LedgerSnapshot, MarketingLedger
from .metrics import RiskReferenceMetrics, TrialReferenceMetrics, evaluate_risk, evaluate_trial
from .provenance import (
    DeclaredSalePolicy, EventProvenance, ProvenancedSale, ProvenancedTrial,
    recognize_sales, post_provenanced_trial,
)

__all__ = [
    "LedgerEntry", "LedgerSnapshot", "MarketingLedger",
    "TrialReferenceMetrics", "RiskReferenceMetrics", "evaluate_trial", "evaluate_risk",
    "DeclaredSalePolicy", "EventProvenance", "ProvenancedSale", "ProvenancedTrial",
    "recognize_sales", "post_provenanced_trial",
]

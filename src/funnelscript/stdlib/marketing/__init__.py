"""Opt-in domain-owned marketing reference accounting.

No automatic compiler or World runtime policy.
"""

from .ledger import LedgerEntry, LedgerSnapshot, MarketingLedger
from .metrics import RiskReferenceMetrics, TrialReferenceMetrics, evaluate_risk, evaluate_trial
from .provenance import (
    DeclaredSalePolicy, DeclaredFinancialAction, EventProvenance, ProvenancedSale, ProvenancedTrial,
    recognize_sales, post_provenanced_trial, post_authorized_trial,
)

from .audit import (AUDIT_SCHEMA, export_audit, restore_audit, replay_audit,
                    write_audit_checkpoint, read_audit_checkpoint)

from .commit import (RECEIPT_SCHEMA, FinancialCommitReceipt, CommitOutcomeUncertain,
                     commit_financial_checkpoint, recover_financial_checkpoint,
                     verify_financial_receipt)

__all__ = [
    "LedgerEntry", "LedgerSnapshot", "MarketingLedger",
    "TrialReferenceMetrics", "RiskReferenceMetrics", "evaluate_trial", "evaluate_risk",
    "DeclaredSalePolicy", "DeclaredFinancialAction", "EventProvenance", "ProvenancedSale", "ProvenancedTrial",
    "recognize_sales", "post_provenanced_trial", "post_authorized_trial",
    "AUDIT_SCHEMA", "export_audit", "restore_audit", "replay_audit",
    "write_audit_checkpoint", "read_audit_checkpoint",
    "RECEIPT_SCHEMA", "FinancialCommitReceipt", "CommitOutcomeUncertain",
    "commit_financial_checkpoint", "recover_financial_checkpoint", "verify_financial_receipt",
]

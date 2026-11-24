"""Opt-in domain-owned marketing reference accounting and marketing science standard library.

Includes:
- Double-entry financial ledgers, audit trails, and commit recovery receipts
- Marketing science kernels (Hill saturation, Adstock decay, Delay queues, Retention)
- Real-world friction (rolling reserves, refunds, chargebacks, Net-30 credit)
- Multi-Touch Attribution (MTA), Shapley & Markov removal effects
- Ingestion adapters for ad platform CSVs (Meta/Google) and payment settlement logs
- Empirical parameter calibration engine & .fnls World code generation
- Empirical 50/50 temporal backtesting and spreadsheet benchmark engine
"""

from .audit import (
    AUDIT_SCHEMA,
    compute_audit_chain,
    export_audit,
    read_audit_checkpoint,
    replay_audit,
    restore_audit,
    verify_audit_chain,
    write_audit_checkpoint,
)
from .backtest import (
    BacktestReport,
    EmpiricalBacktester,
    ForecastMetricComparison,
)
from .calibration import (
    CalibratedCampaignModel,
    CampaignCalibrator,
    ChannelCalibrationResult,
)
from .commit import (
    RECEIPT_SCHEMA,
    CommitOutcomeUncertain,
    FinancialCommitReceipt,
    commit_financial_checkpoint,
    recover_financial_checkpoint,
    verify_financial_receipt,
)
from .ingestion import (
    DailyCampaignMetric,
    IngestionError,
    MarketingDataIngestor,
    PaymentSettlementRecord,
)
from .kernels import (
    Adstock,
    AttributionEngine,
    AuctionEnvironment,
    CohortRetention,
    ConversionPath,
    CreativeFatigue,
    CrossChannelInteraction,
    DelayDistribution,
    HillSaturation,
    Touchpoint,
)
from .ledger import (
    LedgerEntry,
    LedgerSnapshot,
    MarketingLedger,
    allocate_remainder,
)
from .metrics import (
    RiskReferenceMetrics,
    TrialReferenceMetrics,
    UndefinedMetric,
    evaluate_risk,
    evaluate_trial,
)
from .provenance import (
    DeclaredFinancialAction,
    DeclaredSalePolicy,
    EventProvenance,
    ProvenancedSale,
    ProvenancedTrial,
    post_authorized_trial,
    post_provenanced_trial,
    recognize_sales,
)

__all__ = [
    "AUDIT_SCHEMA",
    "RECEIPT_SCHEMA",
    "Adstock",
    "AttributionEngine",
    "AuctionEnvironment",
    "BacktestReport",
    "CalibratedCampaignModel",
    "CampaignCalibrator",
    "ChannelCalibrationResult",
    "CohortRetention",
    "CommitOutcomeUncertain",
    "ConversionPath",
    "CreativeFatigue",
    "CrossChannelInteraction",
    "DailyCampaignMetric",
    "DeclaredFinancialAction",
    "DeclaredSalePolicy",
    "DelayDistribution",
    "EmpiricalBacktester",
    "EventProvenance",
    "FinancialCommitReceipt",
    "ForecastMetricComparison",
    "HillSaturation",
    "IngestionError",
    "LedgerEntry",
    "LedgerSnapshot",
    "MarketingDataIngestor",
    "MarketingLedger",
    "PaymentSettlementRecord",
    "ProvenancedSale",
    "ProvenancedTrial",
    "RiskReferenceMetrics",
    "Touchpoint",
    "TrialReferenceMetrics",
    "UndefinedMetric",
    "allocate_remainder",
    "commit_financial_checkpoint",
    "compute_audit_chain",
    "evaluate_risk",
    "evaluate_trial",
    "export_audit",
    "post_authorized_trial",
    "post_provenanced_trial",
    "read_audit_checkpoint",
    "recognize_sales",
    "recover_financial_checkpoint",
    "replay_audit",
    "restore_audit",
    "verify_audit_chain",
    "verify_financial_receipt",
    "write_audit_checkpoint",
]

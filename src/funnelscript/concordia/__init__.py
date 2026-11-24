"""FunnelScript - Google DeepMind Concordia Integration Subsystem.

Combines Concordia's Generative Agent-Based Modeling (GABM) with FunnelScript's
exact-arithmetic double-entry financial ledger and operational governance circuit breakers.
"""

from funnelscript.concordia.circuit_breaker import (
    CircuitBreakerStatus,
    GovernanceCircuitBreaker,
)
from funnelscript.concordia.components import (
    FinancialWalletContextComponent,
    FunnelConsumerActComponent,
    PsychographicContextComponent,
)
from funnelscript.concordia.game_master import FunnelScriptConcordiaGameMaster
from funnelscript.concordia.prefabs import make_consumer_entity
from funnelscript.concordia.simulation import (
    ConcordiaFunnelSimulation,
    ConcordiaSimulationResult,
)

__all__ = [
    "CircuitBreakerStatus",
    "GovernanceCircuitBreaker",
    "FinancialWalletContextComponent",
    "PsychographicContextComponent",
    "FunnelConsumerActComponent",
    "FunnelScriptConcordiaGameMaster",
    "make_consumer_entity",
    "ConcordiaFunnelSimulation",
    "ConcordiaSimulationResult",
]

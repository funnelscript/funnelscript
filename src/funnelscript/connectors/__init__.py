"""FunnelScript Ingestable connectors, telemetry ingestion, and declarative object mapper."""

from .base import (
    BasePollingConnector,
    BaseWebhookAdapter,
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimitExceededError,
    SecretMasker,
    TokenBucketRateLimiter,
    execute_with_retry,
)
from .ga4 import GA4Connector
from .google_ads import GoogleAdsConnector
from .meta_ads import MetaAdsConnector
from .models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
    IngestionBatch,
    RestatementDelta,
    compute_payload_sha256,
)
from .object_mapper import (
    DLQRecord,
    HydratedEntity,
    IngestionResult,
    MappingConfig,
    ObjectMapper,
    ProvenanceMetadata,
)
from .staging import SQLiteStagingBuffer
from .synthetic_bridge import DiscreteAgentEvent, SyntheticEventBridge
from .webhook_server import (
    WebhookHTTPRequestHandler,
    WebhookReceiver,
    create_webhook_server,
)
from .webhooks import ShopifyWebhookAdapter, StripeWebhookAdapter

__all__ = [
    # Base resilience & contracts
    "BasePollingConnector",
    "BaseWebhookAdapter",
    # Models
    "CanonicalAdSpendRecord",
    "CanonicalConversionEvent",
    "CanonicalSettlementEvent",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    # Object Mapper
    "DLQRecord",
    "DiscreteAgentEvent",
    "GA4Connector",
    "GoogleAdsConnector",
    "HydratedEntity",
    "IngestionBatch",
    "IngestionResult",
    "MappingConfig",
    # Connectors
    "MetaAdsConnector",
    "ObjectMapper",
    "ProvenanceMetadata",
    "RateLimitExceededError",
    "RestatementDelta",
    # Staging & Synthetic Bridge
    "SQLiteStagingBuffer",
    "SecretMasker",
    "ShopifyWebhookAdapter",
    # Webhooks & Server
    "StripeWebhookAdapter",
    "SyntheticEventBridge",
    "TokenBucketRateLimiter",
    "WebhookHTTPRequestHandler",
    "WebhookReceiver",
    "compute_payload_sha256",
    "create_webhook_server",
    "execute_with_retry",
]

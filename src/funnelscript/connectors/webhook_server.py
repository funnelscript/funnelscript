"""FunnelScript Real-Time Webhook Ingestion Server.

Provides:
- HTTP API endpoints for receiving Stripe and Shopify webhooks.
- Cryptographic signature validation with constant-time comparison and replay defense.
- Direct write-to-staging buffer in SQLite WAL mode before returning HTTP 200 OK.
- Dead-Letter Queue (DLQ) routing for corrupted or malformed payloads.
- Standalone multi-threaded HTTP server for `funnelscript ingest serve`.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from funnelscript.connectors.staging import SQLiteStagingBuffer
from funnelscript.connectors.webhooks import ShopifyWebhookAdapter, StripeWebhookAdapter

logger = logging.getLogger("funnelscript.webhooks")


class WebhookReceiver:
    """Core request processing engine for incoming webhooks."""

    def __init__(
        self,
        staging_buffer: SQLiteStagingBuffer,
        stripe_secret: str = "",
        shopify_secret: str = "",
    ) -> None:
        self.staging = staging_buffer
        self.stripe_secret = stripe_secret
        self.shopify_secret = shopify_secret
        self.stripe_adapter = StripeWebhookAdapter()
        self.shopify_adapter = ShopifyWebhookAdapter()

    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body_bytes: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Handles a single HTTP request and returns (status_code, response_json)."""
        clean_path = path.split("?")[0].rstrip("/")

        if method == "GET":
            if clean_path in ("/health", "/api/health"):
                counts = self.staging.count_staging()
                dlq_cnt = self.staging.count_dlq()
                return 200, {
                    "status": "ok",
                    "staging": counts,
                    "dlq_pending": dlq_cnt,
                }
            elif clean_path in ("/metrics", "/api/metrics"):
                counts = self.staging.count_staging()
                dlq_cnt = self.staging.count_dlq()
                return 200, {
                    "pending_records": counts["pending"],
                    "processed_records": counts["processed"],
                    "dlq_count": dlq_cnt,
                }
            return 404, {"error": "Not Found"}

        if method != "POST":
            return 405, {"error": "Method Not Allowed"}

        # Route webhooks
        if clean_path == "/webhooks/stripe":
            return self._handle_stripe(headers, body_bytes)
        elif clean_path == "/webhooks/shopify":
            return self._handle_shopify(headers, body_bytes)
        elif clean_path == "/webhooks/generic":
            return self._handle_generic(headers, body_bytes)
        else:
            return 404, {"error": f"Webhook endpoint '{clean_path}' not found"}

    def _handle_stripe(self, headers: dict[str, str], body_bytes: bytes) -> tuple[int, dict[str, Any]]:
        # Verify HMAC signature
        if self.stripe_secret:
            valid = self.stripe_adapter.verify_signature(body_bytes, headers, secret=self.stripe_secret)
            if not valid:
                return 401, {"error": "Invalid or expired Stripe-Signature"}

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            dlq_id = self.staging.route_to_dlq(
                platform="stripe",
                raw_payload=body_bytes,
                error_code="MALFORMED_JSON",
                error_message=str(exc),
            )
            return 400, {"error": "Malformed JSON payload", "dlq_id": dlq_id}

        try:
            records = self.stripe_adapter.parse_webhook(payload, headers)
            enqueued, duplicates = self.staging.enqueue_batch(records)
            return 200, {
                "status": "accepted",
                "platform": "stripe",
                "enqueued": enqueued,
                "duplicates": duplicates,
            }
        except (ValueError, TypeError, KeyError) as exc:
            dlq_id = self.staging.route_to_dlq(
                platform="stripe",
                raw_payload=payload,
                error_code="PARSE_FAILED",
                error_message=str(exc),
            )
            return 400, {"error": f"Failed to parse Stripe event: {exc}", "dlq_id": dlq_id}

    def _handle_shopify(self, headers: dict[str, str], body_bytes: bytes) -> tuple[int, dict[str, Any]]:
        if self.shopify_secret:
            valid = self.shopify_adapter.verify_signature(body_bytes, headers, secret=self.shopify_secret)
            if not valid:
                return 401, {"error": "Invalid X-Shopify-Hmac-Sha256 signature"}

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            dlq_id = self.staging.route_to_dlq(
                platform="shopify",
                raw_payload=body_bytes,
                error_code="MALFORMED_JSON",
                error_message=str(exc),
            )
            return 400, {"error": "Malformed JSON payload", "dlq_id": dlq_id}

        try:
            records = self.shopify_adapter.parse_webhook(payload, headers)
            enqueued, duplicates = self.staging.enqueue_batch(records)
            return 200, {
                "status": "accepted",
                "platform": "shopify",
                "enqueued": enqueued,
                "duplicates": duplicates,
            }
        except (ValueError, TypeError, KeyError) as exc:
            dlq_id = self.staging.route_to_dlq(
                platform="shopify",
                raw_payload=payload,
                error_code="PARSE_FAILED",
                error_message=str(exc),
            )
            return 400, {"error": f"Failed to parse Shopify event: {exc}", "dlq_id": dlq_id}

    def _handle_generic(self, headers: dict[str, str], body_bytes: bytes) -> tuple[int, dict[str, Any]]:
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
            dlq_id = self.staging.route_to_dlq(
                platform="generic",
                raw_payload=payload,
                error_code="GENERIC_NOT_CONFIGURED",
                error_message="Generic webhook received without explicit mapping",
            )
            return 202, {"status": "routed_to_dlq", "dlq_id": dlq_id}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return 400, {"error": f"Invalid generic payload: {exc}"}


class WebhookHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler routing requests to WebhookReceiver."""

    receiver: WebhookReceiver | None = None

    def _send_json_response(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.receiver:
            self._send_json_response(500, {"error": "Receiver not initialized"})
            return
        headers = {k.lower(): v for k, v in self.headers.items()}
        status, data = self.receiver.handle_request("GET", self.path, headers, b"")
        self._send_json_response(status, data)

    def do_POST(self) -> None:
        if not self.receiver:
            self._send_json_response(500, {"error": "Receiver not initialized"})
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        headers = {k.lower(): v for k, v in self.headers.items()}
        status, data = self.receiver.handle_request("POST", self.path, headers, body_bytes)
        self._send_json_response(status, data)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard request logging in test runs
        pass


def create_webhook_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    staging_buffer: SQLiteStagingBuffer | None = None,
    stripe_secret: str = "",
    shopify_secret: str = "",
) -> tuple[HTTPServer, WebhookReceiver]:
    """Factory creating an HTTPServer instance wired with WebhookReceiver."""
    buffer = staging_buffer or SQLiteStagingBuffer()
    receiver = WebhookReceiver(buffer, stripe_secret=stripe_secret, shopify_secret=shopify_secret)

    class CustomHandler(WebhookHTTPRequestHandler):
        pass

    CustomHandler.receiver = receiver
    server = HTTPServer((host, port), CustomHandler)
    return server, receiver

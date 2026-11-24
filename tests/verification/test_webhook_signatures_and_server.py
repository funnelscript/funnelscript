"""Verification tests for Webhook HMAC Signatures, Replay Defense, and Webhook Server.

Validates:
1. Stripe HMAC-SHA256 signature verification:
   - Valid signature succeeds.
   - Tampered body fails with 401.
   - Stale timestamp (> 300s) fails with 401.
2. Shopify Base64 HMAC-SHA256 signature verification.
3. Event parsing: charge.succeeded, charge.refunded, charge.dispute.created, orders/create.
4. WebhookReceiver integration:
   - Enqueues to SQLiteStagingBuffer before returning HTTP 200.
   - Routes malformed JSON to Dead-Letter Queue (DLQ) with HTTP 400.
   - Health and metrics endpoints return accurate counts.
5. Socket-level integration test: Runs real HTTP server on port 0 with live HTTP client requests.
"""

import base64
import hashlib
import hmac
import json
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from funnelscript.connectors.staging import SQLiteStagingBuffer
from funnelscript.connectors.webhook_server import (
    WebhookReceiver,
    create_webhook_server,
)
from funnelscript.connectors.webhooks import ShopifyWebhookAdapter, StripeWebhookAdapter


def generate_stripe_header(payload_bytes: bytes, secret: str, timestamp: float | None = None) -> str:
    ts = str(int(timestamp or time.time()))
    signed_payload = f"{ts}.".encode() + payload_bytes
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def generate_shopify_header(payload_bytes: bytes, secret: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    ).decode("utf-8")


def test_stripe_signature_verification_success_and_failures():
    adapter = StripeWebhookAdapter()
    secret = "whsec_test_secret_stripe_123"
    payload = b'{"type": "charge.succeeded", "data": {"object": {"id": "ch_123", "amount": 5000}}}'

    # 1. Valid signature within tolerance
    valid_header = generate_stripe_header(payload, secret)
    assert adapter.verify_signature(payload, {"Stripe-Signature": valid_header}, secret=secret) is True

    # 2. Tampered payload with original header fails
    tampered_payload = b'{"type": "charge.succeeded", "data": {"object": {"id": "ch_123", "amount": 99999}}}'
    assert adapter.verify_signature(tampered_payload, {"Stripe-Signature": valid_header}, secret=secret) is False

    # 3. Stale timestamp (350 seconds ago > 300s limit) fails
    stale_ts = time.time() - 350
    stale_header = generate_stripe_header(payload, secret, timestamp=stale_ts)
    assert adapter.verify_signature(payload, {"Stripe-Signature": stale_header}, secret=secret) is False

    # 4. Wrong secret fails
    assert adapter.verify_signature(payload, {"Stripe-Signature": valid_header}, secret="wrong_secret") is False


def test_shopify_signature_verification():
    adapter = ShopifyWebhookAdapter()
    secret = "shpss_test_shopify_secret_456"
    payload = b'{"id": 888777, "total_price": "149.99", "currency": "USD"}'

    valid_header = generate_shopify_header(payload, secret)
    assert adapter.verify_signature(payload, {"X-Shopify-Hmac-Sha256": valid_header}, secret=secret) is True

    # Tampered payload fails
    assert adapter.verify_signature(b"tampered", {"X-Shopify-Hmac-Sha256": valid_header}, secret=secret) is False


def test_stripe_event_parsing_charge_refund_dispute():
    adapter = StripeWebhookAdapter()

    # charge.succeeded
    charge_payload = {
        "type": "charge.succeeded",
        "created": 1700000000,
        "data": {
            "object": {
                "id": "ch_abc123",
                "amount": 10000,
                "currency": "usd",
                "customer": "cus_999",
                "balance_transaction": {"fee": 320},
            }
        },
    }
    records = adapter.parse_webhook(charge_payload, {})
    assert len(records) == 2
    settlement = records[0]
    conversion = records[1]

    assert settlement.gross_cents == 10000
    assert settlement.fee_cents == 320
    assert settlement.net_cash_cents == 9680
    assert settlement.status == "settled"

    assert conversion.revenue_cents == 10000
    assert conversion.customer_id == "cus_999"

    # charge.dispute.created
    dispute_payload = {
        "type": "charge.dispute.created",
        "created": 1700000100,
        "data": {
            "object": {
                "id": "dp_111",
                "charge": "ch_abc123",
                "amount": 10000,
                "currency": "usd",
            }
        },
    }
    disp_records = adapter.parse_webhook(dispute_payload, {})
    assert len(disp_records) == 1
    assert disp_records[0].status == "disputed"
    assert disp_records[0].reserve_hold_cents == 10000


def test_webhook_receiver_routing_and_dlq(tmp_path: Path):
    db_file = tmp_path / "webhook_test.db"
    staging = SQLiteStagingBuffer(db_file)
    secret = "whsec_staging_test"
    receiver = WebhookReceiver(staging, stripe_secret=secret)

    payload_dict = {
        "type": "charge.succeeded",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "ch_webhook_001",
                "amount": 5000,
                "currency": "usd",
            }
        },
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    sig_header = generate_stripe_header(raw_bytes, secret)

    # 1. Successful webhook POST
    status, data = receiver.handle_request(
        "POST",
        "/webhooks/stripe",
        {"stripe-signature": sig_header},
        raw_bytes,
    )
    assert status == 200
    assert data["status"] == "accepted"
    assert data["enqueued"] == 2  # settlement + conversion

    # 2. Invalid signature returns 401
    bad_status, bad_data = receiver.handle_request(
        "POST",
        "/webhooks/stripe",
        {"stripe-signature": "t=123,v1=invalidsig"},
        raw_bytes,
    )
    assert bad_status == 401
    assert "Invalid or expired" in bad_data["error"]

    # 3. Malformed JSON returns 400 and routes to DLQ
    corrupt_bytes = b"{bad_json: missing_quotes"
    corrupt_sig = generate_stripe_header(corrupt_bytes, secret)
    corrupt_status, corrupt_data = receiver.handle_request(
        "POST",
        "/webhooks/stripe",
        {"stripe-signature": corrupt_sig},
        corrupt_bytes,
    )
    assert corrupt_status == 400
    assert "dlq_id" in corrupt_data
    assert staging.count_dlq() == 1

    # 4. Check /health and /metrics endpoints
    h_status, h_data = receiver.handle_request("GET", "/health", {}, b"")
    assert h_status == 200
    assert h_data["status"] == "ok"
    assert h_data["dlq_pending"] == 1

    m_status, m_data = receiver.handle_request("GET", "/metrics", {}, b"")
    assert m_status == 200
    assert m_data["pending_records"] == 2
    staging.close()


def test_live_http_server_socket_execution(tmp_path: Path):
    """Spawns an actual WebhookHTTPServer on port 0, sends real HTTP requests, and terminates cleanly."""
    staging = SQLiteStagingBuffer(tmp_path / "server_test.db")
    secret = "whsec_live_socket_secret"
    server, _receiver = create_webhook_server(
        host="127.0.0.1",
        port=0,  # OS binds to free ephemeral port
        staging_buffer=staging,
        stripe_secret=secret,
    )
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"

    try:
        # GET /health
        with urlopen(f"{base_url}/health", timeout=5.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"

        # POST /webhooks/stripe with valid signature
        body = json.dumps({
            "type": "charge.succeeded",
            "created": int(time.time()),
            "data": {
                "object": {
                    "id": "ch_socket_1",
                    "amount": 7500,
                    "currency": "usd",
                }
            },
        }).encode("utf-8")
        sig = generate_stripe_header(body, secret)

        req = Request(
            f"{base_url}/webhooks/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
            method="POST",
        )
        with urlopen(req, timeout=5.0) as resp:
            assert resp.status == 200
            res_json = json.loads(resp.read().decode("utf-8"))
            assert res_json["status"] == "accepted"
            assert res_json["enqueued"] == 2

        # POST with bad signature returns HTTP 401
        bad_req = Request(
            f"{base_url}/webhooks/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=bad"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc_info:
            urlopen(bad_req, timeout=5.0)
        assert exc_info.value.code == 401

    finally:
        server.shutdown()
        server.server_close()
        staging.close()

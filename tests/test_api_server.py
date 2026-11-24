"""Tests for FunnelScript HTTP Runtime API Server.

Validates:
1. /api/health endpoint.
2. /api/check semantic linter endpoint.
3. /api/simulate execution endpoint returning canonical simulation telemetry for Web Studio.
"""

import json
from http.server import HTTPServer
import threading
import urllib.request
import urllib.error
import pytest

from funnelscript.runtime.server import FunnelScriptAPIHandler


@pytest.fixture(scope="module")
def local_server():
    server = HTTPServer(("127.0.0.1", 0), FunnelScriptAPIHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_api_health_endpoint(local_server: str):
    url = f"{local_server}/api/health"
    with urllib.request.urlopen(url) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"


def test_api_check_endpoint(local_server: str):
    url = f"{local_server}/api/check"
    payload = {
        "$schema": "https://marketing-lang.org",
        "strategy_name": "APITest",
        "metadata": {"author": "Tester", "industry": "Test", "currency": "USD"},
        "environment": {"market_volatility": "low", "competitor_activity": "passive"},
        "entities": {
            "budgets": {"total_budget": 5000, "max_cpc_limit": 1.5, "initial_cash": 10000, "settlement_delay_days": 2},
            "audiences": [{
                "id": "aud_1", "name": "Cold", "type": "cold", "estimated_size": 1000,
                "attributes": {"brand_affinity": 0.5, "price_sensitivity": 0.5, "fomo_index": 0.5},
            }],
            "touchpoints": [
                {"id": "ad_1", "type": "paid_traffic", "base_cpc": 0.5, "ad_creative_score": 0.8},
                {"id": "lp_1", "type": "conversion_surface", "base_conversion_rate": 0.05},
            ],
        },
        "logic_flow": [{"step": 1, "action": "TriggerTraffic", "source": "aud_1", "via": "ad_1", "destination": "lp_1"}],
        "simulation_engine": {
            "engine_type": "Agent-Based_Monte_Carlo",
            "parameters": {"virtual_agents_count": 500, "timeframe_days": 7, "randomness_factor_sigma": 0.1},
            "output_metrics_requested": ["ROAS"],
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["valid"] is True


def test_api_simulate_endpoint(local_server: str):
    url = f"{local_server}/api/simulate"
    payload = {
        "$schema": "https://marketing-lang.org",
        "strategy_name": "APITest",
        "metadata": {"author": "Tester", "industry": "Test", "currency": "USD"},
        "environment": {"market_volatility": "low", "competitor_activity": "passive"},
        "entities": {
            "budgets": {"total_budget": 5000, "max_cpc_limit": 1.5, "initial_cash": 10000, "settlement_delay_days": 2},
            "audiences": [{
                "id": "aud_1", "name": "Cold", "type": "cold", "estimated_size": 1000,
                "attributes": {"brand_affinity": 0.5, "price_sensitivity": 0.5, "fomo_index": 0.5},
            }],
            "touchpoints": [
                {"id": "ad_1", "type": "paid_traffic", "base_cpc": 0.5, "ad_creative_score": 0.8},
                {"id": "lp_1", "type": "conversion_surface", "base_conversion_rate": 0.05},
            ],
        },
        "logic_flow": [{"step": 1, "action": "TriggerTraffic", "source": "aud_1", "via": "ad_1", "destination": "lp_1"}],
        "simulation_engine": {
            "engine_type": "Agent-Based_Monte_Carlo",
            "parameters": {"virtual_agents_count": 500, "timeframe_days": 7, "randomness_factor_sigma": 0.1},
            "output_metrics_requested": ["ROAS"],
        },
        "trials_count": 10,
        "seed": 42,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["strategy_name"] == "APITest"
        assert "roas" in data
        assert "cash_ruin_probability" in data
        assert len(data["daily_trajectories"]) == 7

"""FunnelScript Local Telemetry and Execution API Server.

Provides a lightweight local HTTP bridge connecting visual clients (e.g. apps/web)
directly to the canonical Python simulation engine and Operations Research solver.
Enforces the Single Source of Truth architecture: zero duplicate simulation math in JS/TS.
"""

from __future__ import annotations

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from pydantic import ValidationError

from funnelscript.models import StrategyAST
from funnelscript.compiler.linter import FunnelLinter
from funnelscript.runtime.engine import SimulationEngine
from funnelscript.runtime.exporters import export_report_to_json

logger = logging.getLogger("funnelscript.server")


class FunnelScriptAPIHandler(BaseHTTPRequestHandler):
    """Handles REST API requests from the FunnelScript visual web studio."""

    def _set_cors_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_cors_headers(204)

    def do_GET(self) -> None:
        if self.path in ("/health", "/api/health"):
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "runtime": "FunnelScript Python Core"}).encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 10 * 1024 * 1024:  # 10 MB limit
            self._set_cors_headers(413)
            self.wfile.write(json.dumps({"error": "Payload too large"}).encode("utf-8"))
            return

        body_bytes = self.rfile.read(content_length)

        if self.path == "/api/simulate":
            try:
                raw_json = json.loads(body_bytes.decode("utf-8"))
                ast = StrategyAST.model_validate(raw_json)
            except (json.JSONDecodeError, ValidationError) as exc:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"error": f"Invalid StrategyAST payload: {exc}"}).encode("utf-8"))
                return

            trials = raw_json.get("trials_count", 50)
            seed = raw_json.get("seed", 12345)
            engine = SimulationEngine(ast)
            report = engine.run(num_trials=trials, seed=seed)

            # Format matching Web Studio SimulationResult schema
            daily_trajectories = []
            if report.raw_trials and report.raw_trials[0].daily_snapshots:
                for snapshot in report.raw_trials[0].daily_snapshots:
                    daily_trajectories.append({
                        "day": snapshot.day,
                        "spend": round(snapshot.spend, 2),
                        "revenue": round(snapshot.gross_revenue, 2),
                        "liquid_cash": round(snapshot.liquid_cash, 2),
                    })

            def format_dist(dist: Any) -> dict[str, float]:
                return {
                    "mean": round(dist.mean, 2),
                    "median": round(dist.median, 2),
                    "p10": round(dist.p10, 2),
                    "p90": round(dist.p90, 2),
                }

            result_payload = {
                "strategy_name": report.strategy_name,
                "trials_count": report.trials_count,
                "timeframe_days": report.timeframe_days,
                "roas": format_dist(report.roas),
                "cac": format_dist(report.cac),
                "spend": format_dist(report.spend),
                "revenue": format_dist(report.revenue),
                "probability_of_profit": round(report.probability_of_profit, 4),
                "cash_ruin_probability": round(report.cash_ruin_probability, 4),
                "worst_case_drawdown": round(report.worst_case_drawdown, 2),
                "var_95": round(report.var_95, 2),
                "cvar_95": round(report.cvar_95, 2),
                "daily_trajectories": daily_trajectories,
            }

            self._set_cors_headers(200)
            self.wfile.write(json.dumps(result_payload).encode("utf-8"))

        elif self.path == "/api/check":
            try:
                raw_json = json.loads(body_bytes.decode("utf-8"))
                ast = StrategyAST.model_validate(raw_json)
                linter = FunnelLinter(ast)
                findings = linter.lint()
                self._set_cors_headers(200)
                self.wfile.write(json.dumps({
                    "valid": len(findings) == 0,
                    "findings": [{"rule": f.rule_id, "message": f.message, "severity": f.severity.value} for f in findings],
                }).encode("utf-8"))
            except Exception as exc:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"valid": False, "error": str(exc)}).encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Runs the FunnelScript HTTP runtime API server."""
    server = HTTPServer((host, port), FunnelScriptAPIHandler)
    print(f"FunnelScript Runtime API serving on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

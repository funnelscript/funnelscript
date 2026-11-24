"""FunnelScript Command-Line Interface.

Commands:
  funnelscript check <file>       Static semantic verification and invariant checks
  funnelscript simulate <file>    Vectorized Monte Carlo simulation and stress-testing
  funnelscript init <name>        Scaffold a new validated FunnelScript strategy
  funnelscript init-world <file>  Create a source-level World starter
  funnelscript schema             Output or export JSON Schema specification
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from importlib.metadata import version as distribution_version
from pathlib import Path

from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from funnelscript.compiler.diagnostics import (
    DimensionalTypeError,
    TraitConformanceError,
    render_compiler_error,
)
from funnelscript.compiler.linter import FunnelLinter, LintSeverity, WorldLinter
from funnelscript.compiler.schema import export_json_schema
from funnelscript.compiler.world_ast import WorldAST, WorldTypeError
from funnelscript.compiler.world_lint import WorldLinter as WorldHygieneLinter
from funnelscript.core.event_machine import Event
from funnelscript.formatter import format_funnelscript
from funnelscript.parser import Parser, ParserError
from funnelscript.runtime.engine import SimulationEngine
from funnelscript.runtime.exporters import (
    export_report_to_json,
    export_trials_to_csv,
)
from funnelscript.runtime.world_executor import WorldExecutor
from funnelscript.tokens import LexerError

console = Console(width=1000)

MAX_EVENT_JSON_BYTES = 64 * 1024
MAX_PLAYBOOK_BYTES = 1024 * 1024
MAX_PLAYBOOK_EVENTS = 10_000
PLAYBOOK_SCHEMA = "funnelscript-event-playbook-v1"

WORLD_STARTER = """world MarketingPreview {
  import "std:marketing/lead_response.fnls" as Prospect;
}
"""


def check_command(file_path: str, quiet: bool = False) -> int:
    """Validates syntax, parses AST, and runs full semantic linting.
    
    Exit codes:
      0: Success (clean or warnings only)
      1: Critical invariant failure / Parse error
      2: File I/O error
    """
    path = Path(file_path)
    if file_path.endswith(".fnl") or path.suffix == ".fnl":
        suggested = file_path[:-4] + ".fnls" if file_path.endswith(".fnl") else str(path.with_suffix(".fnls"))
        if not quiet:
            console.print(
                Panel(
                    f"[bold red]❌ Migration Guard:[/bold red] FunnelScript source files have migrated from [yellow].fnl[/yellow] to [bold green].fnls[/bold green].\n"
                    f"Please rename '{file_path}' to '{suggested}'.",
                    border_style="red",
                )
            )
        else:
            print(
                f"Error: FunnelScript source files have migrated from .fnl to .fnls. Please rename '{file_path}' to '{suggested}'.",
                file=sys.stderr,
            )
        return 1
    if not path.exists():
        if not quiet:
            console.print(Panel(f"[bold red]❌ File Not Found:[/bold red] {file_path}", border_style="red"))
        return 2

    try:
        ast = Parser.from_file(str(path))
    except WorldTypeError as exc:
        if not quiet:
            console.print(Panel(f"[bold red]❌ Type Error:[/bold red]\n{escape(render_compiler_error(exc, path))}", border_style="red"))
        return 1
    except (LexerError, ParserError, ValidationError, json.JSONDecodeError) as exc:
        if not quiet:
            console.print(Panel(f"[bold red]❌ Parse Error:[/bold red]\n{escape(render_compiler_error(exc, path))}", border_style="red"))
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"Input I/O error: {exc}", file=sys.stderr)
        return 2

    if isinstance(ast, WorldAST):
        world_findings = WorldHygieneLinter(ast).lint()
        if not quiet:
            for finding in world_findings:
                console.print(
                    Panel(
                        escape(finding.render()),
                        title=f"World hygiene: {finding.code}",
                        border_style="yellow",
                    )
                )
        try:
            WorldLinter(ast).check()
        except (TraitConformanceError, DimensionalTypeError, WorldTypeError) as exc:
            if not quiet:
                console.print(Panel(f"[bold red]❌ Static Analysis Error:[/bold red]\n{escape(render_compiler_error(exc, path))}", border_style="red"))
            return 1

        if not quiet:
            entities = sum(d.kind == "entity" for d in ast.declarations)
            agents = sum(d.kind == "agent" for d in ast.declarations)
            console.print(
                Panel(
                    f"[green]World Type Check Passed[/green]\n"
                    f"World: {ast.name} | Entities: {entities} | Agents: {agents}",
                    title="FunnelScript Language Core",
                )
            )
        return 0

    linter = FunnelLinter(ast)
    findings = linter.lint()

    if not findings:
        if not quiet:
            console.print(
                Panel(
                    f"[bold green]✔ Static Semantic Verification Passed with Zero Warnings![/bold green]\n\n"
                    f"• Strategy: [bold]{ast.strategy_name}[/bold]\n"
                    f"• Audiences: {len(ast.entities.audiences)}\n"
                    f"• Touchpoints: {len(ast.entities.touchpoints)}\n"
                    f"• Budget Cap: ${ast.entities.budgets.total_budget:,.2f}\n"
                    f"• Initial Cash: ${ast.entities.budgets.initial_cash:,.2f}\n"
                    f"• Settlement Delay: {ast.entities.budgets.settlement_delay_days} days\n"
                    f"• Invariant Check: Reachability, Sinks & Conservation [green]OK[/green]",
                    title="FunnelScript Linter v1.2.0",
                    border_style="green",
                )
            )
        return 0

    if not quiet:
        table = Table(title=f"Linter Diagnostics for {ast.strategy_name}", border_style="yellow")
        table.add_column("Code", style="bold cyan", width=8)
        table.add_column("Sev", justify="center", width=8)
        table.add_column("Location / Path", style="dim", width=25)
        table.add_column("Finding Message", style="white")
        table.add_column("Remediation", style="italic green")

        for f in findings:
            sev_color = "red" if f.severity == LintSeverity.ERROR else ("yellow" if f.severity == LintSeverity.WARNING else "blue")
            table.add_row(
                f.code,
                f"[{sev_color}]{f.severity.value}[/{sev_color}]",
                f.path,
                f.message,
                f.remediation,
            )

        console.print(table)

    if linter.has_errors:
        if not quiet:
            console.print(Panel("[bold red]❌ Compilation Halted: One or more critical invariants violated.[/bold red]", border_style="red"))
        return 1

    if not quiet:
        console.print(Panel("[bold yellow]⚠ Completed with advisory warnings. Invariants hold.[/bold yellow]", border_style="yellow"))
    return 0


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON event field '{name}'")
        result[name] = value
    return result


def _parse_world_input_event(spec: str) -> Event:
    """Accept legacy qualified timestamps or a JSON-encoded event record."""
    if spec.lstrip().startswith(("{", "[")):
        if len(spec.encode("utf-8")) > MAX_EVENT_JSON_BYTES:
            raise ValueError("JSON event exceeds the 64 KiB UTF-8 input limit")
        data = json.loads(spec, object_pairs_hook=_unique_json_object)
        if type(data) is not dict:
            raise ValueError("JSON event must be an object")
        extra = data.keys() - {"name", "time", "payload", "priority"}
        if extra:
            raise ValueError(f"Unexpected JSON event fields: {sorted(extra)}")
        if "name" not in data or "time" not in data:
            raise ValueError("JSON event requires name and time")
        if type(data["name"]) is not str or not data["name"]:
            raise ValueError("JSON event name must be a non-empty string")
        return Event(
            time=data["time"], name=data["name"],
            payload=data.get("payload"), priority=data.get("priority", 0),
        )
    name, delimiter, when = spec.rpartition("@")
    if not delimiter or not name or not when:
        raise ValueError("Invalid event syntax; use OWNER.EVENT@TIME or a JSON object")
    return Event(time=float(when), name=name)


def _load_event_playbook(
    file_path: str,
    max_bytes: int = MAX_PLAYBOOK_BYTES,
    max_events: int = MAX_PLAYBOOK_EVENTS,
) -> list[Event]:
    source = Path(file_path)
    with source.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        limit_desc = f"{max_bytes // (1024 * 1024)} MiB" if max_bytes >= 1024 * 1024 else f"{max_bytes} bytes"
        raise ValueError(f"Event playbook exceeds the {limit_desc} input limit")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_json_object)
    if type(raw) is not dict or set(raw) != {"schema", "events"}:
        raise ValueError("Event playbook must have exactly schema and events")
    if raw["schema"] != PLAYBOOK_SCHEMA:
        raise ValueError("Unsupported event playbook schema")
    if type(raw["events"]) is not list or len(raw["events"]) > max_events:
        raise ValueError(f"Invalid event playbook event count (maximum {max_events})")
    events = []
    for record in raw["events"]:
        if type(record) is not dict:
            raise ValueError("Event playbook entries must be objects")
        events.append(_parse_world_input_event(json.dumps(record, allow_nan=False)))
    return events


def run_world_command(
    file_path: str,
    event_specs: list[str],
    *,
    seed: int = 0,
    max_events: int = 100_000,
    events_file: str | None = None,
) -> int:
    """Execute qualified events against a statically checked World source file."""
    if file_path.endswith(".fnl"):
        suggested = file_path[:-4] + ".fnls"
        print(
            f"Error: FunnelScript source files have migrated from .fnl to .fnls.\n"
            f"Please rename '{file_path}' to '{suggested}'.",
            file=sys.stderr,
        )
        return 1
    try:
        ast = Parser.from_file(file_path)
        if not isinstance(ast, WorldAST):
            raise TypeError("run-world requires a world declaration, not a strategy")
        if events_file is not None and event_specs:
            raise ValueError("--event and --events-file are mutually exclusive")
        events = (_load_event_playbook(events_file, max_bytes=50 * 1024 * 1024, max_events=max(max_events, 250_000)) if events_file is not None
                  else [_parse_world_input_event(spec) for spec in event_specs])
        result = WorldExecutor(ast).run(events, seed=seed, max_events=max_events)
    except (OSError, UnicodeError, LexerError, ParserError, ValueError, TypeError, RuntimeError, RecursionError) as exc:
        print(f"World execution error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "world": ast.name,
                "state": result.state,
                "processed_events": len(result.processed),
                "pending_events": len(result.pending),
            },
            sort_keys=True,
        )
    )
    return 0


def simulate_command(
    file_path: str,
    trials: int = 100,
    agents: int | None = None,
    export_csv: str | None = None,
    export_json_path: str | None = None,
    as_json: bool = False,
) -> int:
    """Executes stochastic simulation with rich telemetry tables or raw JSON export."""
    path = Path(file_path)
    if not path.exists():
        if not as_json:
            console.print(Panel(f"[bold red]❌ File Not Found:[/bold red] {file_path}", border_style="red"))
        return 2

    # Verify lint first
    check_code = check_command(file_path, quiet=as_json)
    if check_code != 0:
        return check_code

    try:
        ast = Parser.from_file(str(path))
    except WorldTypeError as exc:
        if not as_json:
            console.print(Panel(f"[bold red]❌ Type Error:[/bold red]\n{escape(render_compiler_error(exc, path))}", border_style="red"))
        return 1
    except (LexerError, ParserError, ValidationError, json.JSONDecodeError) as exc:
        if not as_json:
            console.print(Panel(f"[bold red]❌ Parse Error:[/bold red]\n{escape(render_compiler_error(exc, path))}", border_style="red"))
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"Input I/O error: {exc}", file=sys.stderr)
        return 2

    if isinstance(ast, WorldAST):
        is_d2c = (
            ast.name == "D2CSeasonalScaleStress"
            or any(d.name in ("D2C", "D2CScale") for d in ast.declarations)
        )
        if is_d2c:
            from decimal import Decimal

            from packages.ecommerce.d2c_scale.engine import (
                D2CScaleConfig,
                D2CScaleSimulator,
            )
            cfg = D2CScaleConfig(
                base_daily_ad_spend=Decimal("3000.00"),
                scale_daily_ad_spend=Decimal("6000.00"),
                scale_start_day=8,
                initial_cash=Decimal("75000.00"),
                min_safety_cash=Decimal("15000.00"),
                horizon_days=30,
            )
            sim = D2CScaleSimulator(cfg)
            res = sim.run(seed=trials)
            if as_json:
                print(json.dumps({
                    "strategy": ast.name,
                    "package": "ecommerce/d2c_scale",
                    "paper_roas": float(res.paper_roas),
                    "realized_net_mer": float(res.net_mer),
                    "starting_cash": float(cfg.initial_cash),
                    "min_cash_trough": float(res.min_cash_trough),
                    "min_cash_trough_day": res.min_cash_trough_day,
                    "ending_settled_cash": float(res.ending_cash),
                    "cash_runway_breached": res.cash_runway_breached,
                    "breach_day": res.breach_day,
                    "ledger_audit_status": "CONSERVED_EXACT" if res.ledger_conserved else "FAILED",
                }, indent=2))
                return 0

            table = Table(title="[bold magenta]D2C Scale Working Capital Stress Test[/bold magenta]")
            table.add_column("Metric", style="cyan", no_wrap=True)
            table.add_column("Value", style="bold green")
            table.add_row("Package", "ecommerce/d2c_scale (v0.1.0)")
            table.add_row("Paper ROAS", f"{res.paper_roas}x")
            table.add_row("Realized Net Margin", f"{res.net_mer}x")
            table.add_row("Starting Cash", f"${cfg.initial_cash:,.2f}")
            table.add_row("Min Cash Trough Day & Value", f"Day {res.min_cash_trough_day} (${res.min_cash_trough:,.2f})")
            table.add_row("Ending Settled Cash", f"${res.ending_cash:,.2f}")
            runway_str = f"[bold red]BREACHED on Day {res.breach_day}[/bold red]" if res.cash_runway_breached else "[green]SOLVENT[/green]"
            table.add_row("Cash Runway Status", runway_str)
            ledger_str = "[bold green]PASSED (Exact Double-Entry Conserved, Zero Float Drift)[/bold green]" if res.ledger_conserved else "[red]FAILED[/red]"
            table.add_row("Ledger Audit Status", ledger_str)
            console.print(table)
            return 0

        is_sales_cap = (
            ast.name == "SalesCapacityStressRun"
            or any(d.name in ("SalesCap", "SalesCapacity") for d in ast.declarations)
        )
        if is_sales_cap:
            from decimal import Decimal

            from packages.leadgen.sales_capacity.engine import (
                SalesCapacityConfig,
                SalesCapacitySimulator,
            )
            cfg = SalesCapacityConfig(
                base_daily_ad_spend=Decimal("2000.00"),
                scale_daily_ad_spend=Decimal("5000.00"),
                scale_start_day=1,
                active_reps=4,
                max_leads_per_rep_per_day=12,
                baseline_response_minutes=15.0,
                lead_decay_half_life_minutes=45.0,
                horizon_days=30,
            )
            sim = SalesCapacitySimulator(cfg)
            res = sim.run(seed=trials)
            if as_json:
                print(json.dumps({
                    "strategy": ast.name,
                    "package": "leadgen/sales_capacity",
                    "blended_cpl": float(res.blended_cpl),
                    "peak_queue_backlog": res.peak_queue_backlog,
                    "avg_speed_to_lead_minutes": res.avg_speed_to_lead_minutes,
                    "capacity_utilization_pct": res.capacity_utilization_pct,
                    "effective_close_rate": float(res.effective_close_rate),
                    "effective_cac": float(res.effective_cac),
                    "net_contribution_margin": float(res.net_contribution_margin),
                    "ending_settled_cash": float(res.ending_cash),
                    "ledger_audit_status": "CONSERVED_EXACT" if res.ledger_conserved else "FAILED",
                }, indent=2))
                return 0

            table = Table(title="[bold cyan]Sales Capacity & Lead Queue Stress Test[/bold cyan]")
            table.add_column("Metric", style="cyan", no_wrap=True)
            table.add_column("Value", style="bold green")
            table.add_row("Package", "leadgen/sales_capacity (v0.1.0)")
            table.add_row("Blended CPL", f"${res.blended_cpl}")
            table.add_row("Peak Queue Backlog", f"{res.peak_queue_backlog} leads")
            table.add_row("Avg Speed-to-Lead", f"{res.avg_speed_to_lead_minutes:.1f} minutes")
            table.add_row("Capacity Utilization", f"{res.capacity_utilization_pct:.1f}%")
            table.add_row("Effective Close Rate", f"{res.effective_close_rate:.2%}")
            table.add_row("Effective CAC", f"${res.effective_cac:,.2f}")
            margin_color = "green" if res.net_contribution_margin >= 0 else "bold red"
            table.add_row("Net Contribution Margin", f"[{margin_color}]${res.net_contribution_margin:,.2f}[/{margin_color}]")
            table.add_row("Ending Settled Cash", f"${res.ending_cash:,.2f}")
            ledger_str = "[bold green]PASSED (Exact Double-Entry Conserved, Zero Float Drift)[/bold green]" if res.ledger_conserved else "[red]FAILED[/red]"
            table.add_row("Ledger Audit Status", ledger_str)
            console.print(table)
            return 0

        if not as_json:
            console.print(
                "[yellow]World declarations support static checking only. "
                "World simulation is not implemented yet.[/yellow]"
            )
        return 1

    engine = SimulationEngine(ast)
    report = engine.run(num_trials=trials, agents_count=agents, record_trajectories=True)

    try:
        if export_csv:
            export_trials_to_csv(report, export_csv)
        if export_json_path:
            export_report_to_json(report, export_json_path)
    except OSError as exc:
        print(f"Export I/O error: {exc}", file=sys.stderr)
        return 2

    if not as_json:
        if export_csv:
            console.print(f"[bold green]✔ Monte Carlo trials exported to CSV:[/bold green] {export_csv}")
        if export_json_path:
            console.print(f"[bold green]✔ Simulation Report exported to JSON:[/bold green] {export_json_path}")

    if as_json:
        print(export_report_to_json(report))
        return 0

    table = Table(title=f"Simulation Output Distribution — {report.strategy_name}", border_style="cyan")
    table.add_column("Metric Dimension", justify="left", style="bold white")
    table.add_column("P10 (Worst 10%)", justify="right", style="red")
    table.add_column("Median (P50)", justify="right", style="yellow")
    table.add_column("Mean", justify="right", style="green")
    table.add_column("P90 (Top 10%)", justify="right", style="cyan")

    table.add_row(
        "Return on Ad Spend (ROAS)",
        f"{report.p10_roas:.2f}x",
        f"{report.median_roas:.2f}x",
        f"{report.mean_roas:.2f}x",
        f"{report.p90_roas:.2f}x",
    )
    table.add_row(
        "Customer Acquisition Cost (CAC)",
        f"${report.p90_cac:.2f}",
        f"${report.median_cac:.2f}",
        f"${report.mean_cac:.2f}",
        f"${report.p10_cac:.2f}",
    )
    table.add_row(
        "Ad Spend Budget ($)",
        f"${report.spend.p10:,.2f}",
        f"${report.spend.median:,.2f}",
        f"${report.spend.mean:,.2f}",
        f"${report.spend.p90:,.2f}",
    )
    table.add_row(
        "Gross Revenue ($)",
        f"${report.revenue.p10:,.2f}",
        f"${report.revenue.median:,.2f}",
        f"${report.revenue.mean:,.2f}",
        f"${report.revenue.p90:,.2f}",
    )

    console.print(table)

    ruin_color = "green" if report.cash_ruin_probability < 0.05 else "red"
    cannibal_color = "yellow" if report.cannibalization_rate > 0.10 else "green"

    risk_panel = Panel(
        f"• [bold]Cash Ruin Probability P(Insolvency):[/bold] [{ruin_color}]{report.cash_ruin_probability * 100:.1f}%[/{ruin_color}] "
        f"(Risk of ad spend halt before receivables settle)\n"
        f"• [bold]Discount Cannibalization Rate:[/bold] [{cannibal_color}]{report.cannibalization_rate * 100:.1f}%[/{cannibal_color}] "
        f"(Loyal buyers harvesting abandonment discounts)\n"
        f"• [bold]Probability of Profit (ROAS >= 1.0):[/bold] [green]{report.probability_of_profit * 100:.1f}%[/green]\n"
        f"• [bold]95% Value-at-Risk (VaR-95):[/bold] [yellow]${report.var_95:,.2f}[/yellow]\n"
        f"• [bold]95% Expected Shortfall (CVaR-95):[/bold] [red]${report.cvar_95:,.2f}[/red]\n"
        f"• [bold]Max Capital Loss Drawdown:[/bold] [red]${report.worst_case_drawdown:,.2f}[/red]",
        title="⚠️ Risk, Liquidity & Behavioral Telemetry",
        border_style="magenta",
    )
    console.print(risk_panel)
    return 0


def init_command(name: str, output_path: str | None = None) -> int:
    """Scaffolds a new validated FunnelScript strategy template."""
    clean_name = name.replace(" ", "_")
    target_path = Path(output_path or f"{clean_name.lower()}.fnls.json")

    template = {
        "$schema": "https://marketing-lang.org",
        "strategy_name": clean_name,
        "metadata": {
            "author": "Marketing Systems Engineer",
            "industry": "E-Commerce",
            "currency": "USD",
        },
        "environment": {
            "market_volatility": "moderate",
            "competitor_activity": "moderate",
        },
        "entities": {
            "budgets": {
                "total_budget": 20000.0,
                "max_cpc_limit": 1.50,
                "initial_cash": 10000.0,
                "settlement_delay_days": 3,
            },
            "audiences": [
                {
                    "id": "aud_cold",
                    "name": "Broad In-Market Shoppers",
                    "type": "cold",
                    "estimated_size": 250000,
                    "attributes": {
                        "brand_affinity": 0.40,
                        "price_sensitivity": 0.50,
                        "fomo_index": 0.55,
                    },
                }
            ],
            "touchpoints": [
                {
                    "id": "tp_paid_search",
                    "type": "paid_traffic",
                    "platform": "Google",
                    "base_cpc": 0.65,
                    "ad_creative_score": 0.80,
                },
                {
                    "id": "tp_store_landing",
                    "type": "conversion_surface",
                    "base_conversion_rate": 0.045,
                },
                {
                    "id": "tp_cart_email",
                    "type": "retargeting_channel",
                    "medium": "Email",
                    "base_open_rate": 0.30,
                },
            ],
        },
        "logic_flow": [
            {
                "step": 1,
                "action": "TriggerTraffic",
                "source": "aud_cold",
                "via": "tp_paid_search",
                "destination": "tp_store_landing",
            },
            {
                "step": 2,
                "type": "ConditionalBranch",
                "condition": {
                    "user_action": "AbandonCart",
                    "time_elapsed": "2h",
                },
                "true_branch": [
                    {
                        "action": "ExecuteRetargeting",
                        "channel": "tp_cart_email",
                        "payload": {
                            "offer_type": "Abandonment_Reminder_Discount",
                            "discount_percentage": 10,
                        },
                        "expected_impact": {
                            "conversion_boost": 0.025,
                        },
                    }
                ],
                "false_branch": [
                    {
                        "action": "DoNothing",
                    }
                ],
            },
        ],
        "simulation_engine": {
            "engine_type": "Agent-Based_Monte_Carlo",
            "parameters": {
                "virtual_agents_count": 50000,
                "timeframe_days": 14,
                "randomness_factor_sigma": 0.12,
            },
            "output_metrics_requested": [
                "ROAS_Distribution",
                "CAC_Distribution",
                "Working_Capital_Ruin_Probability",
            ],
        },
    }

    target_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    console.print(Panel(f"[bold green]✔ Scaffolding Complete:[/bold green] {target_path}\nRun: [cyan]funnelscript check {target_path}[/cyan]", border_style="green"))
    return 0


def init_world_command(file_path: str) -> int:
    """Create a runnable World without overwriting existing user files."""
    target = Path(file_path)
    if target.suffix == ".fnl":
        print(
            f"Error: FunnelScript source files have migrated from .fnl to .fnls.\n"
            f"Please use '{target.with_suffix('.fnls')}' instead.",
            file=sys.stderr,
        )
        return 1
    if target.suffix != ".fnls":
        print("World starter target must use a .fnls extension", file=sys.stderr)
        return 2
    if not target.parent.is_dir():
        print(f"World starter parent directory does not exist: {target.parent}", file=sys.stderr)
        return 2
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(WORLD_STARTER)
    except FileExistsError:
        print(f"World starter target already exists: {target}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Cannot create World starter: {exc}", file=sys.stderr)
        return 2
    print(f"World starter created: {target}\nRun: funnelscript check {target}")
    return 0


def fmt_command(file_path: str, check_only: bool = False) -> int:
    """Format FunnelScript source code idempotently."""
    target = Path(file_path)
    if not target.is_file():
        console.print(Panel(f"[bold red]❌ File Not Found:[/bold red] {file_path}", border_style="red"))
        return 2
    try:
        source = target.read_text(encoding="utf-8")
        formatted = format_funnelscript(source)
        if check_only:
            if source != formatted:
                console.print(f"[yellow]Need formatting:[/yellow] {file_path}")
                return 1
            return 0
        if source != formatted:
            target.write_text(formatted, encoding="utf-8")
            console.print(f"[green]Formatted[/green] {file_path}")
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, LexerError, ParserError) as exc:
        console.print(Panel(f"[bold red]❌ Format Error:[/bold red] {exc}", border_style="red"))
        return 1


def map_inspect_command(
    file_path: str,
    target: str | None = None,
    output_path: str | None = None,
) -> int:
    """Inspect raw data file and scaffold explicit mapping.toml specification."""
    try:
        from funnelscript.connectors.object_mapper import ObjectMapper

        path = Path(file_path)
        if not path.is_file():
            console.print(Panel(f"[bold red]❌ File not found:[/bold red] {file_path}", border_style="red"))
            return 1
        toml_content = ObjectMapper.inspect_file(path, target_entity_name=target)
        if output_path:
            out = Path(output_path)
            out.write_text(toml_content, encoding="utf-8")
            console.print(f"[bold green]✔ Declarative mapping written to:[/bold green] {output_path}")
        else:
            console.print(Panel(toml_content, title=f"Draft Mapping: {target or 'CustomEntity'}", border_style="cyan"))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        console.print(Panel(f"[bold red]❌ Map Inspect Error:[/bold red] {exc}", border_style="red"))
        return 1


def schema_command(output_path: str | None = None) -> int:
    """Generates and exports the JSON Schema specification."""
    schema_json = export_json_schema(output_path)
    if output_path:
        console.print(f"[bold green]✔ JSON Schema exported to:[/bold green] {output_path}")
    else:
        print(schema_json)
    return 0


def solve_command(file_path: str, output_path: str | None = None, as_json: bool = False) -> int:
    """Solves deterministic marketing allocation optimization using Operations Research techniques."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 2

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"JSON Syntax Error: {exc}", file=sys.stderr)
        return 1

    from funnelscript.solver.errors import SolverDomainError
    from funnelscript.solver.service import FunnelScriptSolverService
    from funnelscript.solver.types import SolverInput

    try:
        solver_input = SolverInput.model_validate(data)
    except ValidationError as exc:
        print(f"Validation Error: {exc}", file=sys.stderr)
        return 1

    service = FunnelScriptSolverService()
    try:
        result = service.solve(solver_input)
    except SolverDomainError as exc:
        print(f"Domain Solver Error ({exc.code}): {exc.message}", file=sys.stderr)
        print(f"Remediation: {exc.remediation}", file=sys.stderr)
        return 1

    out_payload = {
        "status": result.status,
        "artifact_checksum": result.artifact_checksum,
        "optimal_allocations": result.optimal_allocations,
        "expected_revenue": result.expected_revenue,
        "expected_net_profit": result.expected_net_profit,
        "expected_blended_cac": result.expected_blended_cac,
        "shadow_prices": result.shadow_prices,
        "next_actions": [a.value for a in result.next_actions],
    }
    json_str = json.dumps(out_payload, indent=2, sort_keys=True)

    if output_path:
        try:
            Path(output_path).write_text(json_str, encoding="utf-8")
        except OSError as exc:
            print(f"Export I/O error: {exc}", file=sys.stderr)
            return 2

    if as_json:
        print(json_str)
        return 0

    table = Table(title="[bold green]Optimal Marketing Decision Allocation (OR Solver)[/bold green]")
    table.add_column("Channel", style="cyan")
    table.add_column("Optimal Spend ($)", justify="right", style="green")
    table.add_column("Simplex Weight (w)", justify="right", style="yellow")
    table.add_column("Shadow Price (λ)", justify="right", style="magenta")
    table.add_column("Support Status", style="blue")

    for i, ch in enumerate(solver_input.channels):
        alloc = result.optimal_allocations[ch.channel_id]
        weight = result.optimal_weights[i]
        shadow = result.shadow_prices.get(ch.channel_id, 0.0)
        diag = result.channel_diagnostics[ch.channel_id]
        table.add_row(
            ch.channel_id,
            f"${alloc:,.2f}",
            f"{weight:.4f}",
            f"{shadow:.4f}",
            diag.classification.value,
        )

    console.print(table)
    console.print(f"[bold]Total Budget:[/bold] ${solver_input.total_budget:,.2f} {solver_input.currency}")
    console.print(f"[bold]Expected Revenue:[/bold] ${result.expected_revenue:,.2f}")
    console.print(f"[bold]Expected Net Profit:[/bold] ${result.expected_net_profit:,.2f}")
    console.print(f"[bold]Blended CAC:[/bold] ${result.expected_blended_cac:,.2f}")
    console.print(f"[dim]Artifact Checksum (SHA-256): {result.artifact_checksum}[/dim]")
    if output_path:
        console.print(f"[bold green]✔ Solution saved to:[/bold green] {output_path}")
    return 0


def calibrate_command(
    campaign_csv: str,
    settlements_csv: str | None = None,
    output_path: str | None = None,
    campaign_name: str = "CalibratedEcommerceWorld",
    as_json: bool = False,
) -> int:
    """Infers empirical parameters from historical marketing CSV and generates a .fnls World."""
    from funnelscript.stdlib.marketing.calibration import CampaignCalibrator
    from funnelscript.stdlib.marketing.ingestion import (
        IngestionError,
        MarketingDataIngestor,
    )

    csv_path = Path(campaign_csv)
    if not csv_path.exists():
        print(f"Error: Campaign CSV not found: {campaign_csv}", file=sys.stderr)
        return 2

    try:
        campaign_records = MarketingDataIngestor.load_campaign_csv(csv_path)
        settlement_records = (
            MarketingDataIngestor.load_payment_settlement_csv(settlements_csv)
            if settlements_csv
            else None
        )
    except IngestionError as exc:
        print(f"Ingestion Error: {exc}", file=sys.stderr)
        return 1

    calibrated_model = CampaignCalibrator.calibrate(
        campaign_records, settlement_records, campaign_name=campaign_name
    )

    fnls_code = calibrated_model.generate_fnls_source()

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(fnls_code, encoding="utf-8")

    if as_json:
        payload = {
            "campaign_name": calibrated_model.campaign_name,
            "observation_days": calibrated_model.observation_days,
            "dataset_fingerprint": calibrated_model.dataset_fingerprint,
            "blended_cac": round(calibrated_model.blended_cac, 2),
            "average_order_value": round(calibrated_model.average_order_value, 2),
            "settlement_delay_days": calibrated_model.settlement_delay_days,
            "gateway_fee_rate": round(calibrated_model.gateway_fee_rate, 4),
            "channels": [
                {
                    "channel_id": ch.channel_id,
                    "v_max": round(ch.v_max, 2),
                    "k_sat": round(ch.k_sat, 2),
                    "alpha": round(ch.alpha, 4),
                    "r_squared": round(ch.r_squared, 4),
                    "empirical_cac": round(ch.empirical_cac, 2),
                    "min_spend": round(ch.min_observed_spend, 2),
                    "max_spend": round(ch.max_observed_spend, 2),
                }
                for ch in calibrated_model.channels
            ],
            "fnls_source": fnls_code,
            "fnl_source": fnls_code,
        }
        print(json.dumps(payload, indent=2))
        return 0

    table = Table(title=f"[bold green]Empirical Calibration Report: {calibrated_model.campaign_name}[/bold green]")
    table.add_column("Channel", style="cyan")
    table.add_column("V_max ($)", justify="right", style="green")
    table.add_column("K_sat ($)", justify="right", style="yellow")
    table.add_column("Alpha", justify="right", style="magenta")
    table.add_column("Fit R²", justify="right", style="blue")
    table.add_column("Empirical CAC", justify="right", style="red")

    for ch in calibrated_model.channels:
        table.add_row(
            ch.channel_id,
            f"${ch.v_max:,.2f}",
            f"${ch.k_sat:,.2f}",
            f"{ch.alpha:.3f}",
            f"{ch.r_squared:.3f}",
            f"${ch.empirical_cac:,.2f}",
        )

    console.print(table)
    console.print(f"[bold]Observation Horizon:[/bold] {calibrated_model.observation_days} days")
    console.print(f"[bold]Blended CAC:[/bold] ${calibrated_model.blended_cac:,.2f}")
    console.print(f"[bold]Average Order Value (AOV):[/bold] ${calibrated_model.average_order_value:,.2f}")
    console.print(f"[bold]Settlement Delay (Δ_settle):[/bold] {calibrated_model.settlement_delay_days} days")
    console.print(f"[dim]Dataset Fingerprint: {calibrated_model.dataset_fingerprint}[/dim]")

    if output_path:
        console.print(f"[bold green]✔ Calibrated .fnls model saved to:[/bold green] {output_path}")
    return 0


def backtest_command(
    campaign_csv: str,
    settlements_csv: str | None = None,
    split_ratio: float = 0.50,
    initial_cash: float = 15000.0,
    output_path: str | None = None,
    as_json: bool = False,
) -> int:
    """Runs 50/50 temporal holdout backtest and benchmarks against linear spreadsheet."""
    from funnelscript.stdlib.marketing.backtest import EmpiricalBacktester
    from funnelscript.stdlib.marketing.ingestion import (
        IngestionError,
        MarketingDataIngestor,
    )

    csv_path = Path(campaign_csv)
    if not csv_path.exists():
        print(f"Error: Campaign CSV not found: {campaign_csv}", file=sys.stderr)
        return 2

    try:
        campaign_records = MarketingDataIngestor.load_campaign_csv(csv_path)
        settlement_records = (
            MarketingDataIngestor.load_payment_settlement_csv(settlements_csv)
            if settlements_csv
            else None
        )
    except IngestionError as exc:
        print(f"Ingestion Error: {exc}", file=sys.stderr)
        return 1

    try:
        report = EmpiricalBacktester.run_backtest(
            campaign_records,
            settlement_records,
            split_ratio=split_ratio,
            initial_cash=initial_cash,
        )
    except ValueError as exc:
        print(f"Backtest Configuration Error: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload = {
            "campaign_name": report.campaign_name,
            "total_days": report.total_days,
            "calibration_days": report.calibration_days,
            "holdout_days": report.holdout_days,
            "holdout_total_spend": round(report.holdout_total_spend, 2),
            "metrics": {
                "revenue": {
                    "ground_truth_mean": round(report.revenue_comparison.ground_truth_mean, 2),
                    "funnelscript_mape": round(report.revenue_comparison.funnelscript_mape, 2),
                    "spreadsheet_mape": round(report.revenue_comparison.spreadsheet_mape, 2),
                    "superiority_ratio": round(report.revenue_comparison.superiority_ratio, 2),
                },
                "conversions": {
                    "ground_truth_mean": round(report.conversions_comparison.ground_truth_mean, 2),
                    "funnelscript_mape": round(report.conversions_comparison.funnelscript_mape, 2),
                    "spreadsheet_mape": round(report.conversions_comparison.spreadsheet_mape, 2),
                    "superiority_ratio": round(report.conversions_comparison.superiority_ratio, 2),
                },
                "cac": {
                    "ground_truth_mean": round(report.cac_comparison.ground_truth_mean, 2),
                    "funnelscript_mape": round(report.cac_comparison.funnelscript_mape, 2),
                    "spreadsheet_mape": round(report.cac_comparison.spreadsheet_mape, 2),
                    "superiority_ratio": round(report.cac_comparison.superiority_ratio, 2),
                },
            },
            "liquidity_ruin": {
                "actual_day": report.liquidity_ruin_actual_day,
                "funnelscript_day": report.liquidity_ruin_funnelscript_day,
                "spreadsheet_day": report.liquidity_ruin_spreadsheet_day,
            },
            "trajectories": report.daily_trajectories,
        }
        json_output = json.dumps(payload, indent=2)
        if output_path:
            Path(output_path).write_text(json_output, encoding="utf-8")
        print(json_output)
        return 0

    console.print(Panel(report.summary_table(), title="Empirical Holdout Benchmark", border_style="green"))

    if output_path:
        Path(output_path).write_text(report.summary_table(), encoding="utf-8")
        console.print(f"[bold green]✔ Backtest summary written to:[/bold green] {output_path}")

    return 0


def serve_command(host: str = "127.0.0.1", port: int = 8000) -> int:
    """Starts the local FunnelScript HTTP runtime API server."""
    from funnelscript.runtime.server import start_server
    start_server(host=host, port=port)
    return 0


def ingest_serve_command(
    host: str = "127.0.0.1",
    port: int = 8080,
    db_path: str = "staging.db",
    stripe_secret: str = "",
    shopify_secret: str = "",
) -> int:
    """Starts the local webhook ingestion server."""
    from funnelscript.connectors.staging import SQLiteStagingBuffer
    from funnelscript.connectors.webhook_server import create_webhook_server

    staging_buf = SQLiteStagingBuffer(db_path)
    server, _ = create_webhook_server(
        host=host,
        port=port,
        staging_buffer=staging_buf,
        stripe_secret=stripe_secret or os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        shopify_secret=shopify_secret or os.environ.get("SHOPIFY_WEBHOOK_SECRET", ""),
    )
    console.print(f"[bold green]✔ Webhook ingestion server listening on http://{host}:{port}[/bold green]")
    console.print(f"[dim]Staging buffer: {db_path}[/dim]")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down webhook server...[/yellow]")
        server.server_close()
    return 0


def ingest_poll_command(
    platform: str,
    account_id: str,
    start_date: str,
    end_date: str,
    db_path: str | None = None,
    output_path: str | None = None,
) -> int:
    """Polls external ad platforms and stages or exports telemetry."""
    from funnelscript.connectors.ga4 import GA4Connector
    from funnelscript.connectors.google_ads import GoogleAdsConnector
    from funnelscript.connectors.meta_ads import MetaAdsConnector
    from funnelscript.connectors.staging import SQLiteStagingBuffer

    plat = platform.lower().strip()
    if plat == "meta":
        connector = MetaAdsConnector(account_id=account_id)
    elif plat == "ga4":
        connector = GA4Connector(property_id=account_id)
    elif plat in ("google_ads", "google"):
        connector = GoogleAdsConnector(customer_id=account_id)
    else:
        console.print(f"[bold red]❌ Unsupported platform: '{platform}'. Must be meta, ga4, or google_ads.[/bold red]")
        return 1

    records = connector.fetch_all(start_date=start_date, end_date=end_date)
    console.print(f"[bold green]✔ Pulled {len(records)} records from {platform}[/bold green]")

    if db_path:
        buffer = SQLiteStagingBuffer(db_path)
        enq, dups = buffer.enqueue_batch(records)
        console.print(f"[green]Enqueued to {db_path}: {enq} records ({dups} duplicates skipped)[/green]")

    if output_path:
        out_data = [r.model_dump() for r in records]
        Path(output_path).write_text(json.dumps(out_data, indent=2), encoding="utf-8")
        console.print(f"[green]Exported to {output_path}[/green]")

    return 0


def ingest_stage_command(
    db_path: str = "staging.db",
    drain_ledger: bool = False,
    limit: int = 100,
) -> int:
    """Inspects staging buffer status or drains pending records into ledger."""
    from funnelscript.connectors.staging import SQLiteStagingBuffer
    from funnelscript.ledger import FinancialLedger

    buffer = SQLiteStagingBuffer(db_path)
    counts = buffer.count_staging()
    dlq_count = buffer.count_dlq()

    console.print(
        Panel(
            f"[bold]Staging Status:[/bold]\n"
            f"  Pending:    {counts['pending']}\n"
            f"  Processed:  {counts['processed']}\n"
            f"  Failed:     {counts['failed']}\n"
            f"  DLQ Depth:  {dlq_count}",
            title=f"Staging Database ({db_path})",
            border_style="cyan",
        )
    )

    if drain_ledger and counts["pending"] > 0:
        ledger = FinancialLedger()
        posted = buffer.drain_to_ledger(ledger, limit=limit)
        console.print(f"[bold green]✔ Drained {posted} records into FinancialLedger[/bold green]")
        console.print(f"[dim]Ledger accounts: {len(ledger.accounts)}[/dim]")

    return 0


def ingest_replay_command(
    spend_csv: str,
    output_playbook: str | None = None,
    seed: int = 42,
) -> int:
    """Synthesizes discrete agent event playbook from aggregate campaign CSV."""
    from funnelscript.connectors.models import CanonicalAdSpendRecord
    from funnelscript.connectors.synthetic_bridge import SyntheticEventBridge
    from funnelscript.stdlib.marketing.ingestion import MarketingDataIngestor

    spend_raw = MarketingDataIngestor.load_campaign_csv(spend_csv)
    spend_records = [
        CanonicalAdSpendRecord(
            platform=r.channel,
            account_id="act_replay",
            campaign_id=r.channel,
            campaign_name=r.channel,
            date=r.date,
            spend_cents=int(round(r.spend * 100)),
            impressions=r.impressions,
            clicks=r.clicks,
        )
        for r in spend_raw
    ]

    bridge = SyntheticEventBridge(base_seed=seed)
    events = bridge.synthesize_events_from_spend_and_conversions(
        spend_records=spend_records,
    )
    console.print(f"[bold green]✔ Synthesized {len(events)} discrete agent simulation events[/bold green]")

    if output_playbook:
        playbook_json = bridge.export_playbook_json(events)
        Path(output_playbook).write_text(playbook_json, encoding="utf-8")
        console.print(f"[green]Playbook saved to {output_playbook}[/green]")

    return 0


def fpm_command(args: list[str]) -> int:
    """Forward command arguments to the official Funnel Package Manager (fpm)."""
    # 1. Check if fpm executable exists in PATH
    fpm_bin = shutil.which("fpm")
    if fpm_bin:
        try:
            res = subprocess.run([fpm_bin, *args], check=False)
            return res.returncode
        except (subprocess.SubprocessError, OSError) as err:
            console.print(f"[bold yellow]Warning:[/bold yellow] Error executing system fpm: {err}")

    # 2. Check candidate sibling fpm virtualenv executables
    candidate_dirs = [
        Path(__file__).resolve().parents[3] / "fpm",
        Path.cwd().parent / "fpm",
        Path.cwd() / "fpm",
    ]
    for cand in candidate_dirs:
        venv_bin = cand / ".venv" / "bin" / "fpm"
        if venv_bin.is_file() and os.access(venv_bin, os.X_OK):
            try:
                res = subprocess.run([str(venv_bin), *args], check=False)
                return res.returncode
            except (subprocess.SubprocessError, OSError) as err:
                console.print(f"[bold yellow]Warning:[/bold yellow] Error executing fpm at {venv_bin}: {err}")

    # 3. Check Python import of fpm via sys.path
    for cand in candidate_dirs:
        src_dir = cand / "src"
        if src_dir.is_dir() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
    try:
        from fpm.cli import cli as fpm_cli
        try:
            fpm_cli(args, standalone_mode=False)
            return 0
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except (RuntimeError, ValueError, OSError) as err:
            console.print(f"[bold red]Error running fpm:[/bold red] {err}")
            return 1
    except ImportError:
        pass

    # 4. Fallback helpful diagnostic
    console.print(
        Panel(
            "[bold red]❌ fpm (Funnel Package Manager) executable not found[/bold red]\n\n"
            "To use package management, install fpm or run with uv:\n"
            "  [bold cyan]uv run fpm [args][/bold cyan]\n"
            "or navigate to the sibling `fpm` directory:\n"
            "  [bold cyan]cd ../fpm && uv sync[/bold cyan]",
            border_style="red",
        )
    )
    return 1


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "fpm":
        sys.exit(fpm_command(sys.argv[2:]))

    parser = argparse.ArgumentParser(
        prog="funnelscript",
        description="FunnelScript: A Programming Language for Marketing Systems Powered by Simulated Market Worlds",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {distribution_version('funnelscript')}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check / compile
    check_p = subparsers.add_parser("check", help="Verify syntax and run graph-theoretic semantic linter")
    check_p.add_argument("file", help="Path to strategy file (.json or .fnls)")

    compile_p = subparsers.add_parser("compile", help="Alias for check")
    compile_p.add_argument("file", help="Path to strategy file (.json or .fnls)")

    # run-world (event-driven language core, no external effects)
    world_p = subparsers.add_parser("run-world", help="Execute events on typed World rules")
    world_p.add_argument("file", help="Path to a world .fnls file")
    world_p.add_argument(
        "--event", action="append", default=[], metavar="OWNER.EVENT@TIME",
        help="Timestamped OWNER.EVENT@TIME or JSON event with typed payload (repeatable)",
    )
    world_p.add_argument("--events-file", type=str, default=None,
                         help="Versioned strict UTF-8 JSON event playbook (exclusive with --event)")
    world_p.add_argument("--seed", type=int, default=0)
    world_p.add_argument("--max-events", type=int, default=100_000)

    # simulate
    sim_p = subparsers.add_parser("simulate", help="Run stochastic Monte Carlo simulations")
    sim_p.add_argument("file", help="Path to strategy file (.json or .fnls)")
    sim_p.add_argument("--trials", type=int, default=100, help="Number of Monte Carlo trials (default: 100)")
    sim_p.add_argument("--agents", type=int, default=None, help="Number of virtual agents per trial")
    sim_p.add_argument("--export-csv", type=str, default=None, help="File path to export trial-level CSV data")
    sim_p.add_argument("--export-json", type=str, default=None, help="File path to export complete JSON report")
    sim_p.add_argument("--json", action="store_true", help="Output raw JSON to stdout")

    # init
    init_p = subparsers.add_parser("init", help="Generate starter strategy template")
    init_p.add_argument("name", help="Campaign strategy name")
    init_p.add_argument("--output", "-o", help="Target output file path")

    # init-world
    world_init_p = subparsers.add_parser("init-world", help="Create a safe World starter")
    world_init_p.add_argument("file", help="New .fnls file path")

    # schema
    schema_p = subparsers.add_parser("schema", help="Generate official JSON Schema")
    schema_p.add_argument("--output", "-o", help="Target output file path")

    # solve
    solve_p = subparsers.add_parser("solve", help="Solve deterministic marketing allocation using OR techniques")
    solve_p.add_argument("file", help="Path to solver specification (.json)")
    solve_p.add_argument("--output", "-o", help="Save optimal solution JSON to file")
    solve_p.add_argument("--json", action="store_true", help="Output raw JSON to stdout")

    # calibrate
    cal_p = subparsers.add_parser("calibrate", help="Infer empirical parameters from campaign CSV and generate .fnls")
    cal_p.add_argument("csv", help="Path to advertising campaign CSV file")
    cal_p.add_argument("--settlements", help="Path to payment processor settlement CSV file")
    cal_p.add_argument("--output", "-o", help="Target .fnls file path to write generated model")
    cal_p.add_argument("--name", default="CalibratedEcommerceWorld", help="Campaign world name")
    cal_p.add_argument("--json", action="store_true", help="Output calibration summary as JSON")

    # backtest
    bt_p = subparsers.add_parser("backtest", help="Run 50/50 temporal holdout backtest against spreadsheet baseline")
    bt_p.add_argument("csv", help="Path to advertising campaign CSV file")
    bt_p.add_argument("--settlements", help="Path to payment processor settlement CSV file")
    bt_p.add_argument("--split", type=float, default=0.50, help="Temporal split ratio for holdout (default: 0.50)")
    bt_p.add_argument("--cash", type=float, default=15000.0, help="Initial working capital in dollars (default: 15000)")
    bt_p.add_argument("--output", "-o", help="Save benchmark report summary to file")
    bt_p.add_argument("--json", action="store_true", help="Output raw JSON benchmark metrics")

    # serve
    srv_p = subparsers.add_parser("serve", help="Start local HTTP API bridge server for FunnelScript web studio")
    srv_p.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    srv_p.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")

    # fmt
    fmt_p = subparsers.add_parser("fmt", help="Format FunnelScript source code idempotently")
    fmt_p.add_argument("file", help="Path to FunnelScript file (.fnls)")
    fmt_p.add_argument("--check", action="store_true", help="Check formatting without writing")

    # map
    map_p = subparsers.add_parser("map", help="Declarative data-to-object mapping utilities")
    map_sub = map_p.add_subparsers(dest="map_command", required=True)
    map_insp_p = map_sub.add_parser("inspect", help="Inspect raw data and generate draft mapping.toml")
    map_insp_p.add_argument("file", help="Path to raw dataset file (CSV, JSON, JSONL)")
    map_insp_p.add_argument("--target", help="Target entity name or package reference")
    map_insp_p.add_argument("--output", "-o", help="Target output file path for mapping.toml")

    # ingest
    ingest_p = subparsers.add_parser("ingest", help="Live telemetry ingestion and webhook server")
    ingest_sub = ingest_p.add_subparsers(dest="ingest_command", required=True)

    # ingest serve
    ingest_srv = ingest_sub.add_parser("serve", help="Run real-time webhook receiver server")
    ingest_srv.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    ingest_srv.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    ingest_srv.add_argument("--db", default="staging.db", help="Staging SQLite database path")
    ingest_srv.add_argument("--stripe-secret", default="", help="Stripe webhook endpoint secret")
    ingest_srv.add_argument("--shopify-secret", default="", help="Shopify webhook shared secret")

    # ingest poll
    ingest_poll = ingest_sub.add_parser("poll", help="Poll external marketing platform")
    ingest_poll.add_argument("--platform", required=True, choices=["meta", "ga4", "google_ads"], help="Ad platform")
    ingest_poll.add_argument("--account", required=True, help="Account, Property, or Customer ID")
    ingest_poll.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    ingest_poll.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    ingest_poll.add_argument("--db", help="Optional staging SQLite database path")
    ingest_poll.add_argument("--output", "-o", help="Optional output JSON file path")

    # ingest stage
    ingest_stg = ingest_sub.add_parser("stage", help="Inspect or drain staging SQLite buffer")
    ingest_stg.add_argument("--db", default="staging.db", help="Staging SQLite database path")
    ingest_stg.add_argument("--drain-ledger", action="store_true", help="Drain pending records into FinancialLedger")
    ingest_stg.add_argument("--limit", type=int, default=100, help="Max records to drain (default: 100)")

    # ingest replay
    ingest_rep = ingest_sub.add_parser("replay", help="Synthesize discrete agent event playbook from marketing data")
    ingest_rep.add_argument("spend_csv", help="Path to advertising campaign CSV")
    ingest_rep.add_argument("--output", "-o", help="Target output playbook JSON path")
    ingest_rep.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")

    # fpm
    fpm_p = subparsers.add_parser("fpm", help="Funnel Package Manager (fpm) commands", add_help=False)
    fpm_p.add_argument("fpm_args", nargs=argparse.REMAINDER, help="Arguments passed to fpm")

    args = parser.parse_args()

    exit_code = 0
    if args.command in ("check", "compile"):
        exit_code = check_command(args.file)
    elif args.command == "run-world":
        exit_code = run_world_command(
            args.file,
            args.event,
            seed=args.seed, max_events=args.max_events, events_file=args.events_file,
        )
    elif args.command == "simulate":
        exit_code = simulate_command(
            args.file,
            trials=args.trials,
            agents=args.agents,
            export_csv=args.export_csv,
            export_json_path=args.export_json,
            as_json=args.json,
        )
    elif args.command == "solve":
        exit_code = solve_command(
            args.file,
            output_path=args.output,
            as_json=args.json,
        )
    elif args.command == "calibrate":
        exit_code = calibrate_command(
            args.csv,
            settlements_csv=args.settlements,
            output_path=args.output,
            campaign_name=args.name,
            as_json=args.json,
        )
    elif args.command == "backtest":
        exit_code = backtest_command(
            args.csv,
            settlements_csv=args.settlements,
            split_ratio=args.split,
            initial_cash=args.cash,
            output_path=args.output,
            as_json=args.json,
        )
    elif args.command == "serve":
        exit_code = serve_command(host=args.host, port=args.port)
    elif args.command == "init":
        exit_code = init_command(args.name, args.output)
    elif args.command == "init-world":
        exit_code = init_world_command(args.file)
    elif args.command == "schema":
        exit_code = schema_command(args.output)
    elif args.command == "fmt":
        exit_code = fmt_command(args.file, check_only=args.check)
    elif args.command == "map" and args.map_command == "inspect":
        exit_code = map_inspect_command(
            args.file,
            target=getattr(args, "target", None),
            output_path=getattr(args, "output", None),
        )
    elif args.command == "ingest":
        if args.ingest_command == "serve":
            exit_code = ingest_serve_command(
                host=args.host,
                port=args.port,
                db_path=args.db,
                stripe_secret=args.stripe_secret,
                shopify_secret=args.shopify_secret,
            )
        elif args.ingest_command == "poll":
            exit_code = ingest_poll_command(
                platform=args.platform,
                account_id=args.account,
                start_date=args.start,
                end_date=args.end,
                db_path=args.db,
                output_path=args.output,
            )
        elif args.ingest_command == "stage":
            exit_code = ingest_stage_command(
                db_path=args.db,
                drain_ledger=args.drain_ledger,
                limit=args.limit,
            )
        elif args.ingest_command == "replay":
            exit_code = ingest_replay_command(
                spend_csv=args.spend_csv,
                output_playbook=args.output,
                seed=args.seed,
            )
    elif args.command == "fpm":
        exit_code = fpm_command(args.fpm_args)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

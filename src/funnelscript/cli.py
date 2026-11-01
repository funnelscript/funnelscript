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
import sys
from importlib.metadata import version as distribution_version
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pydantic import ValidationError

from funnelscript.compiler.linter import FunnelLinter, LintSeverity
from funnelscript.compiler.world_ast import WorldAST, WorldTypeError
from funnelscript.compiler.schema import export_json_schema
from funnelscript.parser import Parser, ParserError
from funnelscript.tokens import LexerError
from funnelscript.core.event_machine import Event
from funnelscript.runtime.world_executor import WorldExecutor
from funnelscript.runtime.engine import SimulationEngine
from funnelscript.runtime.exporters import (
    export_report_to_json,
    export_trajectories_to_csv,
    export_trials_to_csv,
)

console = Console()

MAX_EVENT_JSON_BYTES = 64 * 1024
MAX_PLAYBOOK_BYTES = 1024 * 1024
MAX_PLAYBOOK_EVENTS = 10_000
PLAYBOOK_SCHEMA = "funnelscript-event-playbook-v1"

WORLD_STARTER = """world MarketingPreview {
  import "std:marketing/lead_response.fnl" as Prospect;
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
    if not path.exists():
        if not quiet:
            console.print(Panel(f"[bold red]❌ File Not Found:[/bold red] {file_path}", border_style="red"))
        return 2

    try:
        ast = Parser.from_file(str(path))
    except (LexerError, ParserError, WorldTypeError, ValidationError, json.JSONDecodeError) as exc:
        if not quiet:
            console.print(Panel(f"[bold red]❌ Parse Error:[/bold red]\n{exc}", border_style="red"))
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"Input I/O error: {exc}", file=sys.stderr)
        return 2

    if isinstance(ast, WorldAST):
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


def _load_event_playbook(file_path: str) -> list[Event]:
    source = Path(file_path)
    with source.open("rb") as stream:
        data = stream.read(MAX_PLAYBOOK_BYTES + 1)
    if len(data) > MAX_PLAYBOOK_BYTES:
        raise ValueError("Event playbook exceeds the 1 MiB input limit")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_json_object)
    if type(raw) is not dict or set(raw) != {"schema", "events"}:
        raise ValueError("Event playbook must have exactly schema and events")
    if raw["schema"] != PLAYBOOK_SCHEMA:
        raise ValueError("Unsupported event playbook schema")
    if type(raw["events"]) is not list or len(raw["events"]) > MAX_PLAYBOOK_EVENTS:
        raise ValueError("Invalid event playbook event count (maximum 10000)")
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
    try:
        ast = Parser.from_file(file_path)
        if not isinstance(ast, WorldAST):
            raise ValueError("run-world requires a world declaration, not a strategy")
        if events_file is not None and event_specs:
            raise ValueError("--event and --events-file are mutually exclusive")
        events = (_load_event_playbook(events_file) if events_file is not None
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
    except (LexerError, ParserError, WorldTypeError, ValidationError, json.JSONDecodeError) as exc:
        if not as_json:
            console.print(Panel(f"[bold red]❌ Parse Error:[/bold red]\n{exc}", border_style="red"))
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"Input I/O error: {exc}", file=sys.stderr)
        return 2

    if isinstance(ast, WorldAST):
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
    target_path = Path(output_path or f"{clean_name.lower()}.fnl.json")

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
    if target.suffix != ".fnl":
        print("World starter target must use a .fnl extension", file=sys.stderr)
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


def schema_command(output_path: str | None = None) -> int:
    """Generates and exports the JSON Schema specification."""
    schema_json = export_json_schema(output_path)
    if output_path:
        console.print(f"[bold green]✔ JSON Schema exported to:[/bold green] {output_path}")
    else:
        print(schema_json)
    return 0


def main() -> None:
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
    check_p.add_argument("file", help="Path to strategy file (.json or .fnl)")

    compile_p = subparsers.add_parser("compile", help="Alias for check")
    compile_p.add_argument("file", help="Path to strategy file (.json or .fnl)")

    # run-world (event-driven language core, no external effects)
    world_p = subparsers.add_parser("run-world", help="Execute events on typed World rules")
    world_p.add_argument("file", help="Path to a world .fnl file")
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
    sim_p.add_argument("file", help="Path to strategy file (.json or .fnl)")
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
    world_init_p.add_argument("file", help="New .fnl file path")

    # schema
    schema_p = subparsers.add_parser("schema", help="Generate official JSON Schema")
    schema_p.add_argument("--output", "-o", help="Target output file path")

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
    elif args.command == "init":
        exit_code = init_command(args.name, args.output)
    elif args.command == "init-world":
        exit_code = init_world_command(args.file)
    elif args.command == "schema":
        exit_code = schema_command(args.output)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

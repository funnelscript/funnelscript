from __future__ import annotations

import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from funnelscript.compiler.linter import FunnelLinter, LintSeverity
from funnelscript.compiler.schema import export_json_schema
from funnelscript.parser import Parser
from funnelscript.runtime.simulator import MonteCarloSimulator

console = Console()


def check_command(file_path: str) -> None:
    """Validates syntax, parses AST, and runs full semantic linting."""
    console.print(f"[bold cyan]🔍 Checking FunnelScript Strategy:[/bold cyan] {file_path}")
    try:
        ast = Parser.from_file(file_path)
    except Exception as e:
        console.print(Panel(f"[bold red]❌ Parse Error:[/bold red]\n{e}", border_style="red"))
        sys.exit(1)

    linter = FunnelLinter(ast)
    findings = linter.lint()

    if not findings:
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
        return

    # Print Findings Table
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
        console.print(Panel("[bold red]❌ Compilation Halted: One or more critical invariants violated.[/bold red]", border_style="red"))
        sys.exit(1)
    else:
        console.print(Panel("[bold yellow]⚠ Completed with advisory warnings. Invariants hold.[/bold yellow]", border_style="yellow"))


def simulate_command(file_path: str, trials: int = 100, agents: int | None = None) -> None:
    check_command(file_path)
    ast = Parser.from_file(file_path)

    console.print(
        f"\n[bold yellow]🚀 Launching Multi-Scale Monte Carlo Simulation ({trials} trials)...[/bold yellow]\n"
    )

    simulator = MonteCarloSimulator(ast)
    report = simulator.run(num_trials=trials, agents_count=agents)

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

    console.print(table)

    ruin_color = "green" if report.cash_ruin_probability < 0.05 else "red"
    cannibal_color = "yellow" if report.cannibalization_rate > 0.10 else "green"

    risk_panel = Panel(
        f"• [bold]Cash Ruin Probability P(Insolvency):[/bold] [{ruin_color}]{report.cash_ruin_probability * 100:.1f}%[/{ruin_color}] "
        f"(Risk of ad spend halt before receivables settle)\n"
        f"• [bold]Discount Cannibalization Rate:[/bold] [{cannibal_color}]{report.cannibalization_rate * 100:.1f}%[/{cannibal_color}] "
        f"(Loyal buyers harvesting abandonment discounts)\n"
        f"• [bold]Probability of Profit (ROAS >= 1.0):[/bold] [green]{report.probability_of_profit * 100:.1f}%[/green]\n"
        f"• [bold]Max Capital Loss Drawdown:[/bold] [red]${report.worst_case_drawdown:,.2f}[/red]",
        title="⚠️ Risk, Liquidity & Behavioral Telemetry",
        border_style="magenta",
    )
    console.print(risk_panel)


def schema_command(output_path: str | None = None) -> None:
    schema_json = export_json_schema(output_path)
    if output_path:
        console.print(f"[bold green]✔ JSON Schema exported to:[/bold green] {output_path}")
    else:
        print(schema_json)


def main() -> None:
    parser = argparse.ArgumentParser(description="FunnelScript DSL, Compiler & Simulation Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_p = subparsers.add_parser("check", help="Verify syntax and run graph-theoretic semantic linter")
    check_p.add_argument("file", help="Path to strategy file (.json or .fnl)")

    compile_p = subparsers.add_parser("compile", help="Alias for check")
    compile_p.add_argument("file", help="Path to strategy file (.json or .fnl)")

    sim_p = subparsers.add_parser("simulate", help="Run stochastic Monte Carlo simulations")
    sim_p.add_argument("file", help="Path to strategy file (.json or .fnl)")
    sim_p.add_argument("--trials", type=int, default=100, help="Number of Monte Carlo trials")
    sim_p.add_argument("--agents", type=int, default=None, help="Number of virtual agents per trial")

    schema_p = subparsers.add_parser("schema", help="Generate official JSON Schema")
    schema_p.add_argument("--output", "-o", help="Target output file path")

    args = parser.parse_args()
    if args.command in ("check", "compile"):
        check_command(args.file)
    elif args.command == "simulate":
        simulate_command(args.file, trials=args.trials, agents=args.agents)
    elif args.command == "schema":
        schema_command(args.output)


if __name__ == "__main__":
    main()

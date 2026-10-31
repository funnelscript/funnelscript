from __future__ import annotations

import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from funnelscript.parser import Parser
from funnelscript.runtime.simulator import MonteCarloSimulator

console = Console()


def compile_command(file_path: str) -> None:
    console.print(f"[bold cyan]🔍 Validating FunnelScript AST:[/bold cyan] {file_path}")
    try:
        ast = Parser.from_file(file_path)
        console.print(
            Panel(
                f"[bold green]✔ Static Semantic Verification Passed![/bold green]\n\n"
                f"• Strategy: [bold]{ast.strategy_name}[/bold]\n"
                f"• Audiences: {len(ast.entities.audiences)}\n"
                f"• Touchpoints: {len(ast.entities.touchpoints)}\n"
                f"• Budget Cap: ${ast.entities.budgets.total_budget:,.2f}\n"
                f"• Initial Cash: ${ast.entities.budgets.initial_cash:,.2f}\n"
                f"• Settlement Delay: {ast.entities.budgets.settlement_delay_days} days\n"
                f"• Invariant Check: Mass Conservation & Budget Positivity [green]OK[/green]",
                title="FunnelScript Compiler v1.1.0",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(Panel(f"[bold red]❌ Compilation / Invariant Failure:[/bold red]\n{e}", border_style="red"))
        sys.exit(1)


def simulate_command(file_path: str, trials: int = 100, agents: int | None = None) -> None:
    compile_command(file_path)
    ast = Parser.from_file(file_path)

    console.print(
        f"\n[bold yellow]🚀 Launching Multi-Scale Monte Carlo Simulation ({trials} trials)...[/bold yellow]\n"
    )

    simulator = MonteCarloSimulator(ast)
    report = simulator.run(num_trials=trials, agents_count=agents)

    # Output Metric Table
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

    # Risk & Liquidity Panel
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


def main() -> None:
    parser = argparse.ArgumentParser(description="FunnelScript DSL & Simulation Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_p = subparsers.add_parser("compile", help="Validate and type-check a FunnelScript strategy")
    compile_p.add_argument("file", help="Path to strategy file (.json or .fnl)")

    sim_p = subparsers.add_parser("simulate", help="Run stochastic Monte Carlo simulations")
    sim_p.add_argument("file", help="Path to strategy file (.json or .fnl)")
    sim_p.add_argument("--trials", type=int, default=100, help="Number of Monte Carlo trials")
    sim_p.add_argument("--agents", type=int, default=None, help="Number of virtual agents per trial")

    args = parser.parse_args()
    if args.command == "compile":
        compile_command(args.file)
    elif args.command == "simulate":
        simulate_command(args.file, trials=args.trials, agents=args.agents)


if __name__ == "__main__":
    main()

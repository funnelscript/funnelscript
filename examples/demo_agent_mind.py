from __future__ import annotations

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to path
src_dir = str(Path(__file__).parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from funnelscript.core.agent import Agent, PsychographicProfile

console = Console()


def run_agent_mind_experiment() -> None:
    console.print(
        Panel(
            "[bold cyan]🧠 FunnelScript Phase 1: The Agent Mind (Micro-Psychographic Simulation)[/bold cyan]\n"
            "Stepping 10 distinct consumer agents through a live marketing campaign funnel:\n"
            "• Step 1: Paid Social Ad (Creative Score: 0.85, Base CTR: 3%)\n"
            "• Step 2: Product Landing Page ($120 MSRP, 0% initial discount)\n"
            "• Step 3: Retargeting Email for Cart Abandoners (15% discount + Scarcity)",
            border_style="cyan",
        )
    )

    # Instantiate 10 diverse consumer profiles
    agents: list[tuple[str, Agent]] = [
        ("Loyal VIP 1", Agent.create_loyal_vip("vip_01")),
        ("Loyal VIP 2", Agent.create_loyal_vip("vip_02")),
        ("Impulsive 1", Agent.create_impulsive_shopper("imp_01")),
        ("Impulsive 2", Agent.create_impulsive_shopper("imp_02")),
        ("Bargain Hunter 1", Agent.create_skeptic_bargain_hunter("bh_01")),
        ("Bargain Hunter 2", Agent.create_skeptic_bargain_hunter("bh_02")),
        (
            "Frugal Saver",
            Agent(
                "frugal_01",
                PsychographicProfile(brand_affinity=0.4, price_sensitivity=0.85, fomo_index=0.2, wallet_balance=200.0),
            ),
        ),
        (
            "Cold Tech Enthusiast",
            Agent(
                "tech_01",
                PsychographicProfile(brand_affinity=0.55, price_sensitivity=0.45, fomo_index=0.75, wallet_balance=500.0),
            ),
        ),
        (
            "Under-budget Student",
            Agent(
                "student_01",
                PsychographicProfile(brand_affinity=0.7, price_sensitivity=0.95, fomo_index=0.8, wallet_balance=40.0),
            ),
        ),
        (
            "Skeptical Executive",
            Agent(
                "exec_01",
                PsychographicProfile(brand_affinity=0.3, price_sensitivity=0.2, fomo_index=0.15, wallet_balance=3000.0),
            ),
        ),
    ]

    table = Table(title="Micro-Simulation: 10 Agent Trajectories", border_style="green")
    table.add_column("Agent / Archetype", style="bold white")
    table.add_column("Psychographics (Affinity / PriceSens / FOMO)", justify="center", style="dim")
    table.add_column("Ad Click?", justify="center")
    table.add_column("Landing Page", justify="center")
    table.add_column("Retargeting", justify="center")
    table.add_column("Final State", justify="center", style="bold")

    for label, agent in agents:
        p = agent.profile
        psycho_str = f"α:{p.brand_affinity:.2f} | β:{p.price_sensitivity:.2f} | γ:{p.fomo_index:.2f}"

        # 1. Evaluate Ad
        clicked, p_click = agent.evaluate_ad_exposure(base_ctr=0.08, creative_quality=0.85)
        click_str = f"[green]Yes ({p_click*100:.1f}%)[/green]" if clicked else f"[red]No ({p_click*100:.1f}%)[/red]"

        lp_str = "-"
        retarget_str = "-"

        # 2. If clicked, evaluate landing page
        if clicked:
            bought, p_buy = agent.evaluate_purchase(base_cr=0.05, product_price=120.0, discount_percentage=0.0)
            if bought:
                lp_str = f"[bold green]Purchased ({p_buy*100:.1f}%)[/bold green]"
            elif agent.state.value == "CART_ABANDONED":
                lp_str = f"[yellow]Abandoned Cart ({p_buy*100:.1f}%)[/yellow]"
                # 3. Evaluate Retargeting for abandoners
                recovered, p_rec = agent.evaluate_retargeting(discount_percentage=15.0)
                if recovered:
                    retarget_str = f"[bold green]Recovered ({p_rec*100:.1f}%)[/bold green]"
                else:
                    retarget_str = f"[red]Ignored ({p_rec*100:.1f}%)[/red]"
            else:
                lp_str = f"[red]Bounced ({p_buy*100:.1f}%)[/red]"

        # Color-coded final state
        state_color = "green" if agent.state.value == "CONVERTED" else ("yellow" if agent.state.value == "CART_ABANDONED" else "red")
        final_state_str = f"[{state_color}]{agent.state.value}[/{state_color}]"

        table.add_row(label, psycho_str, click_str, lp_str, retarget_str, final_state_str)

    console.print(table)


if __name__ == "__main__":
    run_agent_mind_experiment()

import pytest
from pathlib import Path
from funnelscript.tokens import Lexer, TokenType
from funnelscript.parser import Parser
from funnelscript.runtime.agents import AgentPopulation, ConsumerState
from funnelscript.runtime.simulator import MonteCarloSimulator


def test_lexer_tokenizes_basic_strategy():
    code = """
    strategy TestCampaign {
        budget b1 { total = 5000; }
        audience aud1 { size = 10000; }
    }
    """
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    types = [t.type for t in tokens]
    assert TokenType.STRATEGY in types
    assert TokenType.BUDGET in types
    assert TokenType.AUDIENCE in types


def test_parser_validates_json_ast():
    example_path = Path(__file__).parent.parent / "examples" / "black_friday_2026.json"
    ast = Parser.from_file(example_path)
    assert ast.strategy_name == "ECommerce_Black_Friday_2026"
    assert len(ast.entities.touchpoints) == 3
    assert ast.entities.budgets.total_budget == 25000


def test_parser_catches_undefined_touchpoint():
    bad_json = """
    {
      "strategy_name": "Broken_Campaign",
      "entities": {
        "budgets": {"total_budget": 1000},
        "audiences": [{"id": "aud_01", "estimated_size": 1000}],
        "touchpoints": [{"id": "tp_valid", "type": "conversion_surface"}]
      },
      "logic_flow": [
        {
          "step": 1,
          "action": "TriggerTraffic",
          "source": "aud_01",
          "via": "tp_nonexistent",
          "destination": "tp_valid"
        }
      ]
    }
    """
    with pytest.raises(ValueError, match="Undefined touchpoint via 'tp_nonexistent'"):
        Parser.from_json_str(bad_json)


def test_agent_population_generation():
    example_path = Path(__file__).parent.parent / "examples" / "black_friday_2026.json"
    ast = Parser.from_file(example_path)
    pop = AgentPopulation.generate_from_audience(ast.entities.audiences[0], count=1000)
    assert pop.size == 1000
    assert len(pop.brand_affinity) == 1000
    assert (pop.state == ConsumerState.COLD).all()


def test_simulator_runs_monte_carlo():
    example_path = Path(__file__).parent.parent / "examples" / "black_friday_2026.json"
    ast = Parser.from_file(example_path)
    simulator = MonteCarloSimulator(ast)
    report = simulator.run(num_trials=20, agents_count=5000)

    assert report.trials_count == 20
    assert report.mean_roas > 0
    assert report.mean_cac > 0
    assert 0.0 <= report.cash_ruin_probability <= 1.0
    assert 0.0 <= report.cannibalization_rate <= 1.0


def test_cash_starvation_triggers_ruin_probability():
    example_path = Path(__file__).parent.parent / "examples" / "black_friday_2026.json"
    ast = Parser.from_file(example_path)
    # Severely starve initial cash and lengthen settlement delay
    ast.entities.budgets.initial_cash = 200.0
    ast.entities.budgets.settlement_delay_days = 7
    simulator = MonteCarloSimulator(ast)
    report = simulator.run(num_trials=20, agents_count=10000)

    # Cash starvation must be detected (> 80% ruin risk)
    assert report.cash_ruin_probability > 0.80


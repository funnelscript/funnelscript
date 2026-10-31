import pytest
from pathlib import Path
from funnelscript.compiler.linter import FunnelLinter, LintSeverity
from funnelscript.compiler.schema import generate_json_schema
from funnelscript.parser import Parser


@pytest.fixture
def valid_ast():
    path = Path(__file__).parent.parent / "examples" / "black_friday_2026.json"
    return Parser.from_file(path)


def test_linter_passes_valid_black_friday(valid_ast):
    linter = FunnelLinter(valid_ast)
    findings = linter.lint()
    errors = [f for f in findings if f.severity == LintSeverity.ERROR]
    assert len(errors) == 0
    assert linter.has_errors is False


def test_linter_detects_orphaned_audience(valid_ast):
    # Add an unused audience
    ast_dict = valid_ast.model_dump()
    ast_dict["entities"]["audiences"].append(
        {"id": "aud_unused", "name": "Unused Segment", "type": "cold", "estimated_size": 5000}
    )
    ast = Parser.from_json_str(valid_ast.model_dump_json())
    ast.entities.audiences.append(
        valid_ast.entities.audiences[0].model_copy(update={"id": "aud_orphan", "name": "Orphan"})
    )
    linter = FunnelLinter(ast)
    findings = linter.lint()
    codes = [f.code for f in findings]
    assert "FS201" in codes  # Orphaned audience warning


def test_linter_detects_orphaned_touchpoint(valid_ast):
    ast = Parser.from_json_str(valid_ast.model_dump_json())
    ast.entities.touchpoints.append(
        valid_ast.entities.touchpoints[0].model_copy(update={"id": "tp_unused", "platform": "TikTok"})
    )
    linter = FunnelLinter(ast)
    findings = linter.lint()
    codes = [f.code for f in findings]
    assert "FS202" in codes  # Orphaned touchpoint


def test_linter_detects_traffic_routed_to_paid_ad_destination(valid_ast):
    ast = Parser.from_json_str(valid_ast.model_dump_json())
    # Route traffic to tp_meta_ads instead of landing page
    ast.logic_flow[0]["destination"] = "tp_meta_ads"
    linter = FunnelLinter(ast)
    findings = linter.lint()
    codes = [f.code for f in findings]
    assert "FS301" in codes  # Destination is paid_traffic channel, not conversion surface
    assert linter.has_errors is True


def test_linter_detects_cyclic_attribution_loop(valid_ast):
    ast = Parser.from_json_str(valid_ast.model_dump_json())
    # Create cycle: step 1 routes to tp_landing_page, step 2 routes back to tp_meta_ads
    ast.logic_flow.append(
        {
            "step": 3,
            "action": "TriggerTraffic",
            "source": "aud_01",
            "via": "tp_landing_page",
            "destination": "tp_meta_ads",
        }
    )
    linter = FunnelLinter(ast)
    findings = linter.lint()
    codes = [f.code for f in findings]
    assert "FS402" in codes  # Cyclic attribution deadlock detected
    assert linter.has_errors is True


def test_linter_warns_on_high_settlement_delay_with_low_cash(valid_ast):
    ast = Parser.from_json_str(valid_ast.model_dump_json())
    ast.entities.budgets.settlement_delay_days = 7
    ast.entities.budgets.initial_cash = 500.0  # < 15% of $25,000
    linter = FunnelLinter(ast)
    findings = linter.lint()
    codes = [f.code for f in findings]
    assert "FS501" in codes  # Cash starvation preflight warning


def test_json_schema_generation():
    schema = generate_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "properties" in schema
    assert "entities" in schema["properties"]
    assert "logic_flow" in schema["properties"]

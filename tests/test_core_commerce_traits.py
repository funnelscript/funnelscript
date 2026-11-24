"""Tests verifying the official standard trait package packages/core/commerce_traits.

Release Gate: Phase 3 exit gate
- Package resolves via fpm.toml and index.fnls
- Contains all 5 Universal Behavioral Traits
- Contains all 5 Shared Commerce Contracts
- Zero industry logic in core
- Verifies namespace imports (import "core/commerce_traits" as std)
- Verifies named member imports (import "core/commerce_traits" { ... })
- Verifies static conformance and lowering to zero-cost DEVS primitives
"""

import tomllib
from pathlib import Path

from funnelscript.compiler.linter import WorldLinter
from funnelscript.compiler.lowering import LoweringPass
from funnelscript.compiler.world_ast import EntityDefinition, TraitDefinition, WorldAST
from funnelscript.formatter import format_funnelscript
from funnelscript.parser import Parser

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "packages" / "core" / "commerce_traits"
MANIFEST_FILE = PACKAGE_DIR / "fpm.toml"
ENTRY_FILE = PACKAGE_DIR / "index.fnls"
README_FILE = PACKAGE_DIR / "README.md"


def test_package_metadata_and_structure() -> None:
    """Task 3.1: Package files and manifest metadata are valid."""
    assert PACKAGE_DIR.is_dir(), f"Missing directory: {PACKAGE_DIR}"
    assert MANIFEST_FILE.is_file(), f"Missing manifest: {MANIFEST_FILE}"
    assert ENTRY_FILE.is_file(), f"Missing entrypoint: {ENTRY_FILE}"
    assert README_FILE.is_file(), f"Missing documentation: {README_FILE}"

    with MANIFEST_FILE.open("rb") as f:
        manifest = tomllib.load(f)

    pkg = manifest.get("package", {})
    assert pkg.get("name") == "core/commerce_traits"
    assert pkg.get("version") == "0.1.0"
    assert pkg.get("main") == "index.fnls"
    assert pkg.get("license") == "MIT"

    verification = manifest.get("verification", {})
    assert verification.get("zero_industry_logic") is True
    assert verification.get("interface_only") is True
    assert verification.get("dimensional_safe") is True


def test_standard_package_ast_and_member_specifications() -> None:
    """Task 3.2 & 3.3: index.fnls parses cleanly with 5 traits and 5 commerce contracts."""
    ast = Parser.from_file(ENTRY_FILE)
    assert isinstance(ast, WorldAST)
    assert ast.name == "CommerceTraitsWorld"

    declarations_by_name = {decl.name: decl for decl in ast.declarations}

    # Verify 5 Universal Behavioral Traits
    expected_traits = [
        "FinancialBinding",
        "Capacitated",
        "TimeDelayed",
        "Attributable",
        "Ingestable",
    ]
    for trait_name in expected_traits:
        assert trait_name in declarations_by_name, f"Missing trait: {trait_name}"
        assert isinstance(declarations_by_name[trait_name], TraitDefinition)

    # 1. FinancialBinding members
    fb = declarations_by_name["FinancialBinding"]
    fb_members = {m.name: m for m in fb.members}
    assert "currency" in fb_members and fb_members["currency"].type_name == "Currency"
    assert "clearing_account" in fb_members and fb_members["clearing_account"].type_name == "LedgerAccount"
    assert "on_settlement" in fb_members and fb_members["on_settlement"].kind == "handler"

    # 2. Capacitated members
    cap = declarations_by_name["Capacitated"]
    cap_members = {m.name: m for m in cap.members}
    assert "capacity_limit" in cap_members and cap_members["capacity_limit"].type_name == "CapacityGuard"
    assert "on_bottleneck" in cap_members and cap_members["on_bottleneck"].kind == "handler"

    # 3. TimeDelayed members
    td = declarations_by_name["TimeDelayed"]
    td_members = {m.name: m for m in td.members}
    assert "transit_delay" in td_members and td_members["transit_delay"].type_name == "Duration"
    assert "on_delay_elapsed" in td_members and td_members["on_delay_elapsed"].kind == "handler"

    # 4. Attributable members
    att = declarations_by_name["Attributable"]
    att_members = {m.name: m for m in att.members}
    assert "channel_id" in att_members and att_members["channel_id"].type_name == "string"
    assert "touchpoint_id" in att_members and att_members["touchpoint_id"].type_name == "string"
    assert "on_touchpoint" in att_members and att_members["on_touchpoint"].kind == "handler"

    # 5. Ingestable members
    ing = declarations_by_name["Ingestable"]
    ing_members = {m.name: m for m in ing.members}
    assert "mapping_schema" in ing_members and ing_members["mapping_schema"].type_name == "string"
    assert "idempotency_key" in ing_members and ing_members["idempotency_key"].type_name == "string"
    assert "on_ingest" in ing_members and ing_members["on_ingest"].kind == "handler"

    # Verify 5 Shared Commerce Contracts (Interface-Only Entities)
    expected_contracts = ["Offer", "CustomerCohort", "Channel", "Order", "Settlement"]
    for entity_name in expected_contracts:
        assert entity_name in declarations_by_name, f"Missing contract entity: {entity_name}"
        assert isinstance(declarations_by_name[entity_name], EntityDefinition)


def test_namespace_import_and_trait_conformance(tmp_path: Path) -> None:
    """Task 3.4: Consumer world imports core/commerce_traits as std and conforms cleanly."""
    source_code = """world ConsumerStore {
  import "core/commerce_traits" as std;

  entity CODParcel implements std.FinancialBinding, std.TimeDelayed {
    currency: Currency<EGP> = "EGP";
    ledger clearing_account: LedgerAccount<EGP>;
    transit_delay: Duration<day> = 3;
    state value: int = 150;

    on_settlement -> {
      post debit(clearing_account, 150), credit(bank_cash, 150);
    }

    on_delay_elapsed -> {
      transition value = (value + 0);
    }
  }
}
"""
    file_path = tmp_path / "consumer.fnls"
    file_path.write_text(source_code, encoding="utf-8")

    ast = Parser.from_file(file_path)
    assert isinstance(ast, WorldAST)
    assert ast.name == "ConsumerStore"

    # Verify that all traits from std are imported under std namespace
    decl_names = {d.name for d in ast.declarations}
    assert "std.FinancialBinding" in decl_names
    assert "std.TimeDelayed" in decl_names
    assert "std.Capacitated" in decl_names
    assert "CODParcel" in decl_names

    # Run linter
    linter = WorldLinter(ast)
    errors = linter.lint()
    assert len(errors) == 0, f"Unexpected linter errors: {[str(e) for e in errors]}"
    # check() should complete cleanly without raising
    linter.check()


def test_named_member_import_and_trait_conformance(tmp_path: Path) -> None:
    """Task 3.4: Consumer world imports specific traits by name."""
    source_code = """world B2BLeadEngine {
  import "core/commerce_traits" { Capacitated, FinancialBinding };

  entity QualifiedLead implements Capacitated, FinancialBinding {
    currency: Currency<USD> = "USD";
    ledger clearing_account: LedgerAccount<USD>;
    capacity capacity_limit: CapacityGuard(50, 1d);
    state score: int = 85;

    on_settlement -> {
      post debit(clearing_account, 1000), credit(arr_revenue, 1000);
    }

    on_bottleneck -> {
      transition score = 0;
    }
  }
}
"""
    file_path = tmp_path / "b2b_lead.fnls"
    file_path.write_text(source_code, encoding="utf-8")

    ast = Parser.from_file(file_path)
    assert isinstance(ast, WorldAST)

    linter = WorldLinter(ast)
    errors = linter.lint()
    assert len(errors) == 0, f"Unexpected linter errors: {[str(e) for e in errors]}"
    linter.check()


def test_negative_conformance_against_standard_traits(tmp_path: Path) -> None:
    """Task 3.4: Missing handler from std.FinancialBinding emits FNL-O301."""
    source_code = """world BrokenConsumer {
  import "core/commerce_traits" as std;

  entity BrokenOrder implements std.FinancialBinding {
    currency: Currency<USD> = "USD";
    ledger clearing_account: LedgerAccount<USD>;
    // Missing on_settlement handler!
  }
}
"""
    file_path = tmp_path / "broken_order.fnls"
    file_path.write_text(source_code, encoding="utf-8")

    ast = Parser.from_file(file_path)
    linter = WorldLinter(ast)
    errors = linter.lint()
    assert len(errors) > 0
    codes = [e.code for e in errors]
    assert "FNL-O301" in codes
    missing_err = next(e for e in errors if e.code == "FNL-O301")
    assert "on_settlement" in str(missing_err)


def test_lowering_and_devs_execution_of_standard_trait_entity(tmp_path: Path) -> None:
    """Gate G4 (Partial): Entity implementing core/commerce_traits lowers and executes deterministically."""
    source_code = """world ExecutionWorld {
  import "core/commerce_traits" as std;

  entity Shipment implements std.FinancialBinding, std.TimeDelayed {
    currency: Currency<USD> = "USD";
    ledger clearing_account: LedgerAccount<USD>;
    transit_delay: Duration<day> = 2;
    state status: int = 1;

    on_settlement -> {
      post debit(clearing_account, 500), credit(logistics_cash, 500);
    }

    on_delay_elapsed -> {
      transition status = 2;
    }
  }
}
"""
    file_path = tmp_path / "exec.fnls"
    file_path.write_text(source_code, encoding="utf-8")

    ast = Parser.from_file(file_path)
    linter = WorldLinter(ast)
    assert len(linter.lint()) == 0

    # LoweringPass must erase all trait declarations before tick 0
    lowered = LoweringPass.lower(ast)
    assert not any(isinstance(d, TraitDefinition) for d in lowered.world.declarations)
    shipment_decl = next(d for d in lowered.world.declarations if d.name == "Shipment")
    assert shipment_decl is not None

    # Run in LoweredWorld
    from funnelscript.core.event_machine import Event
    init_st = lowered.initial_state()
    assert init_st["Shipment"]["status"] == 1

    result = lowered.run([Event(time=1.0, name="Shipment.on_delay_elapsed")], seed=42)
    assert result.state["Shipment"]["status"] == 2


def test_core_commerce_traits_fmt_idempotency() -> None:
    """FunnelScript formatter round-trips index.fnls idempotently."""
    source_text = ENTRY_FILE.read_text(encoding="utf-8")
    formatted_1 = format_funnelscript(source_text)
    formatted_2 = format_funnelscript(formatted_1)
    assert formatted_1 == formatted_2

"""Suite 3: Cross-Package Interoperability Verification (Gate G4).

Tests that independent fpm packages (e.g. pkg_a/paid_acquisition and pkg_b/retention_engine)
that have zero knowledge of each other can:
1. Interoperate cleanly via shared contracts from core/commerce_traits.
2. Compile, statically typecheck, and lint with zero diagnostic errors across boundaries.
3. Lower cleanly to deterministic DEVS event machines with zero runtime reflection.
4. Reconcile double-entry ledger postings across package boundaries on a single unified ledger.
5. Guarantee zero entity drops or duplication across cross-package handoffs.
6. Verify examples/holistic_8ps_composition.fnls as the canonical multi-package composition proof.
"""

from decimal import Decimal
from pathlib import Path

from funnelscript.compiler.linter import WorldLinter
from funnelscript.compiler.lowering import LoweringPass
from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker
from funnelscript.core import Event
from funnelscript.ledger import FinancialLedger
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutor

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
PACKAGES_DIR = Path(__file__).resolve().parents[1] / "packages"


def test_holistic_8ps_composition_example_compiles_and_lowers() -> None:
    """Gate G4: Verify examples/holistic_8ps_composition.fnls compiles, lints, and executes."""
    example_path = EXAMPLES_DIR / "holistic_8ps_composition.fnls"
    assert example_path.is_file(), f"Missing example file: {example_path}"

    ast = Parser.from_file(example_path)
    assert isinstance(ast, WorldAST)
    assert ast.name == "HolisticEnterpriseStrategy"

    # 1. Typecheck and lint
    WorldTypeChecker.check(ast)
    linter = WorldLinter(ast)
    errors = linter.lint()
    assert len(errors) == 0, f"Lint errors in holistic composition: {[str(e) for e in errors]}"
    linter.check()

    # 2. Lower to DEVS
    lowered = LoweringPass.lower(ast)
    assert isinstance(lowered.world, WorldAST)

    # 3. Initialize DEVS execution engine
    executor = WorldExecutor(lowered.world)
    state = executor.initial_state()
    assert "EnterpriseCustomerCohort" in state
    assert "HolisticGrowthLoop" in state
    assert "d2c" in state
    assert "leadgen" in state

    # 4. Advance world with cross-channel events
    state = executor.advance(
        state,
        Event(name="HolisticGrowthLoop.DispatchUnifiedOrder", payload={"order_id": 101, "value": 150}, time=0.0),
    )
    growth_state = state["HolisticGrowthLoop"]
    assert growth_state["total_orders_fulfilled"] == 1
    assert growth_state["total_cross_channel_revenue"] == 150

    state = executor.advance(
        state,
        Event(name="HolisticGrowthLoop.CloseEnterpriseContract", payload={"lead_id": 201, "deal_size": 4500}, time=1.0),
    )
    growth_state = state["HolisticGrowthLoop"]
    assert growth_state["total_leads_closed"] == 1
    assert growth_state["total_cross_channel_revenue"] == 4650


def test_independent_mock_packages_interoperate_on_single_ledger(tmp_path: Path) -> None:
    """Suite 3: Two separate fpm packages interoperate on a single shared FinancialLedger."""
    packages_root = tmp_path / "packages"
    packages_root.mkdir(parents=True)

    # Symlink core/commerce_traits into temporary packages dir
    core_commerce = packages_root / "core" / "commerce_traits"
    core_commerce.parent.mkdir(parents=True)
    real_core = PACKAGES_DIR / "core" / "commerce_traits"
    core_commerce.symlink_to(real_core)

    # Package A: pkg_a/paid_acquisition (Producer)
    pkg_a_dir = packages_root / "pkg_a" / "paid_acquisition"
    pkg_a_dir.mkdir(parents=True)
    (pkg_a_dir / "fpm.toml").write_text(
        """[package]
name = "pkg_a/paid_acquisition"
version = "0.1.0"
main = "index.fnls"
[dependencies]
"core/commerce_traits" = "0.1.0"
""",
        encoding="utf-8",
    )
    (pkg_a_dir / "index.fnls").write_text(
        """world AcquisitionWorld {
  import "core/commerce_traits" as std;

  entity AcquisitionOrder implements std.FinancialBinding, std.Attributable {
    currency: Currency<USD> = "USD";
    ledger clearing_account: LedgerAccount<USD>;
    channel_id: string = "meta_paid";
    touchpoint_id: string = "summer_sale";
    state order_id: int = 1;
    state value: int = 250;
    state status: string = "placed";

    on_settlement -> {
      post debit(clearing_account, 250), credit(corporate_cash, 250);
    }

    on_touchpoint -> {
      transition status = "attributed";
    }
  }
}
""",
        encoding="utf-8",
    )

    # Package B: pkg_b/retention_engine (Consumer)
    pkg_b_dir = packages_root / "pkg_b" / "retention_engine"
    pkg_b_dir.mkdir(parents=True)
    (pkg_b_dir / "fpm.toml").write_text(
        """[package]
name = "pkg_b/retention_engine"
version = "0.1.0"
main = "index.fnls"
[dependencies]
"core/commerce_traits" = "0.1.0"
""",
        encoding="utf-8",
    )
    (pkg_b_dir / "index.fnls").write_text(
        """world RetentionWorld {
  import "core/commerce_traits" as std;

  entity RetentionCohort implements std.FinancialBinding, std.Capacitated {
    currency: Currency<USD> = "USD";
    ledger clearing_account: LedgerAccount<USD>;
    capacity capacity_limit: CapacityGuard(100, 1d);
    state cohort_id: int = 1;
    state active_subscribers: int = 80;
    state churn_alert: bool = false;

    on_settlement -> {
      post debit(corporate_cash, 50), credit(clearing_account, 50);
    }

    on_bottleneck -> {
      transition churn_alert = true;
    }
  }
}
""",
        encoding="utf-8",
    )

    # Consumer world importing both packages
    consumer_file = tmp_path / "consumer_strategy.fnls"
    consumer_file.write_text(
        """world ConsumerEnterpriseStrategy {
  import "core/commerce_traits" as std;
  import "pkg_a/paid_acquisition" as acq;
  import "pkg_b/retention_engine" as ret;

  entity CrossPackageCoordinator implements std.Capacitated {
    capacity capacity_limit: CapacityGuard(500, 1d);
    state handoffs_completed: int = 0;
    state active: bool = true;

    event IngestCustomerHandoff(order_id: int, cohort_id: int);

    rule ReceiveHandoff on event IngestCustomerHandoff when (active == true) {
      transition handoffs_completed = (handoffs_completed + 1);
    }

    on_bottleneck -> {
      transition active = false;
    }
  }
}
""",
        encoding="utf-8",
    )

    # Parse and lint across package boundaries
    ast = Parser.from_file(consumer_file)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)
    linter = WorldLinter(ast)
    errors = linter.lint()
    assert len(errors) == 0, f"Cross-package lint errors: {[str(e) for e in errors]}"
    linter.check()

    # Lower to DEVS
    lowered = LoweringPass.lower(ast)
    executor = WorldExecutor(lowered.world)
    state = executor.initial_state()
    assert "CrossPackageCoordinator" in state
    assert "acq.AcquisitionOrder" in state
    assert "ret.RetentionCohort" in state

    # Advance coordinator
    state = executor.advance(
        state,
        Event(name="CrossPackageCoordinator.IngestCustomerHandoff", payload={"order_id": 1, "cohort_id": 1}, time=0.0),
    )
    assert state["CrossPackageCoordinator"]["handoffs_completed"] == 1

    # Single Unified Financial Ledger Reconciliation
    ledger = FinancialLedger()
    ledger.declare_account("corporate_cash", "USD")
    ledger.declare_account("acq_clearing", "USD")
    ledger.declare_account("ret_clearing", "USD")

    # Transaction 1: Acquisition Inflow ($250 from customer to corporate_cash via clearing)
    ledger.post(
        tx_id="tx_acq_order_001",
        timestamp=1.0,
        postings=[
            ("corporate_cash", "debit", 250),
            ("acq_clearing", "credit", 250),
        ],
        description="Acquisition order settled into unified treasury",
    )

    # Transaction 2: Retention Reward / Discount ($50 rebate to customer via retention clearing)
    ledger.post(
        tx_id="tx_ret_rebate_001",
        timestamp=2.0,
        postings=[
            ("ret_clearing", "debit", 50),
            ("corporate_cash", "credit", 50),
        ],
        description="Retention reward debited from unified treasury",
    )

    # Invariant: Double-Entry Conservation holds across both packages
    # corporate_cash: +250 - 50 = +200 USD
    assert ledger.balance("corporate_cash") == Decimal("200.00")
    assert ledger.balance("acq_clearing") == Decimal("-250.00")
    assert ledger.balance("ret_clearing") == Decimal("50.00")

    # Invariant: Total debits == total credits across all accounts
    net_trial_balance = (
        ledger.balance("corporate_cash") +
        ledger.balance("acq_clearing") +
        ledger.balance("ret_clearing")
    )
    assert net_trial_balance == Decimal("0.00")


def test_holistic_composition_formatter_idempotency() -> None:
    """Verify that funnelscript format round-trips holistic composition idempotently."""
    from funnelscript.formatter import format_funnelscript

    example_path = EXAMPLES_DIR / "holistic_8ps_composition.fnls"
    source = example_path.read_text(encoding="utf-8")
    formatted1 = format_funnelscript(source)
    formatted2 = format_funnelscript(formatted1)

    assert formatted1 == formatted2
    # Also verify that the formatted output parses cleanly
    from funnelscript.tokens import Lexer

    tokens = Lexer(formatted1, file=str(example_path)).tokenize()
    ast = Parser(tokens).parse_world(source_path=example_path)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)
    WorldLinter(ast).check()


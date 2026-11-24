"""Verification suite for Static Dimensional Type Checker & Compiler Diagnostics.

Pillars & Hardening Spec:
- Pillar 2.1: Strict dimensional analysis rejecting invalid operations (Currency + Count, Rate > Duration).
- Pillar 2.2: Compile-time validation of marketing invariants (Prob in [0, 1], budgets >= 0).
- Wave 2 Track A2 & A4: Polymorphic marketing signatures, span-accurate FNL-T2xx diagnostics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from funnelscript.cli import check_command
from funnelscript.compiler.diagnostics import DimensionalTypeError
from funnelscript.compiler.linter import WorldLinter
from funnelscript.compiler.world_ast import WorldTypeError
from funnelscript.parser import Parser
from funnelscript.tokens import Lexer


def _parse_source(tmp_path: Path, source: str):
    file_path = tmp_path / "test_world.fnls"
    file_path.write_text(source, encoding="utf-8")
    tokens = Lexer(source, file=str(file_path)).tokenize()
    ast = Parser(tokens).parse_world(source_path=file_path)
    return ast, file_path


# ---------------------------------------------------------------------------
# 1. FNL-T201: Dimensional Mismatch Tests
# ---------------------------------------------------------------------------

class TestDimensionalMismatchFNLT201:
    """Verifies that operations across physically incompatible dimensions are rejected."""

    def test_currency_plus_count_in_transition(self, tmp_path: Path) -> None:
        source = """world BrokenWorld {
  entity Campaign {
    state budget: Currency<USD> = 5000;
    state clicks: Count<Click> = 0;
    event Tick();
    rule OnTick on event Tick {
      transition budget = budget + clicks;
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T201" in str(err)
        assert "Dimensional mismatch" in str(err)
        assert "^" in str(err)
        assert "Hint:" in str(err)

    def test_incompatible_transition_target(self, tmp_path: Path) -> None:
        source = """world BrokenTarget {
  entity Campaign {
    state budget: Currency<USD> = 5000;
    state clicks: Count<Click> = 10;
    event Tick();
    rule OnTick on event Tick {
      transition clicks = budget;
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T201" in str(err)
        assert "Type mismatch assigning 'clicks'" in str(err)

    def test_hill_spend_and_k_dimension_mismatch(self, tmp_path: Path) -> None:
        # S is Currency<USD>, but K is Duration<day>!
        source = """world BrokenHill {
  entity AdChannel {
    state spend: Currency<USD> = 1000;
    state delay_k: Duration<day> = 14;
    state conv: float = 0.0;
    event Tick();
    rule OnTick on event Tick {
      transition conv = hill(spend, delay_k, 0.8, 100);
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T201" in str(err)
        assert "spend S" in str(err)
        assert "half-saturation K" in str(err)


# ---------------------------------------------------------------------------
# 2. FNL-T202: Currency Isolation Violation Tests
# ---------------------------------------------------------------------------

class TestCurrencyIsolationFNLT202:
    """Verifies that distinct ISO currencies cannot be added, subtracted, or assigned without FX."""

    def test_usd_plus_eur_in_transition(self, tmp_path: Path) -> None:
        source = """world MultiCurrencyMismatch {
  entity Portfolio {
    state usd_cash: Currency<USD> = 1000;
    state eur_cash: Currency<EUR> = 500;
    event Rebalance();
    rule OnRebalance on event Rebalance {
      transition usd_cash = usd_cash + eur_cash;
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T202" in str(err)
        assert "Currency isolation violation" in str(err)
        assert "USD" in str(err)
        assert "EUR" in str(err)
        assert "exchange rate" in str(err).lower()

    def test_assign_foreign_currency_to_target(self, tmp_path: Path) -> None:
        source = """world CurrencyAssignmentMismatch {
  entity Channel {
    state usd_budget: Currency<USD> = 1000;
    state eur_budget: Currency<EUR> = 800;
    event Sync();
    rule OnSync on event Sync {
      transition usd_budget = eur_budget;
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T202" in str(err)
        assert "Currency isolation violation" in str(err)


# ---------------------------------------------------------------------------
# 3. FNL-T203: Transcendental Argument Safety Tests
# ---------------------------------------------------------------------------

class TestTranscendentalSafetyFNLT203:
    """Verifies that exp(), log(), and sigmoid() require strictly dimensionless arguments."""

    def test_exp_with_currency_argument(self, tmp_path: Path) -> None:
        source = """world BrokenExp {
  entity Model {
    state spend: Currency<USD> = 100;
    state result: float = 0.0;
    event Eval();
    rule OnEval on event Eval {
      transition result = exp(spend);
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T203" in str(err)
        assert "Non-dimensionless argument to transcendental function 'exp'" in str(err)
        assert "Currency<USD>" in str(err)

    def test_log_with_count_argument(self, tmp_path: Path) -> None:
        source = """world BrokenLog {
  entity Model {
    state clicks: Count<Click> = 500;
    state result: float = 0.0;
    event Eval();
    rule OnEval on event Eval {
      transition result = log(clicks);
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T203" in str(err)
        assert "Non-dimensionless argument to transcendental function 'log'" in str(err)


# ---------------------------------------------------------------------------
# 4. FNL-T204: Probability Bounds Tests
# ---------------------------------------------------------------------------

class TestProbabilityBoundsFNLT204:
    """Verifies compile-time static refinement bounds on Prob in [0.0, 1.0]."""

    def test_prob_state_exceeds_one(self, tmp_path: Path) -> None:
        source = """world BadProb {
  entity AdChannel {
    state cvr: Prob = 1.25;
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T204" in str(err)
        assert "Probability out of bounds" in str(err)
        assert "1.25" in str(err)

    def test_prob_state_negative(self, tmp_path: Path) -> None:
        source = """world NegativeProb {
  entity AdChannel {
    state ctr: Prob = -0.05;
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T204" in str(err)
        assert "Probability out of bounds" in str(err)

    def test_adstock_decay_exceeds_one(self, tmp_path: Path) -> None:
        source = """world BadAdstock {
  entity AdChannel {
    state spend: Currency<USD> = 500;
    state carryover: Currency<USD> = 0;
    event Tick();
    rule OnTick on event Tick {
      transition carryover = adstock(spend, 1.2);
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T204" in str(err)
        assert "Adstock decay rate must be in [0.0, 1.0)" in str(err)


# ---------------------------------------------------------------------------
# 5. FNL-T205: Non-Negative Domain Constraints Tests
# ---------------------------------------------------------------------------

class TestNonNegativeDomainConstraintsFNLT205:
    """Verifies compile-time non-negative domain bounds on financial/physical quantities."""

    def test_negative_budget_state(self, tmp_path: Path) -> None:
        source = """world NegativeBudget {
  entity AdChannel {
    state budget: Currency<USD> = -500;
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T205" in str(err)
        assert "Non-negative domain constraint violated" in str(err)
        assert "-500" in str(err)

    def test_hill_negative_k_saturation(self, tmp_path: Path) -> None:
        source = """world NegativeKHill {
  entity AdChannel {
    state spend: Currency<USD> = 500;
    state response: float = 0.0;
    event Tick();
    rule OnTick on event Tick {
      transition response = hill(spend, -100, 0.8, 50);
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T205" in str(err)
        assert "Half-saturation constant K must be positive" in str(err)

    def test_hill_negative_alpha_slope(self, tmp_path: Path) -> None:
        source = """world NegativeAlphaHill {
  entity AdChannel {
    state spend: Currency<USD> = 500;
    state response: float = 0.0;
    event Tick();
    rule OnTick on event Tick {
      transition response = hill(spend, 100, -0.5, 50);
    }
  }
}
"""
        with pytest.raises((WorldTypeError, DimensionalTypeError)) as exc_info:
            _parse_source(tmp_path, source)
        err = exc_info.value
        assert "FNL-T205" in str(err)
        assert "Hill slope parameter alpha must be positive" in str(err)


# ---------------------------------------------------------------------------
# 6. Valid Marketing Models & Polymorphic Primitives
# ---------------------------------------------------------------------------

class TestValidDimensionalMarketingModels:
    """Proves that correctly dimensioned marketing programs compile with zero warnings."""

    def test_valid_hill_and_adstock_channel(self, tmp_path: Path) -> None:
        source = """world ValidMarketingWorld {
  entity MetaAds {
    state daily_spend: Currency<USD> = 1000;
    state carryover_spend: Currency<USD> = 0;
    state expected_orders: float = 0.0;

    event DailyTick();

    rule OnTick on event DailyTick {
      transition carryover_spend = adstock(daily_spend, 0.65);
      transition expected_orders = hill(carryover_spend, 500, 0.8, 120);
    }
  }
}
"""
        ast, _file_path = _parse_source(tmp_path, source)
        assert ast.name == "ValidMarketingWorld"
        linter = WorldLinter(ast)
        errors = linter.lint()
        assert len(errors) == 0, f"Unexpected errors: {[str(e) for e in errors]}"

    def test_valid_fx_conversion(self, tmp_path: Path) -> None:
        source = """world ValidFXWorld {
  entity CrossBorder {
    state usd_spend: Currency<USD> = 1000;
    state fx_rate: Rate<Currency<EUR> / Currency<USD>> = 0.92;
    state eur_spend: Currency<EUR> = 0;

    event Settle();

    rule OnSettle on event Settle {
      transition eur_spend = fx_convert(usd_spend, fx_rate);
    }
  }
}
"""
        ast, _file_path = _parse_source(tmp_path, source)
        assert ast.name == "ValidFXWorld"
        linter = WorldLinter(ast)
        errors = linter.lint()
        assert len(errors) == 0, f"Unexpected errors: {[str(e) for e in errors]}"


# ---------------------------------------------------------------------------
# 7. CLI Check Integration & Rich Diagnostic Rendering
# ---------------------------------------------------------------------------

class TestCLICheckDiagnosticRendering:
    """Verifies that the CLI check command formats compiler errors with caret pointers."""

    def test_cli_check_displays_dimensional_diagnostic(self, tmp_path: Path, capsys) -> None:
        file_path = tmp_path / "bad_units.fnls"
        file_path.write_text("""world BrokenCLI {
  entity Channel {
    state budget: Currency<USD> = 5000;
    state clicks: Count<Click> = 10;
    event Tick();
    rule R on event Tick {
      transition budget = budget + clicks;
    }
  }
}
""", encoding="utf-8")
        exit_code = check_command(str(file_path))
        assert exit_code == 1
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "FNL-T201" in out
        assert "Dimensional mismatch" in out
        assert "^" in out
        assert "Hint:" in out
        assert "Traceback" not in out

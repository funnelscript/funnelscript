"""Verification suite for Algebraic Dimensional Type System and Marketing Units.

Pillars & Hardening Spec:
- Pillar 2.1: Dimensional & Unit Checking (immutable exponent map over orthogonal bases).
- Pillar 2.2: Domain Constraint Verification (refinement bounds and physical invariants).
- Wave 2 Track A1 & A3: Group-algebra laws and Hypothesis property verification.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from funnelscript.compiler.dimensions import (
    Dimension,
    DimensionParser,
)

# ---------------------------------------------------------------------------
# 1. Base Dimensions & Factory Unit Tests
# ---------------------------------------------------------------------------

class TestBaseDimensions:
    """Verifies orthogonal base dimensions and factory constructors."""

    def test_dimensionless_and_scalar(self) -> None:
        d = Dimension.dimensionless()
        assert d.is_dimensionless()
        assert not d.currencies
        assert not d.entities
        assert d.time_exp == 0
        assert str(d) == "Dimensionless"

        s = Dimension.scalar()
        assert s.is_dimensionless()
        assert str(s) == "Scalar"

        prob = Dimension.prob()
        assert prob.is_prob()
        assert prob.is_dimensionless()
        assert str(prob) == "Prob"

        ratio = Dimension.ratio()
        assert ratio.is_dimensionless()
        assert str(ratio) == "Ratio"

    def test_currency_base(self) -> None:
        usd = Dimension.currency("USD")
        assert usd.is_currency()
        assert usd.get_currency_code() == "USD"
        assert str(usd) == "Currency<USD>"

        eur = Dimension.currency("EUR")
        assert eur.is_currency()
        assert eur.get_currency_code() == "EUR"
        assert str(eur) == "Currency<EUR>"

        generic = Dimension.currency()
        assert generic.is_currency()
        assert generic.get_currency_code() is None
        assert str(generic) == "Currency"

    def test_duration_and_time_scales(self) -> None:
        day = Dimension.duration("day")
        assert day.is_duration()
        assert day.time_exp == 1
        assert day.time_unit == "day"
        assert str(day) == "Duration<day>"

        hour = Dimension.duration("hour")
        assert hour.is_duration()
        assert hour.time_unit == "hour"
        assert str(hour) == "Duration<hour>"

        # Rational scaling factor
        assert math.isclose(day.scale_to("hour"), 24.0)
        assert math.isclose(hour.scale_to("day"), 1.0 / 24.0)
        assert math.isclose(day.scale_to("sec"), 86400.0)

        # Time normalization
        norm_hour = day.normalize_time("hour")
        assert norm_hour.time_unit == "hour"
        assert math.isclose(norm_hour.factor, 24.0)

    def test_nominal_entity_counts(self) -> None:
        click = Dimension.count("Click")
        assert click.is_count()
        assert str(click) == "Count<Click>"

        lead = Dimension.count("Lead")
        assert lead.is_count()
        assert str(lead) == "Count<Lead>"

        order = Dimension.count("Order")
        assert order.is_count()
        assert str(order) == "Count<Order>"

        customer = Dimension.count("Customer")
        assert customer.is_count()
        assert str(customer) == "Count<Customer>"

        impression = Dimension.count("Impression")
        assert impression.is_count()
        assert str(impression) == "Count<Impression>"


# ---------------------------------------------------------------------------
# 2. Marketing Aliases Tests
# ---------------------------------------------------------------------------

class TestMarketingAliases:
    """Verifies that marketing abbreviations desugar to exact dimensional algebra."""

    def test_cpc_alias(self) -> None:
        # CPC = Currency<USD> / Count<Click>
        cpc = Dimension.cpc("USD")
        expected = Dimension.currency("USD") / Dimension.count("Click")
        assert cpc == expected
        assert cpc.kind == "Rate"
        assert "Rate<Currency<USD> / Count<Click>>" in str(cpc)

    def test_cac_alias(self) -> None:
        # CAC = Currency<USD> / Count<Customer>
        cac = Dimension.cac("USD")
        expected = Dimension.currency("USD") / Dimension.count("Customer")
        assert cac == expected
        assert cac.kind == "Rate"
        assert "Rate<Currency<USD> / Count<Customer>>" in str(cac)

    def test_cpm_alias(self) -> None:
        # CPM = Currency<USD> / (1000 * Impression)
        cpm = Dimension.cpm("USD")
        assert cpm.factor == 1000.0
        assert cpm.get_currency_code() == "USD"
        assert ("Impression", -1) in cpm.entities

    def test_ctr_alias(self) -> None:
        # CTR = Click / Impression
        ctr = Dimension.ctr()
        expected = Dimension.count("Click") / Dimension.count("Impression")
        assert ctr == expected
        assert "Rate<Count<Click> / Count<Impression>>" in str(ctr)

    def test_cvr_alias(self) -> None:
        # CVR = Order / Click
        cvr = Dimension.cvr()
        expected = Dimension.count("Order") / Dimension.count("Click")
        assert cvr == expected
        assert "Rate<Count<Order> / Count<Click>>" in str(cvr)

    def test_spend_rate_alias(self) -> None:
        # SpendRate = Currency / Duration
        sr = Dimension.spend_rate("USD", "day")
        expected = Dimension.currency("USD") / Dimension.duration("day")
        assert sr == expected
        assert "Rate<Currency<USD> / Duration<day>>" in str(sr)

    def test_roas_alias(self) -> None:
        # ROAS = Revenue / AdSpend = Dimensionless Ratio
        roas = Dimension.roas()
        assert roas.is_dimensionless()
        assert str(roas) == "Ratio"


# ---------------------------------------------------------------------------
# 3. Currency Isolation & Compatibility Tests
# ---------------------------------------------------------------------------

class TestCurrencyIsolation:
    """Verifies that different currencies cannot be directly combined."""

    def test_distinct_currencies_are_incompatible(self) -> None:
        usd = Dimension.currency("USD")
        eur = Dimension.currency("EUR")
        egp = Dimension.currency("EGP")

        assert not usd.is_compatible_with(eur)
        assert not usd.is_compatible_with(egp)
        assert not eur.is_compatible_with(egp)

    def test_identical_currencies_are_compatible(self) -> None:
        usd1 = Dimension.currency("USD")
        usd2 = Dimension.currency("USD")
        assert usd1.is_compatible_with(usd2)

    def test_generic_wildcard_currency(self) -> None:
        generic = Dimension.currency("*")
        usd = Dimension.currency("USD")
        assert generic.is_compatible_with(usd)
        assert usd.is_compatible_with(generic)

    def test_fx_conversion_derivation(self) -> None:
        # FX Rate: EUR / USD
        fx_rate = Dimension.currency("EUR") / Dimension.currency("USD")
        usd_amount = Dimension.currency("USD")
        # Converting: USD * (EUR / USD) -> EUR
        eur_result = usd_amount * fx_rate
        assert eur_result.is_compatible_with(Dimension.currency("EUR"))
        assert eur_result.get_currency_code() == "EUR"


# ---------------------------------------------------------------------------
# 4. Arithmetic & Group Algebra Operations
# ---------------------------------------------------------------------------

class TestDimensionGroupAlgebra:
    """Tests group-algebra properties: multiplication, division, inversion, power."""

    def test_multiplication_adds_exponents(self) -> None:
        cpc = Dimension.cpc("USD")
        clicks = Dimension.count("Click")
        # CPC * Clicks = Currency<USD>
        total_spend = cpc * clicks
        assert total_spend.is_compatible_with(Dimension.currency("USD"))
        assert total_spend.get_currency_code() == "USD"
        assert not total_spend.entities

    def test_division_cancels_units(self) -> None:
        spend = Dimension.currency("USD")
        clicks = Dimension.count("Click")
        derived_cpc = spend / clicks
        assert derived_cpc == Dimension.cpc("USD")

    def test_inverse_property(self) -> None:
        clicks = Dimension.count("Click")
        inv_clicks = clicks.inverse()
        assert inv_clicks.entities == (("Click", -1),)
        # clicks * inv_clicks == 1 (Dimensionless)
        identity = clicks * inv_clicks
        assert identity.is_dimensionless()

    def test_integer_powers(self) -> None:
        meters = Dimension.count("Meter")
        meters_squared = meters ** 2
        assert meters_squared.entities == (("Meter", 2),)
        meters_cubed = meters ** 3
        assert meters_cubed.entities == (("Meter", 3),)
        meters_zero = meters ** 0
        assert meters_zero.is_dimensionless()

        with pytest.raises(TypeError):
            _ = meters ** 2.5  # Non-integer powers rejected


# ---------------------------------------------------------------------------
# 5. DimensionParser Tests
# ---------------------------------------------------------------------------

class TestDimensionParser:
    """Verifies that the DSL type parser correctly interprets type annotations."""

    @pytest.mark.parametrize(
        ("expr", "expected_kind"),
        [
            ("Currency<USD>", "Currency"),
            ("Currency<EUR>", "Currency"),
            ("Duration<day>", "Duration"),
            ("Duration<hour>", "Duration"),
            ("Count<Click>", "Count"),
            ("Count<Lead>", "Count"),
            ("Prob", "Prob"),
            ("Scalar", "Scalar"),
            ("Ratio", "Ratio"),
            ("CPC", "Rate"),
            ("CAC", "Rate"),
            ("CPM", "Rate"),
            ("CTR", "Rate"),
            ("CVR", "Rate"),
            ("ROAS", "Ratio"),
            ("SpendRate", "Rate"),
            ("Pool<Count<Lead>>", "Count"),
            ("Flow<Currency<USD>>", "Currency"),
            ("LedgerAccount<USD>", "Currency"),
            ("int", "Scalar"),
            ("float", "Scalar"),
            ("bool", "Bool"),
            ("string", "String"),
        ],
    )
    def test_parser_standard_types(self, expr: str, expected_kind: str) -> None:
        dim = DimensionParser.parse(expr)
        assert dim.kind == expected_kind

    def test_parser_nested_rate(self) -> None:
        dim = DimensionParser.parse("Rate<Currency<USD> / Duration<day>>")
        assert dim.is_compatible_with(Dimension.spend_rate("USD", "day"))


# ---------------------------------------------------------------------------
# 6. Hypothesis Property-Based Invariant Verification
# ---------------------------------------------------------------------------

# Strategy for generating valid random dimensions
_currencies = st.sampled_from(["USD", "EUR", "EGP", "GBP"])
_entities = st.sampled_from(["Click", "Lead", "Order", "Customer", "Impression"])
_exponents = st.integers(min_value=-3, max_value=3)


@st.composite
def random_dimension(draw):
    currencies = []
    if draw(st.booleans()):
        curr = draw(_currencies)
        exp = draw(st.integers(min_value=-2, max_value=2))
        if exp != 0:
            currencies.append((curr, exp))

    entities = []
    if draw(st.booleans()):
        ent = draw(_entities)
        exp = draw(st.integers(min_value=-2, max_value=2))
        if exp != 0:
            entities.append((ent, exp))

    time_exp = draw(st.integers(min_value=-2, max_value=2)) if draw(st.booleans()) else 0
    time_unit = "day"

    c_tup = tuple(sorted(currencies))
    e_tup = tuple(sorted(entities))
    derived_kind = Dimension._derive_kind(c_tup, time_exp, e_tup)

    return Dimension(
        currencies=c_tup,
        time_exp=time_exp,
        time_unit=time_unit,
        entities=e_tup,
        factor=1.0,
        kind=derived_kind,
    )


class TestGroupAlgebraHypothesisAxioms:
    """Proves group-algebra mathematical laws across randomized dimensions."""

    @given(a=random_dimension(), b=random_dimension())
    def test_commutativity_law(self, a: Dimension, b: Dimension) -> None:
        """Commutativity: a * b == b * a."""
        assert (a * b) == (b * a)

    @given(a=random_dimension(), b=random_dimension(), c=random_dimension())
    def test_associativity_law(self, a: Dimension, b: Dimension, c: Dimension) -> None:
        """Associativity: (a * b) * c == a * (b * c)."""
        left = (a * b) * c
        right = a * (b * c)
        assert left == right

    @given(a=random_dimension())
    def test_identity_element_law(self, a: Dimension) -> None:
        """Identity: a * 1 == a."""
        identity = Dimension.dimensionless()
        assert (a * identity) == a
        assert (identity * a) == a

    @given(a=random_dimension())
    def test_inverse_cancellation_law(self, a: Dimension) -> None:
        """Inverse: a * a^-1 == 1 (Dimensionless)."""
        inv_a = a.inverse()
        prod = a * inv_a
        assert prod.is_dimensionless()

    @given(a=random_dimension())
    def test_division_reversibility_law(self, a: Dimension) -> None:
        """Reversibility: a / a == 1."""
        div_result = a / a
        assert div_result.is_dimensionless()

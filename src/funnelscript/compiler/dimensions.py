"""Algebraic dimensional type system and unit verification for FunnelScript.

Research & Governance:
- Spec: TYPING_AND_CONNECTORS_99_ROADMAP.md (Part A: Dimensional Typing)
- Spec: spec/meta-ontology-traits-v1.md & spec/grammar.ebnf
- Pillars: Pillar 2.1 (Dimensional Analysis) & 2.2 (Domain Constraint Verification)

Implements an immutable group-algebraic Dimension vector:
  D = M^e_m * T^e_t * E_1^e_1 * ... * E_k^e_k
supporting orthogonal currencies, rational time scales, nominal entity counts,
and derived marketing aliases (CPC, CAC, CPM, CTR, CVR, ROAS, SpendRate).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

_ISO_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

# Exact rational scale factors relative to seconds
TIME_SCALE_SECONDS: dict[str, float] = {
    "s": 1.0,
    "sec": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "m": 60.0,
    "min": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
    "h": 3600.0,
    "hr": 3600.0,
    "hour": 3600.0,
    "hours": 3600.0,
    "d": 86400.0,
    "day": 86400.0,
    "days": 86400.0,
    "w": 604800.0,
    "wk": 604800.0,
    "week": 604800.0,
    "weeks": 604800.0,
    "month": 2592000.0,  # 30-day accounting month
    "months": 2592000.0,
}


@dataclass(frozen=True, slots=True)
class Dimension:
    """An immutable, algebraic dimensional vector over canonical marketing bases.

    - currencies: tuple of (iso_code, exponent) sorted by code, e.g. (("USD", 1),)
    - time_exp: integer exponent of time
    - time_unit: canonical unit name (default "day")
    - entities: tuple of (entity_tag, exponent) sorted by tag, e.g. (("Click", -1), ("Order", 1))
    - factor: numeric scalar factor (e.g. 1000 for CPM)
    - kind: semantic label ("Currency", "Duration", "Count", "Rate", "Prob", "Scalar", "Ratio", "Dimensionless", "Bool", "String", "Any")
    """

    currencies: tuple[tuple[str, int], ...] = ()
    time_exp: int = 0
    time_unit: str = "day"
    entities: tuple[tuple[str, int], ...] = ()
    factor: float = 1.0
    kind: str = "Dimension"

    # Common canonical constants
    DIMENSIONLESS: ClassVar[Dimension]
    SCALAR: ClassVar[Dimension]
    PROB: ClassVar[Dimension]
    RATIO: ClassVar[Dimension]
    BOOLEAN: ClassVar[Dimension]
    STRING: ClassVar[Dimension]
    ANY: ClassVar[Dimension]

    # --- Factory Constructors ---

    @classmethod
    def dimensionless(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="Dimensionless")

    @classmethod
    def scalar(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="Scalar")

    @classmethod
    def prob(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="Prob")

    @classmethod
    def ratio(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="Ratio")

    @classmethod
    def boolean(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="Bool")

    @classmethod
    def string(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="String")

    @classmethod
    def any(cls) -> Dimension:
        return cls(currencies=(), time_exp=0, entities=(), factor=1.0, kind="Any")

    @classmethod
    def currency(cls, code: str = "") -> Dimension:
        c = code.upper().strip() if code else "*"
        return cls(currencies=((c, 1),), time_exp=0, entities=(), factor=1.0, kind="Currency")

    @classmethod
    def duration(cls, unit: str = "day") -> Dimension:
        u = unit.lower().strip() if unit else "day"
        return cls(currencies=(), time_exp=1, time_unit=u, entities=(), factor=1.0, kind="Duration")

    @classmethod
    def count(cls, entity: str = "") -> Dimension:
        tag = entity.strip() if entity else "*"
        return cls(currencies=(), time_exp=0, entities=((tag, 1),), factor=1.0, kind="Count")

    # --- Marketing Aliases ---

    @classmethod
    def cpc(cls, curr: str = "USD") -> Dimension:
        """Cost Per Click = Currency / Click."""
        return cls.currency(curr) / cls.count("Click")

    @classmethod
    def cac(cls, curr: str = "USD") -> Dimension:
        """Customer Acquisition Cost = Currency / Customer."""
        return cls.currency(curr) / cls.count("Customer")

    @classmethod
    def cpm(cls, curr: str = "USD") -> Dimension:
        """Cost Per Mille = Currency / (1000 * Impression)."""
        d = cls.currency(curr) / cls.count("Impression")
        return cls(
            currencies=d.currencies,
            time_exp=d.time_exp,
            time_unit=d.time_unit,
            entities=d.entities,
            factor=1000.0,
            kind="Rate",
        )

    @classmethod
    def ctr(cls) -> Dimension:
        """Click-Through Rate = Click / Impression."""
        return cls.count("Click") / cls.count("Impression")

    @classmethod
    def cvr(cls) -> Dimension:
        """Conversion Rate = Order / Click."""
        return cls.count("Order") / cls.count("Click")

    @classmethod
    def spend_rate(cls, curr: str = "USD", unit: str = "day") -> Dimension:
        """Spend Rate = Currency / Duration."""
        return cls.currency(curr) / cls.duration(unit)

    @classmethod
    def roas(cls) -> Dimension:
        """Return On Ad Spend = Currency / Currency = Dimensionless Ratio."""
        return cls.ratio()

    # Exact rational scale factors relative to seconds
    def scale_to(self, target_unit: str) -> float:
        """Returns the multiplicative scale factor from self.time_unit to target_unit.
        
        Example:
            Duration<day>.scale_to("hour") -> 24.0 (1 day = 24 hours)
            Duration<hour>.scale_to("day") -> 1 / 24.0
        """
        curr_sec = TIME_SCALE_SECONDS.get(self.time_unit.lower(), 86400.0)
        target_sec = TIME_SCALE_SECONDS.get(target_unit.lower(), 86400.0)
        return curr_sec / target_sec

    def normalize_time(self, target_unit: str = "day") -> Dimension:
        """Returns a Dimension with its time scale normalized to target_unit."""
        if self.time_exp == 0 or self.time_unit.lower() == target_unit.lower():
            return self
        scale = self.scale_to(target_unit)
        new_factor = self.factor * (scale ** self.time_exp)
        return Dimension(
            currencies=self.currencies,
            time_exp=self.time_exp,
            time_unit=target_unit.lower(),
            entities=self.entities,
            factor=new_factor,
            kind=self.kind,
        )

    def is_any(self) -> bool:
        return self.kind == "Any"

    def is_dimensionless(self) -> bool:
        return self.time_exp == 0 and not self.currencies and not self.entities

    def is_prob(self) -> bool:
        return self.kind == "Prob"

    def is_currency(self) -> bool:
        return len(self.currencies) == 1 and self.currencies[0][1] == 1 and self.time_exp == 0 and not self.entities

    def get_currency_code(self) -> str | None:
        if len(self.currencies) == 1 and self.currencies[0][1] == 1:
            code = self.currencies[0][0]
            return code if code != "*" else None
        return None

    def is_duration(self) -> bool:
        return self.time_exp == 1 and not self.currencies and not self.entities

    def is_count(self) -> bool:
        return len(self.entities) == 1 and self.entities[0][1] == 1 and self.time_exp == 0 and not self.currencies

    # --- Group Algebra Operations ---

    def __mul__(self, other: Dimension) -> Dimension:
        if self.is_any() or other.is_any():
            return Dimension.any()

        # Combine currencies
        curr_map: dict[str, int] = dict(self.currencies)
        for code, exp in other.currencies:
            curr_map[code] = curr_map.get(code, 0) + exp
            if curr_map[code] == 0:
                del curr_map[code]
        new_curr = tuple(sorted(curr_map.items()))

        # Combine time
        new_time_exp = self.time_exp + other.time_exp
        new_time_unit = self.time_unit if self.time_exp != 0 else other.time_unit

        # Combine entities
        ent_map: dict[str, int] = dict(self.entities)
        for tag, exp in other.entities:
            ent_map[tag] = ent_map.get(tag, 0) + exp
            if ent_map[tag] == 0:
                del ent_map[tag]
        new_ent = tuple(sorted(ent_map.items()))

        new_factor = self.factor * other.factor

        # Determine semantic kind
        new_kind = self._derive_kind(new_curr, new_time_exp, new_ent)
        return Dimension(
            currencies=new_curr,
            time_exp=new_time_exp,
            time_unit=new_time_unit,
            entities=new_ent,
            factor=new_factor,
            kind=new_kind,
        )

    def __truediv__(self, other: Dimension) -> Dimension:
        return self * other.inverse()

    def inverse(self) -> Dimension:
        if self.is_any():
            return Dimension.any()
        inv_curr = tuple((code, -exp) for code, exp in self.currencies)
        inv_ent = tuple((tag, -exp) for tag, exp in self.entities)
        inv_factor = 1.0 / self.factor if self.factor != 0 else 1.0
        new_kind = self._derive_kind(inv_curr, -self.time_exp, inv_ent)
        return Dimension(
            currencies=inv_curr,
            time_exp=-self.time_exp,
            time_unit=self.time_unit,
            entities=inv_ent,
            factor=inv_factor,
            kind=new_kind,
        )

    def __pow__(self, power: int) -> Dimension:
        if not isinstance(power, int):
            raise TypeError("Dimension power must be an integer literal")
        if power == 0:
            return Dimension.dimensionless()
        if power == 1:
            return self
        if self.is_any():
            return Dimension.any()
        new_curr = tuple((code, exp * power) for code, exp in self.currencies)
        new_ent = tuple((tag, exp * power) for tag, exp in self.entities)
        new_factor = self.factor ** power
        new_kind = self._derive_kind(new_curr, self.time_exp * power, new_ent)
        return Dimension(
            currencies=new_curr,
            time_exp=self.time_exp * power,
            time_unit=self.time_unit,
            entities=new_ent,
            factor=new_factor,
            kind=new_kind,
        )

    def is_compatible_with(self, expected: Dimension) -> bool:
        """Verify dimensional equivalence for additive (+, -) and relational (<, ==) operations."""
        if self.is_any() or expected.is_any():
            return True

        if self.kind in ("Bool", "String") or expected.kind in ("Bool", "String"):
            return self.kind == expected.kind

        # Check time exponent
        if self.time_exp != expected.time_exp:
            return False

        # Check entity nominal counts
        if self.entities != expected.entities and not self._entities_compatible(self.entities, expected.entities):
            return False

        # Check currencies
        if not self._currencies_compatible(self.currencies, expected.currencies):
            return False

        # If both are dimensionless scalars, Prob is compatible with Scalar / float
        if self.is_dimensionless() and expected.is_dimensionless():
            return True

        return True

    @staticmethod
    def _currencies_compatible(c1: tuple[tuple[str, int], ...], c2: tuple[tuple[str, int], ...]) -> bool:
        if c1 == c2:
            return True
        if len(c1) != len(c2):
            return False
        for (code1, exp1), (code2, exp2) in zip(c1, c2, strict=False):
            if exp1 != exp2:
                return False
            # Wildcard "*" satisfies any specific currency
            if code1 != "*" and code2 != "*" and code1 != code2:
                return False
        return True

    @staticmethod
    def _entities_compatible(e1: tuple[tuple[str, int], ...], e2: tuple[tuple[str, int], ...]) -> bool:
        if e1 == e2:
            return True
        if len(e1) != len(e2):
            return False
        for (tag1, exp1), (tag2, exp2) in zip(e1, e2, strict=False):
            if exp1 != exp2:
                return False
            if tag1 != "*" and tag2 != "*" and tag1 != tag2:
                return False
        return True

    @staticmethod
    def _derive_kind(currencies: tuple[tuple[str, int], ...], time_exp: int, entities: tuple[tuple[str, int], ...]) -> str:
        if not currencies and time_exp == 0 and not entities:
            return "Dimensionless"
        if len(currencies) == 1 and currencies[0][1] == 1 and time_exp == 0 and not entities:
            return "Currency"
        if time_exp == 1 and not currencies and not entities:
            return "Duration"
        if len(entities) == 1 and entities[0][1] == 1 and time_exp == 0 and not currencies:
            return "Count"
        # If any negative exponent exists, it's a Rate
        has_negative = (time_exp < 0) or any(exp < 0 for _, exp in currencies) or any(exp < 0 for _, exp in entities)
        if has_negative:
            return "Rate"
        return "Composite"

    def __str__(self) -> str:
        if self.is_any():
            return "Any"
        if self.kind == "Prob":
            return "Prob"
        if self.kind == "Scalar":
            return "Scalar"
        if self.kind == "Ratio":
            return "Ratio"
        if self.is_dimensionless():
            return "Dimensionless"

        pos_parts: list[str] = []
        neg_parts: list[str] = []

        for code, exp in self.currencies:
            name = f"Currency<{code}>" if code != "*" else "Currency"
            if exp > 0:
                pos_parts.extend([name] * exp)
            elif exp < 0:
                neg_parts.extend([name] * (-exp))

        if self.time_exp > 0:
            name = f"Duration<{self.time_unit}>"
            pos_parts.extend([name] * self.time_exp)
        elif self.time_exp < 0:
            name = f"Duration<{self.time_unit}>"
            neg_parts.extend([name] * (-self.time_exp))

        for tag, exp in self.entities:
            name = f"Count<{tag}>" if tag != "*" else "Count"
            if exp > 0:
                pos_parts.extend([name] * exp)
            elif exp < 0:
                neg_parts.extend([name] * (-exp))

        num_str = " * ".join(pos_parts) if pos_parts else "1"
        if not neg_parts:
            return num_str
        den_str = " * ".join(neg_parts)
        return f"Rate<{num_str} / {den_str}>"


# Assign constants
Dimension.DIMENSIONLESS = Dimension.dimensionless()
Dimension.SCALAR = Dimension.scalar()
Dimension.PROB = Dimension.prob()
Dimension.RATIO = Dimension.ratio()
Dimension.BOOLEAN = Dimension.boolean()
Dimension.STRING = Dimension.string()
Dimension.ANY = Dimension.any()


class DimensionParser:
    """Parses source DSL type expressions into algebraic Dimension objects."""

    @classmethod
    def parse(cls, type_expr: str) -> Dimension:
        if not type_expr or not isinstance(type_expr, str):
            return Dimension.any()

        s = type_expr.strip()

        # Any / generic
        if s in ("Any", "any", "object", "unknown"):
            return Dimension.any()

        # Marketing Aliases
        if s in ("CPC", "cpc"):
            return Dimension.cpc()
        cpc_m = re.match(r"^CPC<([A-Za-z0-9_]+)>$", s, re.IGNORECASE)
        if cpc_m:
            return Dimension.cpc(cpc_m.group(1).upper())

        if s in ("CAC", "cac"):
            return Dimension.cac()
        cac_m = re.match(r"^CAC<([A-Za-z0-9_]+)>$", s, re.IGNORECASE)
        if cac_m:
            return Dimension.cac(cac_m.group(1).upper())

        if s in ("CPM", "cpm"):
            return Dimension.cpm()
        cpm_m = re.match(r"^CPM<([A-Za-z0-9_]+)>$", s, re.IGNORECASE)
        if cpm_m:
            return Dimension.cpm(cpm_m.group(1).upper())

        if s in ("CTR", "ctr"):
            return Dimension.ctr()

        if s in ("CVR", "cvr"):
            return Dimension.cvr()

        if s in ("ROAS", "roas"):
            return Dimension.roas()

        if s in ("SpendRate", "spend_rate"):
            return Dimension.spend_rate()
        sr_m = re.match(r"^SpendRate<([A-Za-z0-9_]+)>$", s, re.IGNORECASE)
        if sr_m:
            return Dimension.spend_rate(sr_m.group(1).upper())

        # Currency
        curr_m = re.match(r"^Currency(?:<([A-Za-z0-9_]+)>)?$", s)
        if curr_m:
            code = curr_m.group(1)
            return Dimension.currency(code.upper() if code else "")

        # Duration
        dur_m = re.match(r"^Duration(?:<([A-Za-z0-9_]+)>)?$", s)
        if dur_m:
            unit = dur_m.group(1)
            return Dimension.duration(unit.lower() if unit else "day")

        # Count
        count_m = re.match(r"^Count(?:<([A-Za-z0-9_]+)>)?$", s)
        if count_m:
            tag = count_m.group(1)
            return Dimension.count(tag or "")

        # Prob / Scalar / Ratio
        if s == "Prob":
            return Dimension.prob()
        if s == "Scalar":
            return Dimension.scalar()
        if s == "Ratio":
            return Dimension.ratio()

        # Rate<Num / Denom>
        if s.startswith("Rate<") and s.endswith(">"):
            inner = s[5:-1].strip()
            depth = 0
            slash_pos = -1
            for idx, ch in enumerate(inner):
                if ch == "<":
                    depth += 1
                elif ch == ">":
                    depth -= 1
                elif ch == "/" and depth == 0:
                    slash_pos = idx
                    break
            if slash_pos != -1:
                num = cls.parse(inner[:slash_pos].strip())
                den = cls.parse(inner[slash_pos + 1:].strip())
                return num / den

        # Primitive Containers (Flow, Pool, LedgerAccount)
        pool_m = re.match(r"^Pool(?:<([A-Za-z0-9_<>]+)>)?$", s)
        if pool_m:
            inner = cls.parse(pool_m.group(1)) if pool_m.group(1) else Dimension.scalar()
            return inner

        flow_m = re.match(r"^Flow(?:<([A-Za-z0-9_<>]+)>)?$", s)
        if flow_m:
            inner = cls.parse(flow_m.group(1)) if flow_m.group(1) else Dimension.scalar()
            return inner

        ledger_m = re.match(r"^LedgerAccount(?:<([A-Za-z0-9_]+)>)?$", s)
        if ledger_m:
            code = ledger_m.group(1)
            return Dimension.currency(code.upper() if code else "")

        if s.startswith("CapacityGuard"):
            return Dimension.scalar()

        if s == "Metric":
            return Dimension.scalar()

        # Base primitive scalar types
        if s in ("int", "float"):
            return Dimension.scalar()
        if s == "bool":
            return Dimension.boolean()
        if s in ("string", "str"):
            return Dimension.string()

        # Nominal Tagged Count fallback for Capitalized single words (e.g. "Click", "Order")
        if s.isalnum() and s[0].isupper():
            if _ISO_CURRENCY_PATTERN.match(s):
                return Dimension.currency(s)
            return Dimension.count(s)

        return Dimension.any()


from funnelscript.compiler.diagnostics import DimensionalTypeError

# Backwards compatibility alias for DimensionalUnit
DimensionalUnit = Dimension


class DimensionalTypeChecker:
    """Static compile-time dimensional type inference, verification, and refinement checker.
    
    Enforces:
    - FNL-T201: Dimensional Mismatch (e.g. Currency + Count, incompatible transitions)
    - FNL-T202: Currency Isolation (e.g. USD + EUR without FX rate)
    - FNL-T203: Non-Dimensionless Transcendental Argument (e.g. exp(100 USD))
    - FNL-T204: Probability Bounds Violation (Prob literal < 0 or > 1)
    - FNL-T205: Non-Negative Domain Constraint Violation (budget < 0, K <= 0, alpha <= 0)
    """

    @classmethod
    def infer_expression_dim(
        cls,
        expr: Any,
        env: dict[str, Dimension],
        payload_env: dict[str, Dimension] | None = None,
        errors: list[DimensionalTypeError] | None = None,
    ) -> Dimension:
        """Infers the physical/financial dimension of a World or rule expression."""
        if expr is None:
            return Dimension.any()

        # Literal expressions
        if hasattr(expr, "kind") and expr.kind == "literal" or type(expr).__name__ == "LiteralExpression":
            val = getattr(expr, "value", None)
            if isinstance(val, bool):
                return Dimension.boolean()
            if isinstance(val, str):
                return Dimension.string()
            if isinstance(val, (int, float)):
                return Dimension.scalar()
            return Dimension.any()

        # State reference
        if hasattr(expr, "kind") and expr.kind == "reference" or type(expr).__name__ == "ReferenceExpression":
            name = getattr(expr, "name", "")
            if name in env:
                return env[name]
            if name.startswith("self."):
                sub = name.split(".", 1)[1]
                if sub in env:
                    return env[sub]
            return Dimension.any()

        # Payload field reference
        if hasattr(expr, "kind") and expr.kind == "payload_field" or type(expr).__name__ == "PayloadFieldExpression":
            name = getattr(expr, "name", "")
            if payload_env and name in payload_env:
                return payload_env[name]
            return Dimension.any()

        # Binary expression
        if hasattr(expr, "kind") and expr.kind == "binary" or type(expr).__name__ == "BinaryExpression":
            op = getattr(expr, "operator", "+")
            left_dim = cls.infer_expression_dim(expr.left, env, payload_env, errors)
            right_dim = cls.infer_expression_dim(expr.right, env, payload_env, errors)

            if left_dim.is_any() or right_dim.is_any():
                return Dimension.any()

            if op in ("+", "-"):
                if not left_dim.is_compatible_with(right_dim):
                    c_left = left_dim.get_currency_code()
                    c_right = right_dim.get_currency_code()
                    if c_left and c_right and c_left != c_right:
                        err = DimensionalTypeError(
                            code="FNL-T202",
                            message=f"Currency isolation violation: cannot perform '{op}' between distinct currencies {c_left} and {c_right}",
                            span=getattr(expr, "span", None),
                            expected=str(left_dim),
                            inferred=str(right_dim),
                            remediation="Use an explicit exchange rate to convert currencies before adding/subtracting.",
                        )
                        if errors is not None:
                            errors.append(err)
                        else:
                            raise err
                    err = DimensionalTypeError(
                        code="FNL-T201",
                        message=f"Dimensional mismatch in arithmetic: cannot perform '{op}' between {left_dim} and {right_dim}",
                        span=getattr(expr, "span", None),
                        expected=str(left_dim),
                        inferred=str(right_dim),
                        remediation="Verify operands share compatible physical/financial dimensions.",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err
                return left_dim

            if op == "*":
                return left_dim * right_dim

            if op == "/":
                return left_dim / right_dim

            return Dimension.any()

        # Sample expression
        if hasattr(expr, "kind") and expr.kind == "sample" or type(expr).__name__ == "SampleExpression":
            dist = getattr(expr, "distribution", "")
            args = getattr(expr, "arguments", [])
            if dist == "bernoulli" and args:
                p_arg = args[0]
                if hasattr(p_arg, "value") and isinstance(p_arg.value, (int, float)):
                    p_val = float(p_arg.value)
                    if not (0.0 <= p_val <= 1.0):
                        err = DimensionalTypeError(
                            code="FNL-T204",
                            message=f"Probability out of bounds: literal {p_val} must be in [0.0, 1.0]",
                            span=getattr(p_arg, "span", getattr(expr, "span", None)),
                            expected="Prob in [0.0, 1.0]",
                            inferred=str(p_val),
                            remediation="Clamp Bernoulli parameter to [0.0, 1.0].",
                        )
                        if errors is not None:
                            errors.append(err)
                        else:
                            raise err
                return Dimension.boolean()
            if dist == "uniform" and len(args) >= 2:
                low_dim = cls.infer_expression_dim(args[0], env, payload_env, errors)
                return low_dim
            return Dimension.scalar()

        # Call expression
        if hasattr(expr, "kind") and expr.kind == "call" or type(expr).__name__ == "CallExpression":
            fn = getattr(expr, "function", "")
            args = getattr(expr, "arguments", [])

            if fn == "hill":
                if len(args) < 3:
                    return Dimension.scalar()
                s_dim = cls.infer_expression_dim(args[0], env, payload_env, errors)
                k_dim = cls.infer_expression_dim(args[1], env, payload_env, errors)
                alpha_dim = cls.infer_expression_dim(args[2], env, payload_env, errors)

                if hasattr(args[1], "value") and isinstance(args[1].value, (int, float)) and args[1].value <= 0:
                    err = DimensionalTypeError(
                        code="FNL-T205",
                        message=f"Half-saturation constant K must be positive (> 0), got {args[1].value}",
                        span=getattr(args[1], "span", getattr(expr, "span", None)),
                        expected="K > 0",
                        inferred=str(args[1].value),
                        remediation="Set K to a positive spend threshold.",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err

                if hasattr(args[2], "value") and isinstance(args[2].value, (int, float)) and args[2].value <= 0:
                    err = DimensionalTypeError(
                        code="FNL-T205",
                        message=f"Hill slope parameter alpha must be positive (> 0), got {args[2].value}",
                        span=getattr(args[2], "span", getattr(expr, "span", None)),
                        expected="alpha > 0",
                        inferred=str(args[2].value),
                        remediation="Set alpha curvature parameter > 0 (e.g. 0.8).",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err

                if not s_dim.is_any() and not k_dim.is_any() and not k_dim.is_dimensionless() and not s_dim.is_compatible_with(k_dim):
                    err = DimensionalTypeError(
                        code="FNL-T201",
                        message=f"Dimensional mismatch in hill(): spend S ({s_dim}) and half-saturation K ({k_dim}) must have identical dimensions",
                        span=getattr(args[1], "span", getattr(expr, "span", None)),
                        expected=str(s_dim),
                        inferred=str(k_dim),
                        remediation="Ensure K has the same dimension and currency/time units as spend S.",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err

                if not alpha_dim.is_any() and not alpha_dim.is_dimensionless():
                    err = DimensionalTypeError(
                        code="FNL-T201",
                        message=f"Hill slope parameter alpha must be dimensionless Scalar, got {alpha_dim}",
                        span=getattr(args[2], "span", getattr(expr, "span", None)),
                        expected="Scalar",
                        inferred=str(alpha_dim),
                        remediation="Alpha curvature parameter must be a dimensionless number.",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err
                        if errors is not None:
                            errors.append(err)
                        else:
                            raise err

                if len(args) >= 4:
                    return cls.infer_expression_dim(args[3], env, payload_env, errors)
                return Dimension.scalar()

            if fn == "adstock":
                if len(args) < 2:
                    return Dimension.scalar()
                s_dim = cls.infer_expression_dim(args[0], env, payload_env, errors)
                decay_dim = cls.infer_expression_dim(args[1], env, payload_env, errors)

                if not decay_dim.is_any() and not decay_dim.is_dimensionless() and not decay_dim.is_prob():
                    err = DimensionalTypeError(
                        code="FNL-T201",
                        message=f"Adstock decay parameter must be Prob in [0, 1), got {decay_dim}",
                        span=getattr(args[1], "span", getattr(expr, "span", None)),
                        expected="Prob",
                        inferred=str(decay_dim),
                        remediation="Adstock decay rate must be a retention fraction in [0.0, 1.0).",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err

                if hasattr(args[1], "value") and isinstance(args[1].value, (int, float)):
                    d_val = float(args[1].value)
                    if not (0.0 <= d_val < 1.0):
                        err = DimensionalTypeError(
                            code="FNL-T204",
                            message=f"Adstock decay rate must be in [0.0, 1.0), got {d_val}",
                            span=getattr(args[1], "span", getattr(expr, "span", None)),
                            expected="decay in [0.0, 1.0)",
                            inferred=str(d_val),
                            remediation="Clamp decay rate to [0.0, 1.0) to guarantee geometric convergence.",
                        )
                        if errors is not None:
                            errors.append(err)
                        else:
                            raise err
                return s_dim

            if fn in ("exp", "log", "sigmoid"):
                if not args:
                    return Dimension.scalar()
                arg_dim = cls.infer_expression_dim(args[0], env, payload_env, errors)
                if not arg_dim.is_any() and not arg_dim.is_dimensionless():
                    err = DimensionalTypeError(
                        code="FNL-T203",
                        message=f"Non-dimensionless argument to transcendental function '{fn}': expected dimensionless scalar, got {arg_dim}",
                        span=getattr(args[0], "span", getattr(expr, "span", None)),
                        expected="Dimensionless",
                        inferred=str(arg_dim),
                        remediation=f"Normalize or scale the argument to '{fn}' so it is strictly dimensionless.",
                    )
                    if errors is not None:
                        errors.append(err)
                    else:
                        raise err
                return Dimension.scalar()

            if fn == "fx_convert":
                if len(args) < 2:
                    return Dimension.any()
                amt_dim = cls.infer_expression_dim(args[0], env, payload_env, errors)
                rate_dim = cls.infer_expression_dim(args[1], env, payload_env, errors)
                return amt_dim * rate_dim

        return Dimension.any()

    @classmethod
    def check_world(cls, world: Any) -> list[DimensionalTypeError]:
        """Performs static dimensional type checking over an entire WorldAST."""
        errors: list[DimensionalTypeError] = []
        if not hasattr(world, "declarations"):
            return errors

        for decl in world.declarations:
            if not hasattr(decl, "states"):
                continue

            # Build environment for this entity/agent
            env: dict[str, Dimension] = {}

            # States
            for s in getattr(decl, "states", []):
                dim = DimensionParser.parse(s.type_name)
                env[s.name] = dim

                val = getattr(s, "value", None)
                if isinstance(val, (int, float)):
                    num_val = float(val)
                    if dim.is_prob() and not (0.0 <= num_val <= 1.0):
                        errors.append(
                            DimensionalTypeError(
                                code="FNL-T204",
                                message=f"Probability out of bounds for state '{decl.name}.{s.name}': literal {num_val} must be in [0.0, 1.0]",
                                span=getattr(s, "span", None),
                                expected="Prob in [0.0, 1.0]",
                                inferred=str(num_val),
                                remediation="Clamp probability parameter to [0.0, 1.0].",
                            )
                        )
                    if (dim.is_currency() or dim.is_duration()) and num_val < 0:
                        errors.append(
                            DimensionalTypeError(
                                code="FNL-T205",
                                message=f"Non-negative domain constraint violated for state '{decl.name}.{s.name}': found {num_val}",
                                span=getattr(s, "span", None),
                                expected="Non-negative value (>= 0)",
                                inferred=str(num_val),
                                remediation="Ensure budget caps and durations are non-negative (>= 0).",
                            )
                        )

            # Primitives (Pool, Flow, LedgerAccount, etc.)
            for p in getattr(decl, "primitives", []):
                dim = DimensionParser.parse(getattr(p, "type_spec", "Scalar"))
                env[p.name] = dim
                init_val = getattr(p, "initial_value", None)
                if isinstance(init_val, (int, float)):
                    num_val = float(init_val)
                    if dim.is_prob() and not (0.0 <= num_val <= 1.0):
                        errors.append(
                            DimensionalTypeError(
                                code="FNL-T204",
                                message=f"Probability out of bounds for primitive '{decl.name}.{p.name}': literal {num_val} must be in [0.0, 1.0]",
                                span=getattr(p, "span", None),
                                expected="Prob in [0.0, 1.0]",
                                inferred=str(num_val),
                                remediation="Clamp probability parameter to [0.0, 1.0].",
                            )
                        )
                    if (dim.is_currency() or dim.is_duration()) and num_val < 0:
                        errors.append(
                            DimensionalTypeError(
                                code="FNL-T205",
                                message=f"Non-negative domain constraint violated for primitive '{decl.name}.{p.name}': found {num_val}",
                                span=getattr(p, "span", None),
                                expected="Non-negative value (>= 0)",
                                inferred=str(num_val),
                                remediation="Ensure budget caps and durations are non-negative (>= 0).",
                            )
                        )

            # Event schemas
            event_schemas: dict[str, dict[str, Dimension]] = {}
            for ev in getattr(decl, "events", []):
                event_schemas[ev.name] = {
                    f.name: DimensionParser.parse(f.type_name)
                    for f in getattr(ev, "fields", [])
                }

            # Rules
            for rule in getattr(decl, "rules", []):
                payload_env = event_schemas.get(rule.event, {})

                # Transitions
                for t in getattr(rule, "transitions", []):
                    target_dim = env.get(t.target, Dimension.any())
                    expr_dim = cls.infer_expression_dim(t.expr, env, payload_env, errors)

                    if not expr_dim.is_any() and not target_dim.is_any() and not expr_dim.is_compatible_with(target_dim):
                        c_act = expr_dim.get_currency_code()
                        c_tgt = target_dim.get_currency_code()
                        if c_act and c_tgt and c_act != c_tgt:
                            errors.append(
                                DimensionalTypeError(
                                    code="FNL-T202",
                                    message=f"Currency isolation violation assigning '{t.target}': cannot assign {expr_dim} to {target_dim}",
                                    span=getattr(t, "span", None),
                                    expected=str(target_dim),
                                    inferred=str(expr_dim),
                                    remediation=f"Convert {c_act} to {c_tgt} using an explicit exchange rate.",
                                )
                            )
                        else:
                            errors.append(
                                DimensionalTypeError(
                                    code="FNL-T201",
                                    message=f"Dimensional mismatch assigning '{t.target}': expected {target_dim}, got {expr_dim}",
                                    span=getattr(t, "span", None),
                                    expected=str(target_dim),
                                    inferred=str(expr_dim),
                                    remediation=f"Ensure expression dimension matches target state dimension {target_dim}.",
                                )
                            )

                # Emissions
                for em in getattr(rule, "emissions", []):
                    schema = event_schemas.get(em.event, {})
                    for arg_name, arg_expr in getattr(em, "arguments", {}).items():
                        expected_dim = schema.get(arg_name, Dimension.any())
                        actual_dim = cls.infer_expression_dim(arg_expr, env, payload_env, errors)
                        if not actual_dim.is_any() and not expected_dim.is_any() and not actual_dim.is_compatible_with(expected_dim):
                            errors.append(
                                DimensionalTypeError(
                                    code="FNL-T201",
                                    message=f"Dimensional mismatch in emitted argument '{arg_name}' of event '{em.event}': expected {expected_dim}, got {actual_dim}",
                                    span=getattr(arg_expr, "span", getattr(em, "span", None)),
                                    expected=str(expected_dim),
                                    inferred=str(actual_dim),
                                    remediation=f"Match the declared parameter dimension {expected_dim}.",
                                )
                            )
                    delay_expr = getattr(em, "delay", None)
                    if hasattr(delay_expr, "kind"):
                        delay_dim = cls.infer_expression_dim(delay_expr, env, payload_env, errors)
                        if not delay_dim.is_any() and not delay_dim.is_dimensionless() and not delay_dim.is_compatible_with(Dimension.duration()):
                            errors.append(
                                DimensionalTypeError(
                                    code="FNL-T201",
                                    message=f"Dimensional mismatch in emission delay of event '{em.event}': expected Duration or dimensionless scalar, got {delay_dim}",
                                    span=getattr(delay_expr, "span", getattr(em, "span", None)),
                                    expected="Duration | dimensionless",
                                    inferred=str(delay_dim),
                                    remediation="Ensure emission delay expression is dimensionless or has Duration unit.",
                                )
                            )

            # Lifecycle Handlers
            for h in getattr(decl, "handlers", []):
                for act in getattr(h, "actions", []):
                    postings = getattr(act, "postings", None)
                    if postings:
                        for p in postings:
                            acc_name = p.account
                            if acc_name.startswith("self."):
                                acc_name = acc_name.split(".", 1)[1]
                            acc_dim = env.get(acc_name, Dimension.any())
                            amt_dim = cls.infer_expression_dim(p.amount_expr, env, {}, errors)
                            if acc_dim.is_currency() and amt_dim.is_currency():
                                c_acc = acc_dim.get_currency_code()
                                c_amt = amt_dim.get_currency_code()
                                if c_acc and c_amt and c_acc != c_amt:
                                    errors.append(
                                        DimensionalTypeError(
                                            code="FNL-T202",
                                            message=f"Currency isolation violation in post statement: cannot post {c_amt} amount to {c_acc} account '{acc_name}'",
                                            span=getattr(p, "span", getattr(act, "span", None)),
                                            expected=str(acc_dim),
                                            inferred=str(amt_dim),
                                            remediation=f"Ensure posted amount matches account currency {c_acc}.",
                                        )
                                    )

        return errors

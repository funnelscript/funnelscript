"""Typed, domain-neutral World declaration AST and primitive state checker.

Research: funnelscript-research/spec/world-declarations-v0.md (H-W1 to H-W4).
"""

from __future__ import annotations

import linecache
import math
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field

from funnelscript.tokens import SourceSpan, diagnostic_excerpt


class LocatedNode(BaseModel):
    span: SourceSpan | None = Field(default=None, exclude=True, repr=False)


class StateDefinition(LocatedNode):
    name: str
    type_name: str
    value: object


class PayloadFieldExpression(LocatedNode):
    kind: Literal["payload_field"] = "payload_field"
    name: str


class LiteralExpression(LocatedNode):
    kind: Literal["literal"] = "literal"
    value: object


class ReferenceExpression(LocatedNode):
    kind: Literal["reference"] = "reference"
    name: str


class BinaryExpression(LocatedNode):
    kind: Literal["binary"] = "binary"
    operator: Literal["+", "-", "*", "/"]
    left: StateExpression
    right: StateExpression


class SampleExpression(LocatedNode):
    kind: Literal["sample"] = "sample"
    distribution: Literal["bernoulli", "uniform"]
    arguments: list[LiteralExpression | ReferenceExpression | PayloadFieldExpression]


class CallExpression(LocatedNode):
    kind: Literal["call"] = "call"
    function: str
    arguments: list[StateExpression] = Field(default_factory=list)


StateExpression = Annotated[
    LiteralExpression | ReferenceExpression | PayloadFieldExpression | BinaryExpression
    | SampleExpression | CallExpression,
    Field(discriminator="kind"),
]


class StateTransitionDefinition(LocatedNode):
    target: str
    expr: StateExpression


class EventFieldDefinition(LocatedNode):
    name: str
    type_name: str


class EventDefinition(LocatedNode):
    name: str
    fields: list[EventFieldDefinition] = Field(default_factory=list)


class EventEmissionDefinition(LocatedNode):
    event: str
    delay: StateExpression | float | int
    arguments: dict[str, StateExpression] = Field(default_factory=dict)


class GuardDefinition(LocatedNode):
    field: str
    operator: Literal["==", "!=", "<", "<=", ">", ">="]
    value: object


class EventRuleDefinition(LocatedNode):
    name: str
    event: str
    guard: GuardDefinition | None = None
    transitions: list[StateTransitionDefinition] = Field(default_factory=list)
    emissions: list[EventEmissionDefinition] = Field(default_factory=list)


# --- Meta-Ontology, Core Traits & 5 Kernel Primitives AST Nodes ---

class PrimitiveFieldDefinition(LocatedNode):
    primitive_kind: Literal["pool", "flow", "ledger", "capacity", "metric", "attribute"]
    name: str
    type_spec: str
    initial_value: object = None
    capacity_max: float | None = None
    capacity_window: str | None = None
    metric_expr: StateExpression | None = None


class LedgerPostingDefinition(LocatedNode):
    operation: Literal["debit", "credit"]
    account: str
    amount_expr: StateExpression


class PostStatementDefinition(LocatedNode):
    kind: Literal["post"] = "post"
    postings: list[LedgerPostingDefinition] = Field(default_factory=list)


class BranchArmDefinition(LocatedNode):
    condition: bool
    emission: EventEmissionDefinition


class DelayBranchDefinition(LocatedNode):
    kind: Literal["delay_branch"] = "delay_branch"
    delay_expr: StateExpression
    branch_prob_expr: StateExpression
    arms: list[BranchArmDefinition] = Field(default_factory=list)


LifecycleAction = (
    PostStatementDefinition
    | DelayBranchDefinition
    | StateTransitionDefinition
    | EventEmissionDefinition
)


class LifecycleHandlerDefinition(LocatedNode):
    event: str
    actions: list[
        PostStatementDefinition
        | DelayBranchDefinition
        | StateTransitionDefinition
        | EventEmissionDefinition
    ] = Field(default_factory=list)


class TraitParameter(LocatedNode):
    name: str
    type_name: str


class TraitMemberDefinition(LocatedNode):
    kind: Literal["field", "handler"]
    name: str
    type_name: str | None = None
    parameters: list[TraitParameter] = Field(default_factory=list)


class TraitDefinition(LocatedNode):
    kind: Literal["trait"] = "trait"
    name: str
    members: list[TraitMemberDefinition] = Field(default_factory=list)


class EntityDefinition(LocatedNode):
    kind: Literal["entity"] = "entity"
    name: str
    implements: list[str] = Field(default_factory=list)
    states: list[StateDefinition] = Field(default_factory=list)
    primitives: list[PrimitiveFieldDefinition] = Field(default_factory=list)
    events: list[EventDefinition] = Field(default_factory=list)
    rules: list[EventRuleDefinition] = Field(default_factory=list)
    handlers: list[LifecycleHandlerDefinition] = Field(default_factory=list)


class AgentDefinition(EntityDefinition):
    kind: Literal["agent"] = "agent"


WorldDeclaration = Annotated[
    EntityDefinition | AgentDefinition | TraitDefinition, Field(discriminator="kind")
]


class WorldAST(LocatedNode):
    kind: Literal["world"] = "world"
    name: str
    declarations: list[WorldDeclaration] = Field(default_factory=list)


class WorldTypeError(ValueError):
    """A source declaration violates the primitive typing contract."""

    def __init__(
        self,
        message: str,
        *,
        span: SourceSpan | None = None,
        code: str = "FNL-T201",
        expected: str | None = None,
        inferred: str | None = None,
        remediation: str = "Verify declaration names, field references, and primitive types.",
    ) -> None:
        super().__init__(message)
        self.span = span
        self.code = code
        self.expected = expected
        self.inferred = inferred
        self.remediation = remediation

    def __str__(self) -> str:
        message = super().__str__()
        if self.span is None:
            return message
        span = self.span
        line = linecache.getline(span.file, span.start_line).rstrip("\r\n")
        width = span.end_col - span.start_col if span.start_line == span.end_line else 1
        excerpt = diagnostic_excerpt(line, span.start_col, width) if line else ""
        extra = f"\n  Expected: {self.expected}\n  Inferred: {self.inferred}" if self.expected else ""
        return (
            f"{self.code} {span.file}: line {span.start_line}, column {span.start_col}\n"
            f"{excerpt}\nWorldTypeError: {message}{extra}\n"
            f"Hint: {self.remediation}"
        )


@contextmanager
def _located(node: LocatedNode) -> Iterator[None]:
    """Preserve the nearest originating AST span on semantic failure."""
    try:
        yield
    except WorldTypeError as error:
        if error.span is None:
            error.span = node.span
        raise


class WorldTypeChecker:
    """Checks declaration uniqueness and exact primitive literal types."""

    PRIMITIVES: ClassVar[dict[str, type]] = {"int": int, "float": float, "bool": bool, "string": str}

    @classmethod
    def check(cls, world: WorldAST) -> None:
        names: set[str] = set()
        for declaration in world.declarations:
            with _located(declaration):
                if declaration.name in names:
                    raise WorldTypeError(f"Duplicate declaration '{declaration.name}'")
                names.add(declaration.name)
                if isinstance(declaration, TraitDefinition):
                    cls._check_trait(declaration)
                else:
                    cls._check_states(declaration)
                    cls._check_primitives(declaration)
                    cls._check_rules(declaration)

    @classmethod
    def _check_trait(cls, trait: TraitDefinition) -> None:
        member_names: set[str] = set()
        for member in trait.members:
            with _located(member):
                if member.name in member_names:
                    raise WorldTypeError(f"Duplicate member '{member.name}' in trait '{trait.name}'")
                member_names.add(member.name)

    @classmethod
    def _check_primitives(cls, declaration: EntityDefinition) -> None:
        state_names = {state.name for state in declaration.states}
        for prim in declaration.primitives:
            with _located(prim):
                if prim.name in state_names:
                    raise WorldTypeError(f"Duplicate field or state '{prim.name}' in '{declaration.name}'")
                state_names.add(prim.name)

    @classmethod
    def _check_states(cls, declaration: EntityDefinition) -> None:
        fields: set[str] = set()
        for state in declaration.states:
            with _located(state):
                if state.name in fields:
                    raise WorldTypeError(
                        f"Duplicate state '{state.name}' in '{declaration.name}'"
                    )
                fields.add(state.name)
                expected = cls.PRIMITIVES.get(state.type_name)
                if expected is not None:
                    if type(state.value) is not expected:
                        raise WorldTypeError(
                            f"Type mismatch for '{declaration.name}.{state.name}': "
                            f"expected {state.type_name}, got {type(state.value).__name__}"
                        )
                else:
                    from funnelscript.compiler.dimensions import DimensionParser
                    dim = DimensionParser.parse(state.type_name)
                    if dim.is_any():
                        raise WorldTypeError(
                            f"Unknown state type '{state.type_name}' for '{state.name}'"
                        )
                    if dim.kind == "Bool":
                        if type(state.value) is not bool:
                            raise WorldTypeError(
                                f"Type mismatch for '{declaration.name}.{state.name}': "
                                f"expected {state.type_name}, got {type(state.value).__name__}"
                            )
                    elif dim.kind == "String":
                        if type(state.value) is not str:
                            raise WorldTypeError(
                                f"Type mismatch for '{declaration.name}.{state.name}': "
                                f"expected {state.type_name}, got {type(state.value).__name__}"
                            )
                    else:
                        if type(state.value) not in (int, float):
                            raise WorldTypeError(
                                f"Type mismatch for '{declaration.name}.{state.name}': "
                                f"expected {state.type_name}, got {type(state.value).__name__}"
                            )
                        num_val = float(state.value)
                        if dim.is_prob() and not (0.0 <= num_val <= 1.0):
                            raise WorldTypeError(
                                f"Probability out of bounds: literal {num_val} must be in [0.0, 1.0]",
                                code="FNL-T204",
                                expected="Prob in [0.0, 1.0]",
                                inferred=str(num_val),
                                remediation="Clamp probability parameter to [0.0, 1.0].",
                            )
                        if (dim.is_currency() or dim.is_duration()) and num_val < 0:
                            raise WorldTypeError(
                                f"Non-negative domain constraint violated: found {num_val}",
                                code="FNL-T205",
                                expected="Non-negative value (>= 0)",
                                inferred=str(num_val),
                                remediation="Ensure budget caps and durations are non-negative (>= 0).",
                            )

    @classmethod
    def _event_types(cls, declaration: EntityDefinition) -> dict[str, dict[str, str]]:
        schemas: dict[str, dict[str, str]] = {}
        for event in declaration.events:
            with _located(event):
                if event.name in schemas:
                    raise WorldTypeError(f"Duplicate event declaration '{event.name}'")
                schemas[event.name] = cls._event_fields(event)
        return schemas

    @classmethod
    def _event_fields(cls, event: EventDefinition) -> dict[str, str]:
        fields: dict[str, str] = {}
        for field in event.fields:
            with _located(field):
                if field.name in fields:
                    raise WorldTypeError(f"Duplicate event field '{field.name}'")
                if field.type_name not in cls.PRIMITIVES:
                    from funnelscript.compiler.dimensions import DimensionParser
                    dim = DimensionParser.parse(field.type_name)
                    if dim.is_any():
                        raise WorldTypeError(f"Unknown event field type '{field.type_name}'")
                fields[field.name] = field.type_name
        return fields

    @classmethod
    def _check_rules(cls, declaration: EntityDefinition) -> None:
        types = {state.name: state.type_name for state in declaration.states}
        event_types = cls._event_types(declaration)
        names: set[str] = set()
        events: set[str] = set()
        declared_events = {rule.event for rule in declaration.rules}
        for rule in declaration.rules:
            with _located(rule):
                if rule.name in names:
                    raise WorldTypeError(f"Duplicate rule '{rule.name}'")
                if rule.event in events:
                    raise WorldTypeError(f"Duplicate event handler '{rule.event}'")
                names.add(rule.name)
                events.add(rule.event)
                if rule.guard is not None:
                    with _located(rule.guard):
                        cls._check_guard(rule.guard, types)
                cls._check_transitions(rule, types, event_types)
                cls._check_emissions(rule, declared_events, types, event_types)

    @classmethod
    def _check_transitions(
        cls, rule: EventRuleDefinition, types: dict[str, str],
        event_types: dict[str, dict[str, str]],
    ) -> None:
        targets: set[str] = set()
        for transition in rule.transitions:
            with _located(transition):
                target = transition.target
                if target in targets:
                    raise WorldTypeError(f"Duplicate transition target '{target}'")
                if target not in types:
                    raise WorldTypeError(f"Unknown transition target '{target}'")
                targets.add(target)
                actual_type = cls._expression_type(
                    transition.expr, types, event_types.get(rule.event, {})
                )
                if actual_type != types[target]:
                    if actual_type in cls.PRIMITIVES and types[target] in cls.PRIMITIVES:
                        raise WorldTypeError(
                            f"Type mismatch assigning '{target}': "
                            f"expected {types[target]}, got {actual_type}",
                            code="FNL-T201",
                            expected=types[target],
                            inferred=actual_type,
                            remediation=f"Ensure expression type matches target state type {types[target]}.",
                        )
                    from funnelscript.compiler.dimensions import DimensionParser
                    act_dim = DimensionParser.parse(actual_type)
                    tgt_dim = DimensionParser.parse(types[target])
                    if not act_dim.is_compatible_with(tgt_dim):
                        c_act = act_dim.get_currency_code()
                        c_tgt = tgt_dim.get_currency_code()
                        if c_act and c_tgt and c_act != c_tgt:
                            raise WorldTypeError(
                                f"Currency isolation violation: cannot assign {actual_type} to {types[target]}",
                                code="FNL-T202",
                                expected=types[target],
                                inferred=actual_type,
                                remediation=f"Convert {c_act} to {c_tgt} using an explicit exchange rate.",
                            )
                        raise WorldTypeError(
                            f"Type mismatch assigning '{target}': "
                            f"expected {types[target]}, got {actual_type}",
                            code="FNL-T201",
                            expected=types[target],
                            inferred=actual_type,
                            remediation=f"Ensure expression dimension matches target state dimension {types[target]}.",
                        )

    @classmethod
    def _check_emissions(
        cls, rule: EventRuleDefinition, declared_events: set[str],
        types: dict[str, str], event_types: dict[str, dict[str, str]],
    ) -> None:
        for emission in rule.emissions:
            with _located(emission):
                if emission.event not in declared_events:
                    raise WorldTypeError(f"Unknown emitted event '{emission.event}'")
                cls._check_payload_arguments(
                    emission.arguments,
                    event_types.get(emission.event, {}),
                    types,
                    event_types.get(rule.event, {}),
                )
                delay = emission.delay
                if type(delay) in (int, float):
                    try:
                        finite = math.isfinite(float(delay))
                    except OverflowError:
                        finite = False
                    if not finite or delay < 0:
                        raise WorldTypeError("Event emission delay must be finite and non-negative")
                elif isinstance(delay, (LiteralExpression, ReferenceExpression, PayloadFieldExpression, BinaryExpression, CallExpression, SampleExpression)):
                    delay_type = cls._expression_type(delay, types, event_types.get(rule.event, {}))
                    if delay_type not in ("int", "float", "Duration"):
                        raise WorldTypeError(
                            f"Event emission delay must be numeric: expression must resolve to int, float, or Duration, got '{delay_type}'"
                        )
                else:
                    raise WorldTypeError("Event emission delay must be numeric")

    @classmethod
    def _check_payload_arguments(
        cls,
        arguments: dict[str, StateExpression],
        schema: dict[str, str],
        state_types: dict[str, str],
        current_payload: dict[str, str],
    ) -> None:
        missing = schema.keys() - arguments.keys()
        extra = arguments.keys() - schema.keys()
        if extra:
            raise WorldTypeError(f"Unexpected event arguments: {sorted(extra)}")
        if missing:
            raise WorldTypeError(f"Missing event arguments: {sorted(missing)}")
        for name, expr in arguments.items():
            if isinstance(expr, SampleExpression):
                raise WorldTypeError("Sampling is only permitted in transitions")
            actual = cls._expression_type(expr, state_types, current_payload)
            if actual != schema[name]:
                if actual in cls.PRIMITIVES and schema[name] in cls.PRIMITIVES:
                    raise WorldTypeError(
                        f"Type mismatch in emitted argument '{name}': "
                        f"expected {schema[name]}, got {actual}",
                        code="FNL-T201",
                        expected=schema[name],
                        inferred=actual,
                        remediation=f"Ensure emitted argument '{name}' matches declared type {schema[name]}.",
                    )
                from funnelscript.compiler.dimensions import DimensionParser
                act_dim = DimensionParser.parse(actual)
                sch_dim = DimensionParser.parse(schema[name])
                if not act_dim.is_compatible_with(sch_dim):
                    raise WorldTypeError(
                        f"Type mismatch in emitted argument '{name}': "
                        f"expected {schema[name]}, got {actual}",
                        code="FNL-T201",
                        expected=schema[name],
                        inferred=actual,
                        remediation=f"Ensure emitted argument '{name}' matches declared type {schema[name]}.",
                    )

    @classmethod
    def _check_guard(cls, guard: GuardDefinition, types: dict[str, str]) -> None:
        type_name = types.get(guard.field)
        if type_name is None:
            raise WorldTypeError(f"Unknown guard field '{guard.field}'")
        expected = cls.PRIMITIVES.get(type_name)
        if expected is not None:
            if type(guard.value) is not expected:
                raise WorldTypeError(
                    f"Type mismatch in guard '{guard.field}': expected {type_name}"
                )
            if guard.operator in ("<", "<=", ">", ">=") and type_name not in ("int", "float"):
                raise WorldTypeError("Ordered guard comparisons require numeric types")
        else:
            from funnelscript.compiler.dimensions import DimensionParser
            dim = DimensionParser.parse(type_name)
            if dim.kind == "Bool":
                if type(guard.value) is not bool:
                    raise WorldTypeError(f"Type mismatch in guard '{guard.field}': expected bool")
            elif dim.kind == "String":
                if type(guard.value) is not str:
                    raise WorldTypeError(f"Type mismatch in guard '{guard.field}': expected string")
            else:
                if type(guard.value) not in (int, float):
                    raise WorldTypeError(f"Type mismatch in guard '{guard.field}': expected numeric {type_name}")

    @classmethod
    def _expression_type(
        cls, expr: StateExpression, types: dict[str, str],
        payload_types: dict[str, str] | None = None,
    ) -> str:
        if isinstance(expr, LiteralExpression):
            if type(expr.value) is float and not math.isfinite(expr.value):
                raise WorldTypeError("Non-finite float literal")
            for name, value_type in cls.PRIMITIVES.items():
                if type(expr.value) is value_type:
                    return name
            raise WorldTypeError("Unknown literal value type")
        if isinstance(expr, ReferenceExpression):
            if expr.name not in types:
                raise WorldTypeError(f"Unknown state reference '{expr.name}'")
            return types[expr.name]
        if isinstance(expr, PayloadFieldExpression):
            if expr.name not in (payload_types or {}):
                raise WorldTypeError(f"Unknown payload field '{expr.name}'")
            return payload_types[expr.name]
        if isinstance(expr, SampleExpression):
            return cls._sample_type(expr, types, payload_types or {})
        if isinstance(expr, CallExpression):
            return cls._call_type(expr, types, payload_types or {})
        if isinstance(expr, BinaryExpression):
            if cls._expression_depth(expr) > 24:
                raise WorldTypeError("Arithmetic expression depth limit exceeded")
            left_type = cls._expression_type(expr.left, types, payload_types)
            right_type = cls._expression_type(expr.right, types, payload_types)
            if left_type in ("bool", "string") or right_type in ("bool", "string"):
                raise WorldTypeError("Binary arithmetic requires numeric operands")
            if left_type in ("int", "float") and right_type in ("int", "float"):
                if left_type != right_type:
                    raise WorldTypeError(
                        f"Type mismatch in arithmetic: {left_type} versus {right_type}"
                    )
                if expr.operator == "/":
                    if isinstance(expr.right, LiteralExpression) and expr.right.value == 0:
                        raise WorldTypeError("Division by literal zero")
                    return "float"
                return left_type

            from funnelscript.compiler.dimensions import DimensionParser
            left_dim = DimensionParser.parse(left_type)
            right_dim = DimensionParser.parse(right_type)

            if expr.operator in ("+", "-"):
                if not left_dim.is_compatible_with(right_dim):
                    c_left = left_dim.get_currency_code()
                    c_right = right_dim.get_currency_code()
                    if c_left and c_right and c_left != c_right:
                        raise WorldTypeError(
                            f"Currency isolation violation: cannot perform '{expr.operator}' between distinct currencies {c_left} and {c_right}",
                            code="FNL-T202",
                            expected=str(left_dim),
                            inferred=str(right_dim),
                            remediation="Use an explicit exchange rate to convert currencies before adding/subtracting.",
                        )
                    raise WorldTypeError(
                        f"Dimensional mismatch in arithmetic: cannot perform '{expr.operator}' between {left_type} and {right_type}",
                        code="FNL-T201",
                        expected=str(left_dim),
                        inferred=str(right_dim),
                        remediation="Ensure operands share compatible physical/financial dimensions.",
                    )
                return left_type

            if expr.operator == "*":
                return str(left_dim * right_dim)

            if expr.operator == "/":
                if isinstance(expr.right, LiteralExpression) and expr.right.value == 0:
                    raise WorldTypeError("Division by literal zero")
                return str(left_dim / right_dim)

        raise WorldTypeError("Unknown state expression")

    @classmethod
    def _call_type(
        cls, expr: CallExpression, types: dict[str, str], payload_types: dict[str, str]
    ) -> str:
        from funnelscript.compiler.dimensions import DimensionParser
        fn = expr.function
        args = expr.arguments

        if fn == "hill":
            if len(args) not in (3, 4):
                raise WorldTypeError(f"hill() expects 3 or 4 arguments, got {len(args)}")
            s_type = cls._expression_type(args[0], types, payload_types)
            k_type = cls._expression_type(args[1], types, payload_types)
            alpha_type = cls._expression_type(args[2], types, payload_types)

            s_dim = DimensionParser.parse(s_type)
            k_dim = DimensionParser.parse(k_type)
            alpha_dim = DimensionParser.parse(alpha_type)

            if isinstance(args[1], LiteralExpression) and isinstance(args[1].value, (int, float)) and args[1].value <= 0:
                raise WorldTypeError(
                    f"Half-saturation constant K must be positive (> 0), got {args[1].value}",
                    code="FNL-T205",
                    expected="K > 0",
                    inferred=str(args[1].value),
                    remediation="Set K to a positive spend threshold.",
                )
            if isinstance(args[2], LiteralExpression) and isinstance(args[2].value, (int, float)) and args[2].value <= 0:
                raise WorldTypeError(
                    f"Hill slope parameter alpha must be positive (> 0), got {args[2].value}",
                    code="FNL-T205",
                    expected="alpha > 0",
                    inferred=str(args[2].value),
                    remediation="Set alpha curvature parameter > 0 (e.g. 0.8).",
                )

            if not s_dim.is_any() and not k_dim.is_any() and not k_dim.is_dimensionless() and not s_dim.is_compatible_with(k_dim):
                raise WorldTypeError(
                    f"Dimensional mismatch in hill(): spend S ({s_dim}) and half-saturation K ({k_dim}) must have identical dimensions",
                    code="FNL-T201",
                    expected=str(s_dim),
                    inferred=str(k_dim),
                    remediation="Ensure K has the same dimension and currency/time units as spend S.",
                )
            if not alpha_dim.is_any() and not alpha_dim.is_dimensionless():
                raise WorldTypeError(
                    f"Hill slope parameter alpha must be dimensionless Scalar, got {alpha_dim}",
                    code="FNL-T201",
                    expected="Scalar",
                    inferred=str(alpha_dim),
                    remediation="Alpha curvature parameter must be a dimensionless number.",
                )
            if len(args) == 4:
                vmax_type = cls._expression_type(args[3], types, payload_types)
                if vmax_type in ("int", "float"):
                    return "float"
                return vmax_type
            return "float"

        if fn == "adstock":
            if len(args) != 2:
                raise WorldTypeError(f"adstock() expects 2 arguments (spend, decay), got {len(args)}")
            s_type = cls._expression_type(args[0], types, payload_types)
            decay_type = cls._expression_type(args[1], types, payload_types)
            decay_dim = DimensionParser.parse(decay_type)

            if not decay_dim.is_any() and not decay_dim.is_dimensionless() and not decay_dim.is_prob():
                raise WorldTypeError(
                    f"Adstock decay parameter must be Prob in [0, 1), got {decay_dim}",
                    code="FNL-T201",
                    expected="Prob",
                    inferred=str(decay_dim),
                    remediation="Adstock decay rate must be a retention fraction in [0.0, 1.0).",
                )
            if isinstance(args[1], LiteralExpression) and isinstance(args[1].value, (int, float)):
                d_val = float(args[1].value)
                if not (0.0 <= d_val < 1.0):
                    raise WorldTypeError(
                        f"Adstock decay rate must be in [0.0, 1.0), got {d_val}",
                        code="FNL-T204",
                        expected="decay in [0.0, 1.0)",
                        inferred=str(d_val),
                        remediation="Clamp decay rate to [0.0, 1.0) to guarantee geometric convergence.",
                    )
            return s_type

        if fn in ("exp", "log", "sigmoid"):
            if len(args) != 1:
                raise WorldTypeError(f"{fn}() expects 1 argument, got {len(args)}")
            arg_type = cls._expression_type(args[0], types, payload_types)
            arg_dim = DimensionParser.parse(arg_type)
            if not arg_dim.is_any() and not arg_dim.is_dimensionless():
                raise WorldTypeError(
                    f"Non-dimensionless argument to transcendental function '{fn}': expected dimensionless scalar, got {arg_dim}",
                    code="FNL-T203",
                    expected="Dimensionless",
                    inferred=str(arg_dim),
                    remediation=f"Normalize or scale the argument to '{fn}' so it is strictly dimensionless.",
                )
            return "float"

        if fn == "fx_convert":
            if len(args) != 2:
                raise WorldTypeError(f"fx_convert() expects 2 arguments (amount, rate), got {len(args)}")
            amt_type = cls._expression_type(args[0], types, payload_types)
            rate_type = cls._expression_type(args[1], types, payload_types)
            amt_dim = DimensionParser.parse(amt_type)
            rate_dim = DimensionParser.parse(rate_type)
            return str(amt_dim * rate_dim)

        raise WorldTypeError(f"Unknown built-in function '{fn}' in expression")

    @staticmethod
    def _expression_depth(expr: StateExpression) -> int:
        if not isinstance(expr, BinaryExpression):
            return 1
        return 1 + max(WorldTypeChecker._expression_depth(expr.left),
                       WorldTypeChecker._expression_depth(expr.right))

    @classmethod
    def _sample_type(
        cls, expr: SampleExpression, types: dict[str, str], payload_types: dict[str, str]
    ) -> str:
        expected_count = 1 if expr.distribution == "bernoulli" else 2
        if len(expr.arguments) != expected_count:
            raise WorldTypeError(
                f"Invalid {expr.distribution} argument count: expected {expected_count}"
            )
        for argument in expr.arguments:
            if cls._expression_type(argument, types, payload_types) != "float":
                raise WorldTypeError("Distribution arguments must have exact float type")
            if isinstance(argument, LiteralExpression) and not math.isfinite(argument.value):
                raise WorldTypeError("Distribution arguments must be finite")
        literals = [
            argument.value if isinstance(argument, LiteralExpression) else None
            for argument in expr.arguments
        ]
        if expr.distribution == "bernoulli":
            if literals[0] is not None and not 0.0 <= literals[0] <= 1.0:
                raise WorldTypeError("Bernoulli probability must be in [0, 1]")
            return "bool"
        lower, upper = literals
        if lower is not None and upper is not None:
            if lower > upper:
                raise WorldTypeError("Uniform bounds must satisfy low <= high")
            if not math.isfinite(upper - lower):
                raise WorldTypeError("Uniform span must be finite")
        return "float"

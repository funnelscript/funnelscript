"""Bounded source diagnostics for schema validation and JSON parsing."""

from __future__ import annotations

import json
import linecache
from pathlib import Path

from pydantic import ValidationError

from funnelscript.tokens import SourceSpan, diagnostic_excerpt


class TraitConformanceError(ValueError):
    """Static Trait resolution, conformance, or dimensional invariant failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        span: SourceSpan | None = None,
        remediation: str = "Verify Trait implementation signatures and dimensional contracts.",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.span = span
        self.remediation = remediation

    def __str__(self) -> str:
        msg = super().__str__()
        if self.span is None:
            return f"{self.code}: {msg}\nHint: {self.remediation}"
        span = self.span
        line = linecache.getline(span.file, span.start_line).rstrip("\r\n")
        width = span.end_col - span.start_col if span.start_line == span.end_line else 1
        excerpt = diagnostic_excerpt(line, span.start_col, width) if line else ""
        return (
            f"{self.code} {span.file}: line {span.start_line}, column {span.start_col}\n"
            f"{excerpt}\nTraitConformanceError: {msg}\n"
            f"Hint: {self.remediation}"
        )


class DimensionalTypeError(ValueError):
    """Static compile-time dimensional algebra or unit verification failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        span: SourceSpan | None = None,
        expected: str | None = None,
        inferred: str | None = None,
        remediation: str = "Verify dimensional units and physical consistency.",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.span = span
        self.expected = expected
        self.inferred = inferred
        self.remediation = remediation

    def __str__(self) -> str:
        msg = super().__str__()
        extra = f"\n  Expected: {self.expected}\n  Inferred: {self.inferred}" if self.expected else ""
        if self.span is None:
            return f"{self.code}: {msg}{extra}\nHint: {self.remediation}"
        span = self.span
        line = linecache.getline(span.file, span.start_line).rstrip("\r\n")
        width = span.end_col - span.start_col if span.start_line == span.end_line else 1
        excerpt = diagnostic_excerpt(line, span.start_col, width) if line else ""
        return (
            f"{self.code} {span.file}: line {span.start_line}, column {span.start_col}\n"
            f"{excerpt}\nDimensionalTypeError: {msg}{extra}\n"
            f"Hint: {self.remediation}"
        )

MAX_VALIDATION_DIAGNOSTICS = 32


def _field_path(loc: tuple[str | int, ...]) -> str:
    result = ""
    for part in loc:
        if isinstance(part, int):
            result += f"[{part}]"
        elif part.isidentifier():
            result += f".{part}" if result else part
        else:
            result += f"[{json.dumps(part, ensure_ascii=True)}]"
    return result or "<root>"


def _validation_error(error: ValidationError, path: str | Path) -> str:
    items = error.errors(include_input=False, include_url=False, include_context=False)
    visible = items[:MAX_VALIDATION_DIAGNOSTICS]
    details = []
    for item in visible:
        location = _field_path(item["loc"])[:120]
        message = item["msg"][:180]
        details.append(f"  {location}: {message} [{item['type']}]")
    remaining = len(items) - len(visible)
    if remaining:
        details.append(f"  {remaining} further validation errors omitted")
    return "\n".join(
        [
            f"FNL-T202 {path}: {len(items)} validation error(s)",
            *details,
            "Hint: Correct the listed schema fields and recheck the input.",
            "Note: Field paths are structural; source line positions are unavailable.",
        ]
    )


def _json_syntax_error(error: json.JSONDecodeError, path: str | Path) -> str:
    lines = error.doc.splitlines()
    line = lines[error.lineno - 1] if error.lineno <= len(lines) else ""
    excerpt = diagnostic_excerpt(line, error.colno)
    return (
        f"FNL-E103 {path}\nline {error.lineno}, column {error.colno}\n"
        f"{excerpt}\nJSONDecodeError: {error.msg}\n"
        "Hint: Correct the JSON syntax at the marked character."
    )


def render_compiler_error(
    error: Exception, source_path: str | Path,
) -> str:
    """Render known decoder/schema errors without inventing source positions."""
    if isinstance(error, (TraitConformanceError, DimensionalTypeError)):
        return str(error)
    if isinstance(error, json.JSONDecodeError):
        return _json_syntax_error(error, source_path)
    if isinstance(error, ValidationError):
        return _validation_error(error, source_path)
    return str(error)

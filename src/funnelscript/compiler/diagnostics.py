"""Bounded source diagnostics for schema validation and JSON parsing."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from funnelscript.tokens import diagnostic_excerpt

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
    if isinstance(error, json.JSONDecodeError):
        return _json_syntax_error(error, source_path)
    if isinstance(error, ValidationError):
        return _validation_error(error, source_path)
    return str(error)

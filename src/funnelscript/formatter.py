"""Source code formatter for FunnelScript DSL and World declarations.

Research: docs/meta-ontology/02_IMPLEMENTATION_ROADMAP.md
Guarantees idempotent round-tripping: format_funnelscript(format_funnelscript(s)) == format_funnelscript(s)
"""

from __future__ import annotations

import re

from funnelscript.tokens import Lexer, TokenType


def format_funnelscript(source: str) -> str:
    """Format FunnelScript source code with canonical 2-space indentation and spacing."""
    stripped = source.strip()
    if not stripped:
        return ""

    tokens = Lexer(source).tokenize()
    if not tokens or (len(tokens) == 1 and tokens[0].type == TokenType.EOF):
        return ""

    lines: list[str] = []
    indent_level = 0
    current_line_tokens: list[str] = []

    def flush_line():
        nonlocal current_line_tokens
        if current_line_tokens:
            indent = "  " * indent_level
            line_str = " ".join(current_line_tokens)
            # Clean up whitespace before semicolons, commas, closing parens, etc.
            line_str = re.sub(r"\s+([,;:)\]])", r"\1", line_str)
            line_str = re.sub(r"([(<\$])\s+", r"\1", line_str)
            line_str = re.sub(r"\s+>", r">", line_str)
            line_str = re.sub(r"(\w+)\s+\(", r"\1(", line_str)
            line_str = re.sub(r"(\w+)\s+<", r"\1<", line_str)
            line_str = re.sub(r"(\w+)\s+\.\s+(\w+)", r"\1.\2", line_str)
            lines.append(f"{indent}{line_str}")
            current_line_tokens = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == TokenType.EOF:
            break

        val = str(tok.value)

        if tok.type == TokenType.LBRACE:
            current_line_tokens.append("{")
            flush_line()
            indent_level += 1
            i += 1
            continue

        if tok.type == TokenType.RBRACE:
            flush_line()
            indent_level = max(0, indent_level - 1)
            lines.append(f"{'  ' * indent_level}}}")
            i += 1
            continue

        if tok.type == TokenType.SEMICOLON:
            current_line_tokens.append(";")
            flush_line()
            i += 1
            continue

        if tok.type == TokenType.STRING:
            current_line_tokens.append(f'"{val}"')
            i += 1
            continue

        current_line_tokens.append(val)
        i += 1

    flush_line()
    return "\n".join(lines) + "\n"

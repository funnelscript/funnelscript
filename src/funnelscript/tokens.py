from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Keywords
    STRATEGY = auto()
    METADATA = auto()
    ENVIRONMENT = auto()
    ENTITIES = auto()
    BUDGET = auto()
    AUDIENCE = auto()
    TOUCHPOINT = auto()
    FLOW = auto()
    TRIGGER = auto()
    FROM = auto()
    VIA = auto()
    TO = auto()
    WHEN = auto()
    ELSE = auto()
    INVARIANTS = auto()
    SIMULATE = auto()

    # Literals & Identifiers
    IDENTIFIER = auto()
    NUMBER = auto()
    PERCENTAGE = auto()
    STRING = auto()
    DURATION = auto()

    # Operators & Delimiters
    ASSIGN = auto()
    COLON = auto()
    MINUS = auto()
    PLUS = auto()
    STAR = auto()
    SLASH = auto()
    DOTDOT = auto()
    DOT = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    SEMICOLON = auto()
    GTE = auto()
    LTE = auto()
    GT = auto()
    LT = auto()
    EQ = auto()
    NEQ = auto()
    ARROW = auto()       # ->
    FAT_ARROW = auto()   # =>

    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "strategy": TokenType.STRATEGY,
    "metadata": TokenType.METADATA,
    "environment": TokenType.ENVIRONMENT,
    "entities": TokenType.ENTITIES,
    "budget": TokenType.BUDGET,
    "audience": TokenType.AUDIENCE,
    "touchpoint": TokenType.TOUCHPOINT,
    "flow": TokenType.FLOW,
    "trigger": TokenType.TRIGGER,
    "from": TokenType.FROM,
    "via": TokenType.VIA,
    "to": TokenType.TO,
    "when": TokenType.WHEN,
    "else": TokenType.ELSE,
    "invariants": TokenType.INVARIANTS,
    "simulate": TokenType.SIMULATE,
}


@dataclass(frozen=True)
class SourceSpan:
    """Exclusive-end location of a token in its original source."""

    file: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str | float | int
    line: int
    column: int
    span: SourceSpan | None = None


def diagnostic_excerpt(source_line: str, column: int, width: int = 1) -> str:
    """Bound source excerpts while preserving the caret's actual column."""
    start = max(0, column - 1 - 64)
    fragment = source_line[start : start + 120]
    prefix = "..." if start else ""
    suffix = "..." if start + 120 < len(source_line) else ""
    caret = " " * (column - 1 - start + len(prefix)) + "^" * min(max(width, 1), 80)
    return f"{prefix}{fragment}{suffix}\n{caret}"


class LexerError(ValueError):
    def __init__(
        self, message: str, line: int, column: int, *,
        file: str = "<memory>", source_line: str | None = None,
    ):
        diagnostic = f"LexerError at line {line}, col {column}: {message}"
        if source_line is not None:
            diagnostic = (
                f"FNL-E101 {file}: line {line}, column {column}\n"
                f"{diagnostic_excerpt(source_line, column)}\n"
                f"{diagnostic}\nHint: Correct the invalid source character or literal."
            )
        super().__init__(diagnostic)
        self.line = line
        self.column = column
        self.file = file


class Lexer:
    """Lexical analyzer for FunnelScript DSL."""

    def __init__(self, source: str, *, file: str = "<memory>") -> None:
        self.source = source
        self.file = file
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def _emit(self, kind: TokenType, value: str | float, line: int, col: int) -> None:
        span = SourceSpan(self.file, line, col, self.line, self.col)
        self.tokens.append(Token(kind, value, line, col, span))

    def _error(self, message: str, line: int, col: int) -> LexerError:
        lines = self.source.splitlines()
        source_line = lines[line - 1] if 0 < line <= len(lines) else None
        return LexerError(
            message, line, col, file=self.file, source_line=source_line
        )

    def tokenize(self) -> list[Token]:
        length = len(self.source)

        while self.pos < length:
            char = self.source[self.pos]

            # Whitespace handling
            if char in " \t\r":
                self._advance()
                continue
            if char == "\n":
                self.line += 1
                self.col = 1
                self.pos += 1
                continue

            # Strip comments (# or //)
            if char == "#" or (char == "/" and self.pos + 1 < length and self.source[self.pos + 1] == "/"):
                while self.pos < length and self.source[self.pos] != "\n":
                    self.pos += 1
                continue

            # Multi-character symbols
            if char == "." and self.pos + 1 < length and self.source[self.pos + 1] == ".":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.DOTDOT, "..", line, col)
                continue
            if char == ">" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.GTE, ">=", line, col)
                continue
            if char == "<" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.LTE, "<=", line, col)
                continue
            if char == "=" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.EQ, "==", line, col)
                continue
            if char == "=" and self.pos + 1 < length and self.source[self.pos + 1] == ">":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.FAT_ARROW, "=>", line, col)
                continue
            if char == "-" and self.pos + 1 < length and self.source[self.pos + 1] == ">":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.ARROW, "->", line, col)
                continue
            if char == "!" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                line, col = self.line, self.col
                self._advance(2)
                self._emit(TokenType.NEQ, "!=", line, col)
                continue

            # Single-character delimiters
            delimiters = {
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                ",": TokenType.COMMA,
                ";": TokenType.SEMICOLON,
                "=": TokenType.ASSIGN,
                ":": TokenType.COLON,
                "-": TokenType.MINUS,
                "+": TokenType.PLUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                ">": TokenType.GT,
                "<": TokenType.LT,
                ".": TokenType.DOT,
            }
            if char in delimiters:
                line, col = self.line, self.col
                self._advance()
                self._emit(delimiters[char], char, line, col)
                continue

            # Strings
            if char in ('"', "'"):
                self._lex_string(char)
                continue

            # Numbers / Durations / Percentages
            if char.isdigit():
                self._lex_number_or_duration()
                continue

            # Identifiers and Keywords
            if char.isalpha() or char == "_":
                self._lex_identifier()
                continue

            raise self._error(f"Unexpected character '{char}'", self.line, self.col)

        self._emit(TokenType.EOF, "", self.line, self.col)
        return self.tokens

    def _advance(self, count: int = 1) -> None:
        self.pos += count
        self.col += count

    def _lex_string(self, quote: str) -> None:
        start_line = self.line
        start_col = self.col
        self._advance()  # Skip opening quote
        chars: list[str] = []

        while self.pos < len(self.source) and self.source[self.pos] != quote:
            if self.source[self.pos] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            chars.append(self.source[self.pos])
            self.pos += 1

        if self.pos >= len(self.source):
            raise self._error("Unterminated string literal", start_line, start_col)

        self._advance()  # Skip closing quote
        self._emit(TokenType.STRING, "".join(chars), start_line, start_col)

    def _lex_number_or_duration(self) -> None:
        start_col = self.col
        start_pos = self.pos

        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == "."):
            # Avoid consuming .. as a float
            if self.source[self.pos] == "." and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == ".":
                break
            self.pos += 1
            self.col += 1

        num_str = self.source[start_pos : self.pos]
        try:
            val: int | float = float(num_str) if "." in num_str else int(num_str)
        except (ValueError, OverflowError) as exc:
            raise self._error("Invalid numeric literal", self.line, start_col) from exc
        if isinstance(val, float) and not math.isfinite(val):
            raise self._error("Non-finite float literal", self.line, start_col)

        # Check for percentage (e.g., 40%)
        if self.pos < len(self.source) and self.source[self.pos] == "%":
            try:
                percentage = float(val) / 100.0
            except (ValueError, OverflowError) as exc:
                raise self._error("Percentage literal out of range", self.line, start_col) from exc
            if not math.isfinite(percentage):
                raise self._error("Percentage literal out of range", self.line, start_col)
            self.pos += 1
            self.col += 1
            self._emit(TokenType.PERCENTAGE, percentage, self.line, start_col)
            return

        # Check for duration suffixes (e.g., 2h, 14d, 30m)
        duration_match = re.match(r"^([a-zA-Z]+)", self.source[self.pos :])
        if duration_match:
            suffix = duration_match.group(1)
            if suffix in ("h", "hours", "d", "days", "w", "weeks", "m", "months"):
                self.pos += len(suffix)
                self.col += len(suffix)
                self._emit(TokenType.DURATION, f"{val}{suffix}", self.line, start_col)
                return

        self._emit(TokenType.NUMBER, val, self.line, start_col)

    def _lex_identifier(self) -> None:
        start_col = self.col
        start_pos = self.pos

        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self.pos += 1
            self.col += 1

        ident = self.source[start_pos : self.pos]
        token_type = KEYWORDS.get(ident, TokenType.IDENTIFIER)
        self._emit(token_type, ident, self.line, start_col)

from __future__ import annotations

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
    DOTDOT = auto()
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
    EQ = auto()
    NEQ = auto()

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
class Token:
    type: TokenType
    value: str | float | int
    line: int
    column: int


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"LexerError at line {line}, col {column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    """Lexical analyzer for FunnelScript DSL."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

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
                self.tokens.append(Token(TokenType.DOTDOT, "..", self.line, self.col))
                self._advance(2)
                continue
            if char == ">" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                self.tokens.append(Token(TokenType.GTE, ">=", self.line, self.col))
                self._advance(2)
                continue
            if char == "<" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                self.tokens.append(Token(TokenType.LTE, "<=", self.line, self.col))
                self._advance(2)
                continue
            if char == "=" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                self.tokens.append(Token(TokenType.EQ, "==", self.line, self.col))
                self._advance(2)
                continue
            if char == "!" and self.pos + 1 < length and self.source[self.pos + 1] == "=":
                self.tokens.append(Token(TokenType.NEQ, "!=", self.line, self.col))
                self._advance(2)
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
            }
            if char in delimiters:
                self.tokens.append(Token(delimiters[char], char, self.line, self.col))
                self._advance()
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

            raise LexerError(f"Unexpected character '{char}'", self.line, self.col)

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
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
            chars.append(self.source[self.pos])
            self.pos += 1
            self.col += 1

        if self.pos >= len(self.source):
            raise LexerError("Unterminated string literal", start_line, start_col)

        self._advance()  # Skip closing quote
        self.tokens.append(Token(TokenType.STRING, "".join(chars), start_line, start_col))

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
        val: int | float = float(num_str) if "." in num_str else int(num_str)

        # Check for percentage (e.g., 40%)
        if self.pos < len(self.source) and self.source[self.pos] == "%":
            self.pos += 1
            self.col += 1
            self.tokens.append(Token(TokenType.PERCENTAGE, float(val) / 100.0, self.line, start_col))
            return

        # Check for duration suffixes (e.g., 2h, 14d, 30m)
        duration_match = re.match(r"^([a-zA-Z]+)", self.source[self.pos :])
        if duration_match:
            suffix = duration_match.group(1)
            if suffix in ("h", "hours", "d", "days", "w", "weeks", "m", "months"):
                self.pos += len(suffix)
                self.col += len(suffix)
                self.tokens.append(Token(TokenType.DURATION, f"{val}{suffix}", self.line, start_col))
                return

        self.tokens.append(Token(TokenType.NUMBER, val, self.line, start_col))

    def _lex_identifier(self) -> None:
        start_col = self.col
        start_pos = self.pos

        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self.pos += 1
            self.col += 1

        ident = self.source[start_pos : self.pos]
        token_type = KEYWORDS.get(ident, TokenType.IDENTIFIER)
        self.tokens.append(Token(token_type, ident, self.line, start_col))

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from funnelscript.models import StrategyAST
from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker
from funnelscript.tokens import Lexer, Token, TokenType


class ParserError(Exception):
    def __init__(self, message: str, token: Token | None = None) -> None:
        if token:
            super().__init__(f"ParserError at line {token.line}, col {token.column}: {message}")
        else:
            super().__init__(f"ParserError: {message}")
        self.token = token


class Parser:
    """Parses FunnelScript textual syntax or JSON Intermediate Representation."""

    @staticmethod
    def from_json_str(raw_json: str) -> StrategyAST:
        """Parses and type-checks a JSON AST string."""
        data = json.loads(raw_json)
        return StrategyAST.model_validate(data)

    @staticmethod
    def from_file(file_path: str | Path) -> StrategyAST | WorldAST:
        """Loads and parses a legacy strategy or a domain-neutral world."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Strategy file not found: {path}")

        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return Parser.from_json_str(content)

        lexer = Lexer(content)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        if tokens[0].type == TokenType.IDENTIFIER and tokens[0].value == "world":
            return parser.parse_world()
        return parser.parse_strategy()

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]

    def peek(self) -> Token | None:
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        return None

    def match(self, token_type: TokenType) -> bool:
        if self.current().type == token_type:
            self.pos += 1
            return True
        return False

    def expect(self, token_type: TokenType, message: str | None = None) -> Token:
        curr = self.current()
        if curr.type != token_type:
            msg = message or f"Expected token {token_type.name}, found {curr.type.name} ('{curr.value}')"
            raise ParserError(msg, curr)
        self.pos += 1
        return curr

    def parse_strategy(self) -> StrategyAST:
        self.expect(TokenType.STRATEGY, "Strategy declaration must start with 'strategy'")
        name_tok = self.expect(TokenType.IDENTIFIER, "Expected strategy identifier")
        self.expect(TokenType.LBRACE, "Expected '{' after strategy name")

        metadata: dict[str, Any] = {}
        environment: dict[str, Any] = {}
        entities_data: dict[str, Any] = {"budgets": {"total_budget": 10000.0}, "audiences": [], "touchpoints": []}
        logic_flow: list[Any] = []
        sim_params: dict[str, Any] = {}

        while not self.match(TokenType.RBRACE) and not self.match(TokenType.EOF):
            tok = self.current()
            if self.match(TokenType.METADATA):
                metadata = self._parse_block_map()
            elif self.match(TokenType.ENVIRONMENT):
                environment = self._parse_block_map()
            elif self.match(TokenType.ENTITIES):
                self.expect(TokenType.LBRACE)
                while not self.match(TokenType.RBRACE) and not self.match(TokenType.EOF):
                    if self.match(TokenType.BUDGET):
                        entities_data["budgets"] = self._parse_budget()
                    elif self.match(TokenType.AUDIENCE):
                        entities_data["audiences"].append(self._parse_audience())
                    elif self.match(TokenType.TOUCHPOINT):
                        entities_data["touchpoints"].append(self._parse_touchpoint())
                    else:
                        raise ParserError(f"Unexpected token in entities block: {self.current().value}", self.current())
            elif self.match(TokenType.FLOW):
                logic_flow = self._parse_flow()
            elif self.match(TokenType.SIMULATE):
                sim_params = self._parse_block_map()
            else:
                self.pos += 1

        ast_dict = {
            "strategy_name": str(name_tok.value),
            "metadata": metadata,
            "environment": environment,
            "entities": entities_data,
            "logic_flow": logic_flow,
            "simulation_engine": {"parameters": sim_params} if sim_params else {},
        }
        return StrategyAST.model_validate(ast_dict)

    def _parse_block_map(self) -> dict[str, Any]:
        self.expect(TokenType.LBRACE)
        res: dict[str, Any] = {}
        while not self.match(TokenType.RBRACE) and not self.match(TokenType.EOF):
            key_tok = self.expect(TokenType.IDENTIFIER)
            self.expect(TokenType.ASSIGN)
            val = self.current().value
            self.pos += 1
            res[str(key_tok.value)] = val
            self.match(TokenType.SEMICOLON)
        return res

    def _parse_budget(self) -> dict[str, Any]:
        name_tok = self.expect(TokenType.IDENTIFIER)
        block = self._parse_block_map()
        return {
            "total_budget": float(block.get("total", block.get("total_budget", 10000.0))),
            "max_cpc_limit": float(block.get("max_cpc", block.get("max_cpc_limit", 2.0))),
        }

    def _parse_audience(self) -> dict[str, Any]:
        name_tok = self.expect(TokenType.IDENTIFIER)
        block = self._parse_block_map()
        return {
            "id": str(name_tok.value),
            "name": str(name_tok.value),
            "type": str(block.get("type", "cold")),
            "estimated_size": int(block.get("size", 100000)),
            "attributes": {
                "brand_affinity": float(block.get("affinity", 0.5)),
                "price_sensitivity": float(block.get("price_sensitivity", 0.5)),
                "fomo_index": float(block.get("fomo", 0.5)),
            },
        }

    def _parse_touchpoint(self) -> dict[str, Any]:
        name_tok = self.expect(TokenType.IDENTIFIER)
        block = self._parse_block_map()
        return {
            "id": str(name_tok.value),
            "type": str(block.get("type", "paid_traffic")),
            "platform": block.get("platform"),
            "base_cpc": float(block.get("base_cpc", 0.50)),
            "ad_creative_score": float(block.get("creative_score", 0.80)),
            "base_conversion_rate": float(block.get("conversion_rate", 0.03)),
        }

    def _parse_flow(self) -> list[Any]:
        self.expect(TokenType.LBRACE)
        steps: list[Any] = []
        step_counter = 1
        while not self.match(TokenType.RBRACE) and not self.match(TokenType.EOF):
            if self.match(TokenType.TRIGGER):
                trigger_name = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.FROM)
                src = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.VIA)
                via = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.TO)
                dest = self.expect(TokenType.IDENTIFIER).value
                self.match(TokenType.SEMICOLON)
                steps.append(
                    {
                        "step": step_counter,
                        "action": "TriggerTraffic",
                        "source": str(src),
                        "via": str(via),
                        "destination": str(dest),
                    }
                )
                step_counter += 1
            else:
                self.pos += 1
        return steps


    def parse_world(self) -> WorldAST:
        """Parse a standalone domain-neutral world into a typed declaration AST."""
        start = self.expect(TokenType.IDENTIFIER)
        if start.value != "world":
            raise ParserError("Expected world declaration", start)
        name = str(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.LBRACE)
        declarations: list[dict[str, Any]] = []

        while self.current().type != TokenType.RBRACE:
            if self.current().type == TokenType.EOF:
                raise ParserError("Unclosed world declaration", self.current())
            kind = self.expect(TokenType.IDENTIFIER)
            if kind.value not in ("entity", "agent"):
                raise ParserError("Expected entity or agent declaration", kind)
            decl_name = str(self.expect(TokenType.IDENTIFIER).value)
            self.expect(TokenType.LBRACE)
            states = self._parse_world_states()
            self.expect(TokenType.RBRACE)
            declarations.append({"kind": kind.value, "name": decl_name, "states": states})

        self.expect(TokenType.RBRACE)
        self.expect(TokenType.EOF, "Unexpected content after world declaration")
        ast = WorldAST.model_validate({"name": name, "declarations": declarations})
        WorldTypeChecker.check(ast)
        return ast

    def _parse_world_states(self) -> list[dict[str, Any]]:
        states: list[dict[str, Any]] = []
        while self.current().type != TokenType.RBRACE:
            if self.current().type == TokenType.EOF:
                raise ParserError("Unclosed entity or agent", self.current())
            keyword = self.expect(TokenType.IDENTIFIER)
            if keyword.value != "state":
                raise ParserError("Expected state declaration", keyword)
            field_name = str(self.expect(TokenType.IDENTIFIER).value)
            self.expect(TokenType.COLON)
            type_name = str(self.expect(TokenType.IDENTIFIER).value)
            self.expect(TokenType.ASSIGN)
            value = self._parse_world_literal()
            self.expect(TokenType.SEMICOLON)
            states.append({"name": field_name, "type_name": type_name, "value": value})
        return states

    def _parse_world_literal(self) -> int | float | bool | str:
        negative = self.match(TokenType.MINUS)
        tok = self.current()
        if tok.type == TokenType.NUMBER:
            self.pos += 1
            return -tok.value if negative else tok.value
        if negative:
            raise ParserError("Unary minus requires a number", tok)
        if tok.type == TokenType.STRING:
            self.pos += 1
            return str(tok.value)
        if tok.type == TokenType.IDENTIFIER and tok.value in ("true", "false"):
            self.pos += 1
            return tok.value == "true"
        raise ParserError("Expected state literal", tok)

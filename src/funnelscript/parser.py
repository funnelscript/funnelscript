from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from funnelscript.compiler.world_ast import (
    AgentDefinition,
    EntityDefinition,
    TraitDefinition,
    WorldAST,
    WorldTypeChecker,
)
from funnelscript.models import StrategyAST
from funnelscript.tokens import Lexer, SourceSpan, Token, TokenType, diagnostic_excerpt


class ParserError(Exception):
    def __init__(self, message: str, token: Token | None = None) -> None:
        if token:
            diagnostic = f"ParserError at line {token.line}, col {token.column}: {message}"
            if token.span is not None and token.span.file != "<memory>":
                path = Path(token.span.file)
                try:
                    with path.open(encoding="utf-8") as source:
                        line = next(
                            (text.rstrip("\n") for i, text in enumerate(source, start=1)
                             if i == token.span.start_line),
                            None,
                        )
                except (OSError, UnicodeError):
                    line = None
                if line is not None:
                    width = (token.span.end_col - token.span.start_col
                             if token.span.start_line == token.span.end_line else 1)
                    excerpt = diagnostic_excerpt(line, token.span.start_col, width)
                    diagnostic = (
                        f"FNL-E102 {path}: line {token.span.start_line}, "
                        f"column {token.span.start_col}\n"
                        f"{excerpt}\n"
                        f"{diagnostic}\nHint: Check the expected syntax at this location."
                    )
            super().__init__(diagnostic)
        else:
            super().__init__(f"ParserError: {message}")
        self.token = token


class ParserErrors(ParserError):
    """Multiple recoverable syntax errors from one World source."""

    def __init__(self, errors: list[ParserError], *, truncated: bool = False) -> None:
        self.errors = tuple(errors)
        suffix = " (diagnostic limit reached)" if truncated else ""
        details = "\n\n".join(str(error) for error in errors)
        super().__init__(f"{len(errors)} syntax errors{suffix}:\n\n{details}")


class Parser:
    """Parses FunnelScript textual syntax or JSON Intermediate Representation."""

    @staticmethod
    def from_json_str(raw_json: str) -> StrategyAST:
        """Parses and type-checks a JSON AST string."""
        data = json.loads(raw_json)
        return StrategyAST.model_validate(data)

    @staticmethod
    def from_file(file_path: str | Path) -> StrategyAST | WorldAST:
        """Load and validate a strategy or compile a World with local imports."""
        return Parser._load_file(Path(file_path), ())

    @staticmethod
    def _load_file(
        path: Path, ancestors: tuple[Path, ...],
        via: Token | None = None,
    ) -> StrategyAST | WorldAST:
        resolved = path.resolve()
        if resolved in ancestors:
            cycle = (*ancestors[ancestors.index(resolved):], resolved)
            trace = " -> ".join(str(module) for module in cycle)
            raise ParserError(f"Cyclic World module import: {trace}", via)
        if len(ancestors) >= 16:
            raise ParserError("World module import depth limit exceeded")
        if not resolved.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")
        content = resolved.read_text(encoding="utf-8")
        if resolved.suffix.lower() == ".json":
            return Parser.from_json_str(content)
        tokens = Lexer(content, file=str(resolved)).tokenize()
        parser = Parser(tokens)
        if tokens[0].type == TokenType.IDENTIFIER and tokens[0].value == "world":
            return parser.parse_world(
                source_path=resolved, ancestors=ancestors + (resolved,)
            )
        return parser.parse_strategy()

    @staticmethod
    def _module_path(reference: str, source_path: Path) -> Path:
        if not reference or "\\" in reference:
            raise ParserError("Invalid World module path")
        if reference.startswith("std:"):
            root = Path(__file__).resolve().parent / "stdlib"
            fragment = reference.removeprefix("std:")
            relative = Path(fragment)
            if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".fnls":
                raise ParserError("Invalid World module path")
            resolved = (root / relative).resolve()
            if not resolved.is_relative_to(root.resolve()):
                raise ParserError("World module path escapes the allowed directory")
            if not resolved.is_file():
                raise ParserError("World module not found")
            return resolved

        # Direct .fnls file reference relative to source_path.parent
        if reference.endswith(".fnls"):
            root = source_path.parent
            relative = Path(reference)
            if relative.is_absolute() or ".." in relative.parts:
                raise ParserError("Invalid World module path")
            resolved = (root / relative).resolve()
            if not resolved.is_relative_to(root.resolve()):
                raise ParserError("World module path escapes the allowed directory")
            if not resolved.is_file():
                raise ParserError("World module not found")
            return resolved

        # Package reference (e.g. "ecommerce/d2c_scale" or "@scope/pkg")
        pkg_rel = Path(reference)
        if pkg_rel.is_absolute() or ".." in pkg_rel.parts:
            raise ParserError("Invalid World module path")

        # 1. Resolve via .fpm/resolution-map.json if present
        curr_fpm = source_path.parent.resolve()
        for _ in range(6):
            map_file = curr_fpm / ".fpm" / "resolution-map.json"
            if map_file.is_file():
                try:
                    res_map = json.loads(map_file.read_text(encoding="utf-8"))
                    packages = res_map.get("packages", {})
                    parts = reference.split("/", 2)
                    pkg_key = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else parts[0]
                    if pkg_key in packages:
                        pkg_info = packages[pkg_key]
                        if len(parts) == 3 and "modules" in pkg_info and parts[2] in pkg_info["modules"]:
                            target = Path(pkg_info["modules"][parts[2]]).resolve()
                            if target.is_file():
                                return target
                        elif "entry" in pkg_info:
                            target = Path(pkg_info["entry"]).resolve()
                            if target.is_file():
                                return target
                except (json.JSONDecodeError, OSError, KeyError):
                    pass
            if curr_fpm.parent == curr_fpm:
                break
            curr_fpm = curr_fpm.parent

        search_dirs: list[Path] = [
            source_path.parent,
            source_path.parent / ".funnelscript_modules",
            source_path.parent / "packages",
            source_path.parent / "fpm",
        ]
        curr = source_path.parent.resolve()
        for _ in range(5):
            search_dirs.extend([
                curr / ".funnelscript_modules",
                curr / "packages",
                curr / "fpm",
            ])
            if curr.parent == curr:
                break
            curr = curr.parent

        repo_root = Path(__file__).resolve().parents[2]
        search_dirs.extend([
            repo_root / "packages",
            repo_root / "fpm",
            repo_root.parent / "fpm",
            Path(__file__).resolve().parent / "stdlib",
        ])

        for cand_root in search_dirs:
            if not cand_root.is_dir():
                continue
            pkg_dir = (cand_root / pkg_rel).resolve()
            if pkg_dir.is_dir() and pkg_dir.is_relative_to(cand_root.resolve()):
                entry_filename = "index.fnls"
                manifest_json = pkg_dir / "manifest.json"
                funnel_json = pkg_dir / "funnelscript.json"
                fpm_toml = pkg_dir / "fpm.toml"
                if fpm_toml.is_file():
                    try:
                        import tomllib
                        with fpm_toml.open("rb") as f:
                            toml_data = tomllib.load(f)
                        entry_filename = toml_data.get("package", {}).get("main", entry_filename)
                    except (tomllib.TOMLDecodeError, OSError, KeyError):
                        entry_filename = "index.fnls"
                elif manifest_json.is_file():
                    try:
                        data = json.loads(manifest_json.read_text(encoding="utf-8"))
                        entry_filename = data.get("main", entry_filename)
                    except (json.JSONDecodeError, OSError, KeyError):
                        entry_filename = "index.fnls"
                elif funnel_json.is_file():
                    try:
                        data = json.loads(funnel_json.read_text(encoding="utf-8"))
                        entry_filename = data.get("main", entry_filename)
                    except (json.JSONDecodeError, OSError, KeyError):
                        entry_filename = "index.fnls"
                entry_file = (pkg_dir / entry_filename).resolve()
                if entry_file.is_file() and entry_file.is_relative_to(pkg_dir):
                    return entry_file
            cand_fnls = (cand_root / f"{reference}.fnls").resolve()
            if cand_fnls.is_file() and cand_fnls.is_relative_to(cand_root.resolve()):
                return cand_fnls

        raise ParserError("World module not found")

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        if self.tokens and self.tokens[-1].type == TokenType.EOF:
            return self.tokens[-1]
        raise ParserError("Unexpected end of token stream", self.tokens[-1] if self.tokens else None)

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
        self.expect(TokenType.IDENTIFIER)
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
                self.expect(TokenType.IDENTIFIER)
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


    def _record_world_error(self, error: ParserError) -> None:
        self._world_errors.append(error)
        if len(self._world_errors) == 32:
            raise ParserErrors(self._world_errors, truncated=True) from None

    def _raise_world_errors(self) -> None:
        if len(self._world_errors) == 1:
            raise self._world_errors[0]
        if self._world_errors:
            raise ParserErrors(self._world_errors)

    def _recover_world(self, start: int, starters: frozenset[str]) -> None:
        """Resume at a grammar boundary outside nested expressions and blocks."""
        parentheses = blocks = 0
        for index in range(start, len(self.tokens)):
            token = self.tokens[index]
            if index >= self.pos:
                if token.type == TokenType.EOF:
                    self.pos = index
                    return
                if blocks == 0 and token.type == TokenType.RBRACE:
                    self.pos = index
                    return
                if blocks == 0 and parentheses == 0:
                    if token.type == TokenType.SEMICOLON:
                        self.pos = index + 1
                        return
                    if token.type == TokenType.IDENTIFIER and token.value in starters:
                        self.pos = index
                        return
            if token.type == TokenType.LPAREN:
                parentheses += 1
            elif token.type == TokenType.RPAREN:
                parentheses = max(0, parentheses - 1)
            elif token.type == TokenType.LBRACE:
                blocks += 1
            elif token.type == TokenType.RBRACE:
                blocks = max(0, blocks - 1)
        self.pos = len(self.tokens)

    def _node_span(self, start: int) -> SourceSpan | None:
        if not 0 <= start < self.pos <= len(self.tokens):
            return None
        first = self.tokens[start].span
        last = self.tokens[self.pos - 1].span
        if first is None or last is None:
            return None
        return SourceSpan(
            first.file, first.start_line, first.start_col,
            last.end_line, last.end_col,
        )

    def parse_world(
        self, *, source_path: Path | None = None,
        ancestors: tuple[Path, ...] = (),
    ) -> WorldAST:
        """Parse a World and compile imported one-declaration modules."""
        self._world_errors: list[ParserError] = []
        world_start = self.pos
        start = self.expect(TokenType.IDENTIFIER)
        if start.value != "world":
            raise ParserError("Expected world declaration", start)
        name = str(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.LBRACE)
        declarations: list[dict[str, Any] | EntityDefinition | AgentDefinition] = []
        imports: list[tuple[str, list[tuple[str | None, str]], Token]] = []
        while self.current().type != TokenType.RBRACE:
            declaration_start = self.pos
            if self.current().type == TokenType.EOF:
                self._record_world_error(ParserError("Unclosed world declaration", self.current()))
                self._raise_world_errors()
            try:
                self._parse_world_declaration(declarations, imports)
            except ParserErrors:
                raise
            except ParserError as error:
                self._record_world_error(error)
                self._recover_world(declaration_start, frozenset({"entity", "agent", "import"}))

        self.expect(TokenType.RBRACE)
        world_span = self._node_span(world_start)
        try:
            self.expect(TokenType.EOF, "Unexpected content after world declaration")
        except ParserError as error:
            self._record_world_error(error)
        self._raise_world_errors()

        if imports and source_path is None:
            raise ParserError("World module imports require a source file path")
        for reference, selected, source_token in imports:
            path = self._module_path(reference, source_path)
            module = self._load_file(path, ancestors, via=source_token)
            if not isinstance(module, WorldAST):
                raise ParserError("World module must contain a world declaration")
            if selected[0][0] is None:
                alias = selected[0][1]
                if len(module.declarations) == 1:
                    imported = module.declarations[0].model_copy(deep=True)
                    imported.name = alias
                    declarations.append(imported)
                elif not reference.endswith(".fnls"):
                    for item in module.declarations:
                        imported = item.model_copy(deep=True)
                        imported.name = f"{alias}.{item.name}"
                        declarations.append(imported)
                else:
                    raise ParserError("World module must export exactly one declaration")
            else:
                exported = {item.name: item for item in module.declarations}
                for symbol, alias in selected:
                    if symbol not in exported:
                        raise ParserError(f"Unknown World module export '{symbol}'", source_token)
                    imported = exported[symbol].model_copy(deep=True)
                    imported.name = alias
                    declarations.append(imported)
        ast = WorldAST.model_validate(
            {"name": name, "declarations": declarations, "span": world_span}
        )
        WorldTypeChecker.check(ast)
        return ast

    def _parse_world_declaration(
        self,
        declarations: list[dict[str, Any] | EntityDefinition | AgentDefinition | TraitDefinition],
        imports: list[tuple[str, list[tuple[str | None, str]], Token]],
    ) -> None:
        declaration_start = self.pos
        kind = self.expect(TokenType.IDENTIFIER)
        if kind.value == "import":
            source_token = self.expect(TokenType.STRING)
            selected = self._parse_import_bindings()
            self.expect(TokenType.SEMICOLON)
            imports.append((str(source_token.value), selected, source_token))
            return
        if kind.value == "trait":
            trait_name = str(self.expect(TokenType.IDENTIFIER).value)
            self.expect(TokenType.LBRACE)
            members = self._parse_trait_members()
            self.expect(TokenType.RBRACE)
            declarations.append({
                "kind": "trait",
                "name": trait_name,
                "members": members,
                "span": self._node_span(declaration_start),
            })
            return
        if kind.value not in ("entity", "agent"):
            raise ParserError("Expected entity, agent, trait or import declaration", kind)
        decl_name = str(self.expect(TokenType.IDENTIFIER).value)
        implements_traits: list[str] = []
        if self.current().type == TokenType.IDENTIFIER and self.current().value == "extends":
            extends_tok = self.current()
            raise ParserError(
                "FNL-O305: Unsupported class inheritance ('extends'). "
                "FunnelScript supports flat composition via 'implements' only.",
                extends_tok,
            )
        if self.current().type == TokenType.IDENTIFIER and self.current().value == "implements":
            self.pos += 1
            while True:
                trait_ref = self._parse_trait_ref()
                implements_traits.append(trait_ref)
                if not self.match(TokenType.COMMA):
                    break
        self.expect(TokenType.LBRACE)
        states, primitives, events, rules, handlers = self._parse_world_members()
        self.expect(TokenType.RBRACE)
        declarations.append({
            "kind": kind.value,
            "name": decl_name,
            "implements": implements_traits,
            "states": states,
            "primitives": primitives,
            "events": events,
            "rules": rules,
            "handlers": handlers,
            "span": self._node_span(declaration_start),
        })

    def _parse_trait_ref(self) -> str:
        ident = str(self.expect(TokenType.IDENTIFIER).value)
        if self.match(TokenType.DOT):
            member = str(self.expect(TokenType.IDENTIFIER).value)
            return f"{ident}.{member}"
        return ident

    def _parse_type_expression(self) -> str:
        tok = self.current()
        if tok.type not in (TokenType.IDENTIFIER, TokenType.FLOW):
            raise ParserError("Expected type identifier", tok)
        parts = [str(tok.value)]
        self.pos += 1
        if self.current().type == TokenType.DOT:
            self.pos += 1
            parts.append("." + str(self.expect(TokenType.IDENTIFIER).value))
        if self.current().type == TokenType.LT:
            self.pos += 1
            parts.append("<")
            depth = 1
            while depth > 0 and self.current().type != TokenType.EOF:
                c = self.current()
                if c.type == TokenType.LT:
                    depth += 1
                    parts.append("<")
                elif c.type == TokenType.GT:
                    depth -= 1
                    parts.append(">")
                    self.pos += 1
                    continue
                else:
                    parts.append(str(c.value))
                self.pos += 1
        return "".join(parts)

    def _parse_trait_members(self) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        while self.current().type != TokenType.RBRACE:
            if self.current().type == TokenType.EOF:
                self._record_world_error(ParserError("Unclosed trait declaration", self.current()))
                self._raise_world_errors()
            member_start = self.pos
            tok = self.expect(TokenType.IDENTIFIER)
            name = str(tok.value)
            if name.startswith("on_") and self.current().type == TokenType.LPAREN:
                self.expect(TokenType.LPAREN)
                params: list[dict[str, Any]] = []
                if self.current().type != TokenType.RPAREN:
                    while True:
                        param_start = self.pos
                        pname = str(self.expect(TokenType.IDENTIFIER).value)
                        self.expect(TokenType.COLON)
                        ptype = self._parse_type_expression()
                        params.append({
                            "name": pname,
                            "type_name": ptype,
                            "span": self._node_span(param_start),
                        })
                        if not self.match(TokenType.COMMA):
                            break
                self.expect(TokenType.RPAREN)
                self.expect(TokenType.SEMICOLON)
                members.append({
                    "kind": "handler",
                    "name": name,
                    "parameters": params,
                    "span": self._node_span(member_start),
                })
            else:
                self.expect(TokenType.COLON)
                type_spec = self._parse_type_expression()
                self.expect(TokenType.SEMICOLON)
                members.append({
                    "kind": "field",
                    "name": name,
                    "type_name": type_spec,
                    "span": self._node_span(member_start),
                })
        return members

    def _parse_import_bindings(self) -> list[tuple[str | None, str]]:
        if self.match(TokenType.LBRACE):
            selected: list[tuple[str | None, str]] = []
            if self.current().type == TokenType.RBRACE:
                raise ParserError("Named World module import cannot be empty", self.current())
            while True:
                symbol = str(self.expect(TokenType.IDENTIFIER).value)
                alias = symbol
                if self.current().type == TokenType.IDENTIFIER and self.current().value == "as":
                    self.pos += 1
                    alias = str(self.expect(TokenType.IDENTIFIER).value)
                selected.append((symbol, alias))
                if not self.match(TokenType.COMMA):
                    break
            self.expect(TokenType.RBRACE)
            return selected
        alias_keyword = self.expect(TokenType.IDENTIFIER)
        if alias_keyword.value != "as":
            raise ParserError("Expected 'as' after module path", alias_keyword)
        return [(None, str(self.expect(TokenType.IDENTIFIER).value))]

    def _parse_world_members(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        states: list[dict[str, Any]] = []
        primitives: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        rules: list[dict[str, Any]] = []
        handlers: list[dict[str, Any]] = []
        while self.current().type != TokenType.RBRACE:
            if self.current().type == TokenType.EOF:
                self._record_world_error(ParserError("Unclosed entity or agent", self.current()))
                self._raise_world_errors()
            member_start = self.pos
            try:
                tok = self.current()
                if (
                    tok.type == TokenType.IDENTIFIER
                    and str(tok.value).startswith("on_")
                    and self.peek() is not None
                    and self.peek().type == TokenType.ARROW
                ):
                    self.pos += 1
                    handler_name = str(tok.value)
                    self.expect(TokenType.ARROW)
                    self.expect(TokenType.LBRACE)
                    actions: list[dict[str, Any]] = []
                    while self.current().type != TokenType.RBRACE:
                        if self.current().type == TokenType.EOF:
                            raise ParserError("Unclosed lifecycle handler body", self.current())
                        action_start = self.pos
                        act_tok = self.current()
                        if act_tok.type == TokenType.IDENTIFIER and act_tok.value == "post":
                            actions.append(self._parse_post_statement(action_start))
                        elif act_tok.type == TokenType.IDENTIFIER and act_tok.value == "delay":
                            actions.append(self._parse_delay_branch_statement(action_start))
                        elif act_tok.type == TokenType.IDENTIFIER and act_tok.value in ("transition", "emit"):
                            _kind_stmt, stmt = self._parse_world_rule_statement()
                            actions.append(stmt)
                        else:
                            raise ParserError(f"Unexpected statement in lifecycle handler: '{act_tok.value}'", act_tok)
                    self.expect(TokenType.RBRACE)
                    handlers.append({
                        "event": handler_name,
                        "actions": actions,
                        "span": self._node_span(member_start),
                    })
                    continue

                keyword = self.expect_identifier_or_keyword()
                val = str(keyword.value)
                if val == "rule":
                    rules.append(self._parse_world_rule(member_start))
                elif val == "event":
                    events.append(self._parse_event_declaration(member_start))
                elif val == "state":
                    field_name = str(self.expect_identifier_or_keyword().value)
                    self.expect(TokenType.COLON)
                    type_name = self._parse_type_expression()
                    if type_name.startswith(("Pool<", "Pool")):
                        init_val = None
                        if self.match(TokenType.ASSIGN):
                            init_val = self._parse_world_literal()
                        self.expect(TokenType.SEMICOLON)
                        primitives.append({
                            "primitive_kind": "pool",
                            "name": field_name,
                            "type_spec": type_name,
                            "initial_value": init_val if init_val is not None else 0,
                            "span": self._node_span(member_start),
                        })
                    else:
                        self.expect(TokenType.ASSIGN)
                        value = self._parse_world_literal()
                        self.expect(TokenType.SEMICOLON)
                        states.append({
                            "name": field_name, "type_name": type_name, "value": value,
                            "span": self._node_span(member_start),
                        })
                elif val == "flow":
                    field_name = str(self.expect_identifier_or_keyword().value)
                    self.expect(TokenType.COLON)
                    type_name = self._parse_type_expression()
                    init_val = None
                    if self.match(TokenType.ASSIGN):
                        init_val = self._parse_world_literal()
                    self.expect(TokenType.SEMICOLON)
                    primitives.append({
                        "primitive_kind": "flow",
                        "name": field_name,
                        "type_spec": type_name,
                        "initial_value": init_val,
                        "span": self._node_span(member_start),
                    })
                elif val == "ledger":
                    field_name = str(self.expect_identifier_or_keyword().value)
                    self.expect(TokenType.COLON)
                    type_name = self._parse_type_expression()
                    self.expect(TokenType.SEMICOLON)
                    primitives.append({
                        "primitive_kind": "ledger",
                        "name": field_name,
                        "type_spec": type_name,
                        "span": self._node_span(member_start),
                    })
                elif val == "capacity":
                    field_name = str(self.expect_identifier_or_keyword().value)
                    self.expect(TokenType.COLON)
                    type_tok = self.expect_identifier_or_keyword()
                    type_name = str(type_tok.value)
                    cap_max = None
                    cap_window = None
                    if self.match(TokenType.LPAREN):
                        if self.current().type == TokenType.NUMBER:
                            cap_max = float(self.current().value)
                            self.pos += 1
                        if self.match(TokenType.COMMA):
                            dur_tok = self.current()
                            if dur_tok.type in (TokenType.DURATION, TokenType.IDENTIFIER, TokenType.STRING):
                                cap_window = str(dur_tok.value)
                                self.pos += 1
                        self.expect(TokenType.RPAREN)
                    self.expect(TokenType.SEMICOLON)
                    primitives.append({
                        "primitive_kind": "capacity",
                        "name": field_name,
                        "type_spec": type_name,
                        "capacity_max": cap_max,
                        "capacity_window": cap_window,
                        "span": self._node_span(member_start),
                    })
                elif val == "metric":
                    field_name = str(self.expect_identifier_or_keyword().value)
                    self.expect(TokenType.COLON)
                    type_name = self._parse_type_expression()
                    metric_expr = None
                    if self.match(TokenType.ASSIGN):
                        metric_expr = self._parse_rule_expression()
                    self.expect(TokenType.SEMICOLON)
                    primitives.append({
                        "primitive_kind": "metric",
                        "name": field_name,
                        "type_spec": type_name,
                        "metric_expr": metric_expr,
                        "span": self._node_span(member_start),
                    })
                elif self.current().type == TokenType.COLON:
                    field_name = val
                    self.expect(TokenType.COLON)
                    type_name = self._parse_type_expression()
                    init_val = None
                    if self.match(TokenType.ASSIGN):
                        init_val = self._parse_world_literal()
                    self.expect(TokenType.SEMICOLON)
                    primitives.append({
                        "primitive_kind": "attribute",
                        "name": field_name,
                        "type_spec": type_name,
                        "initial_value": init_val,
                        "span": self._node_span(member_start),
                    })
                else:
                    raise ParserError("Expected state, primitive, event, rule or handler declaration", keyword)
            except ParserErrors:
                raise
            except ParserError as error:
                self._record_world_error(error)
                self._recover_world(member_start, frozenset({"state", "event", "rule", "flow", "ledger", "capacity", "metric"}))
        return states, primitives, events, rules, handlers

    def expect_identifier_or_keyword(self) -> Token:
        tok = self.current()
        if tok.type in (TokenType.IDENTIFIER, TokenType.FLOW, TokenType.BUDGET, TokenType.DURATION):
            self.pos += 1
            return tok
        if tok.value and isinstance(tok.value, str) and tok.value.isidentifier() and tok.value not in ("true", "false"):
            self.pos += 1
            return tok
        return self.expect(TokenType.IDENTIFIER)
        raise ParserError(f"Expected identifier or declaration keyword, got {tok.type.name}", tok)

    def _parse_post_statement(self, start: int) -> dict[str, Any]:
        self.pos += 1
        postings: list[dict[str, Any]] = []
        while True:
            posting_start = self.pos
            dir_tok = self.expect(TokenType.IDENTIFIER)
            direction = str(dir_tok.value)
            if direction not in ("debit", "credit"):
                raise ParserError("Expected 'debit' or 'credit' in post statement", dir_tok)
            self.expect(TokenType.LPAREN)
            acct_tok = self.expect(TokenType.IDENTIFIER)
            acct_name = str(acct_tok.value)
            if acct_name == "self" and self.match(TokenType.DOT):
                acct_name = str(self.expect(TokenType.IDENTIFIER).value)
            self.expect(TokenType.COMMA)
            amount_expr = self._parse_rule_expression()
            self.expect(TokenType.RPAREN)
            postings.append({
                "operation": direction,
                "account": acct_name,
                "amount_expr": amount_expr,
                "span": self._node_span(posting_start),
            })
            if not self.match(TokenType.COMMA):
                break
        self.expect(TokenType.SEMICOLON)
        return {
            "kind": "post",
            "postings": postings,
            "span": self._node_span(start),
        }

    def _parse_delay_branch_statement(self, start: int) -> dict[str, Any]:
        self.pos += 1
        self.expect(TokenType.LPAREN)
        delay_expr = self._parse_rule_expression()
        self.expect(TokenType.RPAREN)
        self.expect(TokenType.ARROW)
        branch_tok = self.expect(TokenType.IDENTIFIER)
        if branch_tok.value != "branch":
            raise ParserError("Expected 'branch' after delay arrow", branch_tok)
        self.expect(TokenType.LPAREN)
        branch_prob_expr = self._parse_rule_expression()
        self.expect(TokenType.RPAREN)
        self.expect(TokenType.LBRACE)
        arms: list[dict[str, Any]] = []
        while self.current().type != TokenType.RBRACE:
            arm_start = self.pos
            cond_tok = self.expect(TokenType.IDENTIFIER)
            if cond_tok.value not in ("true", "false"):
                raise ParserError("Branch arm condition must be 'true' or 'false'", cond_tok)
            cond_val = (cond_tok.value == "true")
            self.expect(TokenType.FAT_ARROW)
            kind, emit_stmt = self._parse_world_rule_statement()
            if kind != "emit":
                raise ParserError("Branch arm body must be an emit statement", cond_tok)
            arms.append({
                "condition": cond_val,
                "emission": emit_stmt,
                "span": self._node_span(arm_start),
            })
        self.expect(TokenType.RBRACE)
        return {
            "kind": "delay_branch",
            "delay_expr": delay_expr,
            "branch_prob_expr": branch_prob_expr,
            "arms": arms,
            "span": self._node_span(start),
        }

    def _parse_event_declaration(self, start: int) -> dict[str, Any]:
        name = str(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.LPAREN)
        fields: list[dict[str, str]] = []
        if self.current().type != TokenType.RPAREN:
            while True:
                field_start = self.pos
                field = str(self.expect(TokenType.IDENTIFIER).value)
                self.expect(TokenType.COLON)
                type_name = str(self.expect(TokenType.IDENTIFIER).value)
                fields.append({
                    "name": field, "type_name": type_name,
                    "span": self._node_span(field_start),
                })
                if not self.match(TokenType.COMMA):
                    break
        self.expect(TokenType.RPAREN)
        self.expect(TokenType.SEMICOLON)
        return {"name": name, "fields": fields, "span": self._node_span(start)}

    def _parse_world_rule(self, start: int) -> dict[str, Any]:
        rule_name = str(self.expect(TokenType.IDENTIFIER).value)
        on = self.expect(TokenType.IDENTIFIER)
        if on.value != "on":
            raise ParserError("Expected 'on' after rule name", on)
        event_keyword = self.expect(TokenType.IDENTIFIER)
        if event_keyword.value != "event":
            raise ParserError("Expected 'event' after 'on'", event_keyword)
        event_name = str(self.expect(TokenType.IDENTIFIER).value)
        guard = self._parse_rule_guard(self.pos - 1) if self.match(TokenType.WHEN) else None
        self.expect(TokenType.LBRACE)
        transitions: list[dict[str, Any]] = []
        emissions: list[dict[str, Any]] = []
        while self.current().type != TokenType.RBRACE:
            if self.current().type == TokenType.EOF:
                self._record_world_error(ParserError("Unclosed rule", self.current()))
                self._raise_world_errors()
            statement_start = self.pos
            try:
                kind, statement = self._parse_world_rule_statement()
            except ParserErrors:
                raise
            except ParserError as error:
                self._record_world_error(error)
                self._recover_world(statement_start, frozenset({"transition", "emit"}))
                continue
            if kind == "transition":
                transitions.append(statement)
            else:
                emissions.append(statement)
        self.expect(TokenType.RBRACE)
        return {
            "name": rule_name, "event": event_name, "guard": guard,
            "transitions": transitions, "emissions": emissions,
            "span": self._node_span(start),
        }

    def _parse_world_rule_statement(self) -> tuple[str, dict[str, Any]]:
        statement_start = self.pos
        keyword = self.expect(TokenType.IDENTIFIER)
        if keyword.value == "transition":
            target = str(self.expect_identifier_or_keyword().value)
            self.expect(TokenType.ASSIGN)
            expr = self._parse_rule_expression()
            self.expect(TokenType.SEMICOLON)
            return "transition", {
                "target": target, "expr": expr,
                "span": self._node_span(statement_start),
            }
        if keyword.value != "emit":
            raise ParserError("Expected transition or emit statement", keyword)
        target = str(self.expect_identifier_or_keyword().value)
        arguments: dict[str, dict[str, Any]] = {}
        if self.match(TokenType.LPAREN):
            if self.current().type != TokenType.RPAREN:
                while True:
                    field = str(self.expect_identifier_or_keyword().value)
                    if field in arguments:
                        raise ParserError(f"Duplicate emitted event field '{field}'")
                    self.expect(TokenType.ASSIGN)
                    arguments[field] = self._parse_rule_expression()
                    if not self.match(TokenType.COMMA):
                        break
            self.expect(TokenType.RPAREN)
        after = self.expect(TokenType.IDENTIFIER)
        if after.value != "after":
            raise ParserError("Expected 'after' in emit statement", after)
        delay_expr = self._parse_rule_expression()
        if delay_expr.get("kind") == "literal" and type(delay_expr.get("value")) in (int, float):
            delay = delay_expr["value"]
        else:
            delay = delay_expr
        self.expect(TokenType.SEMICOLON)
        return "emit", {
            "event": target, "delay": delay, "arguments": arguments,
            "span": self._node_span(statement_start),
        }

    def _parse_rule_guard(self, start: int) -> dict[str, Any]:
        self.expect(TokenType.LPAREN)
        field = str(self.expect_identifier_or_keyword().value)
        operators = {
            TokenType.EQ: "==",
            TokenType.NEQ: "!=",
            TokenType.LT: "<",
            TokenType.LTE: "<=",
            TokenType.GT: ">",
            TokenType.GTE: ">=",
        }
        comparison = self.current()
        if comparison.type not in operators:
            raise ParserError("Expected guard comparison operator", comparison)
        self.pos += 1
        value = self._parse_world_literal()
        self.expect(TokenType.RPAREN)
        return {
            "field": field, "operator": operators[comparison.type], "value": value,
            "span": self._node_span(start),
        }

    def _parse_payload_reference(self) -> dict[str, Any]:
        start = self.pos
        self.expect(TokenType.IDENTIFIER)
        self.expect(TokenType.DOT)
        return {
            "kind": "payload_field",
            "name": str(self.expect(TokenType.IDENTIFIER).value),
            "span": self._node_span(start),
        }

    def _parse_rule_expression(self) -> dict[str, Any]:
        start = self.pos
        result = self._parse_arithmetic(0, 0)
        if self.pos - start > 256:
            raise ParserError("Arithmetic expression token limit exceeded", self.current())
        return result

    def _parse_arithmetic(self, minimum: int, depth: int) -> dict[str, Any]:
        start = self.pos
        if depth > 24:
            raise ParserError("Arithmetic expression depth limit exceeded", self.current())
        left = self._parse_primary(depth + 1)
        precedence = {TokenType.PLUS: (1, "+"), TokenType.MINUS: (1, "-"),
                      TokenType.STAR: (2, "*"), TokenType.SLASH: (2, "/")}
        while self.current().type in precedence:
            level, operator = precedence[self.current().type]
            if level < minimum:
                break
            self.pos += 1
            right = self._parse_arithmetic(level + 1, depth + 1)
            left = {
                "kind": "binary", "operator": operator, "left": left, "right": right,
                "span": self._node_span(start),
            }
        return left

    def _parse_primary(self, depth: int) -> dict[str, Any]:
        start = self.pos
        token = self.current()
        if self.match(TokenType.LPAREN):
            expression = self._parse_arithmetic(0, depth)
            self.expect(TokenType.RPAREN, "Missing closing expression parenthesis")
            expression["span"] = self._node_span(start)
            return expression
        if token.type == TokenType.IDENTIFIER and token.value == "sample" and (
            self.peek() is not None and self.peek().type == TokenType.IDENTIFIER
        ):
            return self._parse_sample_expression()
        if token.type == TokenType.IDENTIFIER and token.value == "payload" and (
            self.peek() is not None and self.peek().type == TokenType.DOT
        ):
            return self._parse_payload_reference()
        if (
            (token.type == TokenType.IDENTIFIER or token.type in (TokenType.BUDGET, TokenType.FLOW, TokenType.DURATION))
            and token.value not in ("true", "false")
        ):
            if self.peek() is not None and self.peek().type == TokenType.LPAREN:
                return self._parse_call_expression()
            self.pos += 1
            return {
                "kind": "reference", "name": str(token.value),
                "span": self._node_span(start),
            }
        value = self._parse_world_literal()
        return {"kind": "literal", "value": value, "span": self._node_span(start)}

    def _parse_call_expression(self) -> dict[str, Any]:
        start = self.pos
        fn_tok = self.expect(TokenType.IDENTIFIER)
        fn_name = str(fn_tok.value)
        self.expect(TokenType.LPAREN)
        arguments: list[dict[str, Any]] = []
        if self.current().type != TokenType.RPAREN:
            while True:
                arguments.append(self._parse_rule_expression())
                if not self.match(TokenType.COMMA):
                    break
        self.expect(TokenType.RPAREN)
        return {
            "kind": "call",
            "function": fn_name,
            "arguments": arguments,
            "span": self._node_span(start),
        }

    def _parse_sample_expression(self) -> dict[str, Any]:
        start = self.pos
        self.expect(TokenType.IDENTIFIER)
        distribution_token = self.expect(TokenType.IDENTIFIER)
        distribution = str(distribution_token.value)
        if distribution not in ("bernoulli", "uniform"):
            raise ParserError("Unknown sample distribution", distribution_token)
        self.expect(TokenType.LPAREN)
        arguments: list[dict[str, Any]] = []
        if self.current().type != TokenType.RPAREN:
            while True:
                arguments.append(self._parse_sample_argument())
                if not self.match(TokenType.COMMA):
                    break
        self.expect(TokenType.RPAREN)
        return {
            "kind": "sample", "distribution": distribution, "arguments": arguments,
            "span": self._node_span(start),
        }

    def _parse_sample_argument(self) -> dict[str, Any]:
        start = self.pos
        token = self.current()
        if token.type == TokenType.IDENTIFIER and token.value == "payload" and (
            self.peek() is not None and self.peek().type == TokenType.DOT
        ):
            return self._parse_payload_reference()
        if (
            (token.type == TokenType.IDENTIFIER or token.type in (TokenType.BUDGET, TokenType.FLOW, TokenType.DURATION))
            and token.value not in ("true", "false")
        ):
            if self.peek() is not None and self.peek().type == TokenType.LPAREN:
                return self._parse_call_expression()
            self.pos += 1
            return {
                "kind": "reference", "name": str(token.value),
                "span": self._node_span(start),
            }
        value = self._parse_world_literal()
        return {"kind": "literal", "value": value, "span": self._node_span(start)}

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
        if tok.type == TokenType.IDENTIFIER:
            self.pos += 1
            if tok.value in ("true", "false"):
                return tok.value == "true"
            return str(tok.value)
        raise ParserError("Expected state literal", tok)

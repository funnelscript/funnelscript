# Plan 003: Specify and Verify Parser EOF Safety and Narrow Binary Arithmetic

> Executor: begin with research and a type/grammar decision. The old plan was stale: the parser function is `_parse_rule_expression`, and `TokenType.STAR`/`TokenType.SLASH` **do not exist**. Do not copy the old operator patch without updating lexer, grammar and type checker together.
>
> Drift preflight: `git status --short -- src/funnelscript/tokens.py src/funnelscript/parser.py src/funnelscript/compiler/world_ast.py src/funnelscript/runtime/world_executor.py tests/`, `git diff 41f00f1 -- src/funnelscript/tokens.py src/funnelscript/parser.py src/funnelscript/compiler/world_ast.py src/funnelscript/runtime/world_executor.py tests/`; in research inspect `git status --short -- spec/ evals/` and `git diff abe561f -- spec/ evals/`.

## Status

- **Priority:** P1
- **Effort:** M
- **Risk:** MED, because arithmetic typing and grammar are language contracts
- **Depends on:** 001 green; a research hypothesis/type rule recorded before implementation
- **Category:** correctness / language
- **Planned at:** app `41f00f1`, research `abe561f`, reassessed 2026-10-31
- **Status:** TODO

## Why this matters

`Parser.current()` directly indexes `self.tokens[-1]` for an empty token sequence, which raises an implementation `IndexError`. World rules support a narrow `state_ref +|- literal_or_payload` expression form, but marketing models need typed multiplication and division for derived quantities. This should remain a **bounded v0 grammar change**, not an implicit full expression language with undocumented precedence, coercion or zero-division behavior.

## Verified current code and research gate

- `src/funnelscript/parser.py:81-82`: `return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]`; empty token input is unsafe.
- `src/funnelscript/parser.py:404-442`: `_parse_rule_expression` recognizes a state reference followed by `PLUS` or `MINUS`; right operand accepts payload reference or literal. It checks `self.current().value` while choosing the right side.
- `src/funnelscript/tokens.py:6-58,120-170`: operator tokens include `PLUS` and `MINUS`, **not** `STAR`/`SLASH`; `//` starts a comment and must keep working after adding division.
- `src/funnelscript/compiler/world_ast.py:35-39`: `BinaryExpression.operator: Literal["+", "-"]`, left `ReferenceExpression`, right literal/payload. `WorldTypeChecker._expression_type` currently enforces same exact numeric type for two operands.
- `src/funnelscript/runtime/world_executor.py:72-76`: binary evaluation handles only `+`/`-` through a two-way branch.
- Test patterns: `tests/test_world_rules.py`, `tests/test_world_language.py`, `tests/test_world_stochastic.py`. Research `spec/rule-transitions-v0.md` and `spec/grammar.ebnf`, DEC-022/027/031.
- **H-AR1:** an empty or exhausted token stream yields a deliberate `ParserError`, never raw `IndexError`.
- **H-AR2:** supported single-binary expressions parse, type-check and evaluate deterministically with exact type rules. Falsifier: mismatch between AST type and interpreter result.
- **H-AR3:** zero denominators are rejected at compile time when literal and at runtime when dynamic; `//` comments preserve prior meaning.
- **Invariant:** no implicit int/float widening. Result of `/` is `float` (including int/int), so assigning it to an `int` state is a type error. Other supported operators preserve strict typed operands; no silent division truncation or non-finite results.

## Scope

**In:** application `src/funnelscript/tokens.py`, `src/funnelscript/parser.py`, `src/funnelscript/compiler/world_ast.py`, `src/funnelscript/runtime/world_executor.py`, `tests/test_world_rules.py`, `tests/test_world_language.py`; research `spec/arithmetic-expressions-v0.md`, `spec/grammar.ebnf`, `evals/arithmetic-expressions-v0.md`.

**Out:** general AST rewrite, operator precedence beyond one binary expression, automatic numeric coercion, variable scoping changes, sampling semantics, legacy StrategyAST behavior, external dependencies and implicit marketing/economic compiler rules.

## Steps and verification

1. **Formalize first:** in research `spec/arithmetic-expressions-v0.md`, record H-AR1..3, typing judgments for `+,-,*,/`, examples `revenue = units * payload.price` and `ratio = spend / clicks`, dynamic zero policy, overflow/non-finite policy and explicit grammar exclusion of chained operators/parentheses. Adjust `spec/grammar.ebnf` consistently. Verify: `rg -n 'H-AR1|H-AR2|H-AR3|division|type' spec/arithmetic-expressions-v0.md` and reviewer checks no dangling EBNF productions.
2. **Write RED boundary and operator tests:** empty `Parser([])`/empty source, valid multiplication/division, mixed numeric type rejection, static/dynamic division by zero, comment `//`, negative right literal, invalid second operator and unknown state ref. Verify: `uv run pytest tests/test_world_rules.py tests/test_world_language.py -v`, record expected new failing cases before implementing.
3. **Handle EOF deliberately:** return/raise a stable `ParserError` from public parsing on empty tokens; never manufacture a fake source position that hides the error. Verify: `uv run pytest tests/test_world_language.py -v` exits 0 for boundary tests.
4. **Add lexer and parser operators:** add `TokenType.STAR` and `TokenType.SLASH`, tokenize `*` and `/` while preserving `//` comment precedence. Extend only `_parse_rule_expression` to a single supported binary operation with a typed right literal/payload/state reference; reject unsupported chaining explicitly. Verify: focused World rules tests pass.
5. **Type-check and evaluate:** add supported operators to `BinaryExpression`; preserve numeric same-type constraint except division result is always float; reject static literal zero and runtime dynamic zero; reject non-finite arithmetic outputs. Avoid `eval()` and duplicate arithmetic semantics. Verify: `uv run pytest tests/test_world_rules.py tests/test_world_stochastic.py -v` exits 0.
6. **Run full acceptance:** `uv run pytest -q` exits 0, documented `examples/counter_world.fnl` runs unchanged, research `python3 -m unittest discover -s tests -v` exits 0. Record source SHA and test results in `evals/arithmetic-expressions-v0.md`.

## Test plan and done criteria

- [ ] No uncaught empty-token `IndexError`.
- [ ] Lexer recognizes multiplication/division and still recognizes `//` comments.
- [ ] AST/type/runtime agree for positive, negative, zero and non-finite arithmetic boundaries.
- [ ] Division expression type is float; strict int assignment rejects it.
- [ ] No unplanned precedence, coercion, cyclic language semantics or source file changes.
- [ ] Existing and new tests pass, research grammar/eval is synchronized, and later conformance 006 can consume new cases.

## STOP conditions and maintenance

STOP if strict v0 typing produces an unresolved design choice, adding `/` breaks existing comment tokenization, or precedence must be introduced to support a requested expression. Do not change the grammar informally: record a research decision first. The next executor must also update accepted decision/master/failure records if the language contract is changed.

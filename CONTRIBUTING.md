# Contributing to FunnelScript

> Engineering guidelines, development workflows, testing requirements, and contribution taxonomy for the FunnelScript compiler and runtime.

---

## Architectural Overview

FunnelScript is engineered with a strict inside-out separation of concerns:

```
src/funnelscript/
├── tokens.py              # Lexer token specifications and regex rules
├── parser.py              # Recursive-descent AST parser (WorldAST & StrategyAST)
├── linter.py              # Static semantic analysis, DAG reachability, mass balance
├── runtime/
│   ├── engine.py          # Vectorized SIMD agent execution engine
│   └── event_kernel.py    # Priority-queue discrete-event calendar substrate
├── compiler/
│   └── world_ast.py       # General World, Entity, and Agent type checking
├── adapters/
│   └── pymc_adapter.py    # Bayesian posterior parameter ingestion
└── cli.py                 # Command-line interface (check, simulate, calibrate)
```

Web client applications and visualization dashboards reside in `apps/web`.

---

## Development Environment Setup

### Prerequisites

* Python $\ge 3.11$ with [`uv`](https://github.com/astral-sh/uv)
* [`bun`](https://bun.sh) for JavaScript/TypeScript tooling

### Installation

```bash
git clone https://github.com/imMamdouhaboammar/funnelscript.git
cd funnelscript

# Install Python dependencies and virtual environment
uv sync

# Install Web Studio dependencies
cd apps/web
bun install
cd ../..
```

---

## Verification & Test Execution

All pull requests must pass the complete polyglot test suite before review:

### Python Compiler & Runtime Tests

```bash
# Execute complete unit, integration, and performance test suite
uv run pytest -v

# Target specific compiler test suites
uv run pytest tests/test_world_language.py -v
uv run pytest tests/test_event_kernel.py -v
uv run pytest tests/test_linter.py -v
uv run pytest tests/test_runtime.py -v
```

### Web Studio Tests & Production Build

```bash
cd apps/web
bun test
bun run build
cd ../..
```

---

## Contribution Taxonomy & Entry Points

Issues and pull requests are categorized by architectural layer:

| Label | Scope | Typical Entry Tasks |
| :--- | :--- | :--- |
| `good-first-issue` | Standard Library & CLI | New standard channels, CLI output formatting, documentation examples |
| `compiler` | Syntax & AST | Parser extensions, AST node definitions, type checker validations |
| `runtime` | Execution Engine | Vectorized SIMD kernels, event calendar performance, stochastic sampling |
| `adapters` | Ecosystem Connectors | PyMC calibration schemas, provider API mocks, webhook ingestion |
| `rfc` | Language Specification | Formal grammar revisions, new syntax keywords, core type changes |

---

## Pull Request Guidelines

1. **Strict 100% English Standard:** All code, comments, docstrings, issue reports, and commit messages must be strictly in English. Non-English characters are prohibited in tracked source files.
2. **Red-Green Falsification:** Every bug fix or net-new feature must include automated test cases that fail without the proposed implementation and pass with it.
3. **Mass & Budget Invariants:** Any modification to strategy linting or simulation semantics must prove that audience mass conservation ($\sum P(\text{state}) = 1.0$) and financial budget ceilings ($C_{\text{max}}$) remain fully preserved.
4. **RFC Process for Core Changes:** Changes modifying language grammar (`tokens.py`, `parser.py`) or type systems require an accepted RFC proposal in `docs/` prior to implementation.

---

## Strategic & Architectural Documentation

Contributors should consult the following foundational guides:

* **[Open-Source Growth Playbook](docs/OPEN_SOURCE_GROWTH_PLAYBOOK.md):** The 4-pillar open-source scaling strategy.
* **[The Shim Strategy](docs/SHIM_STRATEGY.md):** Specification-first adoption and the linter wedge.
* **[Package Manager Specification (`fpm`)](docs/fpm.md):** Anatomy, lockfiles, and commercial incentives.
* **[Marketing Systems Engineering](docs/MARKETING_SYSTEMS_ENGINEERING.md):** The core persona, mental models, and JTBD.
* **[Architecture Decision Records](docs/DECISIONS.md):** Canonical record of all accepted architectural decisions (DEC-001 through DEC-026).
* **[Intellectual Debates](docs/DEBATES.md):** Rigorous engineering trade-offs and falsification boundaries.
* **[Out of the Box Ideas](docs/OUT_OF_THE_BOX.md):** Speculative hypotheses and frontier research tracking (OOTB-001 through OOTB-020).

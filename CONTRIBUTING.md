# Contributing to FunnelScript

FunnelScript is an experimental source language, not an empirically validated market forecasting system. Contributions must preserve the separation between the domain-neutral World interpreter and the legacy marketing-strategy simulator.

## Implementation map

| Path | Responsibility |
| --- | --- |
| [`src/funnelscript/parser.py`](src/funnelscript/parser.py) and [`tokens.py`](src/funnelscript/tokens.py) | Source parsing and token definitions |
| [`src/funnelscript/compiler/world_ast.py`](src/funnelscript/compiler/world_ast.py) | Typed World AST, semantic validation, module contracts |
| [`src/funnelscript/core/event_machine.py`](src/funnelscript/core/event_machine.py) | Discrete-event ordering, bounded execution, seeded RNG |
| [`src/funnelscript/runtime/world_executor.py`](src/funnelscript/runtime/world_executor.py) | Pure World rule execution and events |
| [`src/funnelscript/runtime/simulator.py`](src/funnelscript/runtime/simulator.py) | Separate legacy marketing simulator |
| [`src/funnelscript/cli.py`](src/funnelscript/cli.py) | `check`, `compile`, `run-world`, `simulate`, `init`, `init-world`, `schema`, `--version` |
| [`src/funnelscript/stdlib/marketing/`](src/funnelscript/stdlib/marketing/lead_response.fnl) | First reusable Marketing Standard Library source module |
| [`tests/`](tests/test_preview_quickstart.py) | Python behavior, negative-path, and installed-CLI tests |
| [`apps/web/`](apps/web/package.json) | Bun-based editor/frontend and tests |

## Development and verification

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required. Bun is required to verify changes affecting the Web Studio.

```bash
git clone https://github.com/funnelscript/funnelscript.git
cd funnelscript
uv sync --locked --dev
uv run pytest -v
uv build
cd apps/web
bun install --frozen-lockfile
bun test
bun run build
```

For a narrow change, first run its relevant test module (for example `uv run pytest tests/test_world_modules.py -v` or `uv run pytest tests/test_preview_quickstart.py -v`), then run the complete suite and affected build gates before submitting. The GitHub workflow [`preview-ci.yml`](.github/workflows/preview-ci.yml) runs the pinned Python/wheel and Bun paths on supported pushes and tags.

## Research-first TDD

1. Read [`AGENTS.md`](AGENTS.md) and the relevant [research specification](https://github.com/funnelscript/funnelscript-research/tree/main/spec). Record a theoretical or measured anchor, a falsifiable hypothesis and explicit invariants before changing language behavior.
2. Write an independently justified regression test. For a new behavior or bug, observe RED against the current implementation, then implement the minimum GREEN change.
3. Preserve existing test oracles. Do not weaken tests, add silent error recovery, or present fabricated simulation outputs as market evidence.
4. Update the app [decision/debate/hypothesis records](docs/DECISIONS.md) and their research counterparts when decisions change; update [failure lessons](failure-lessons/README.md) for actual failures.
5. Verify the CLI and public docs against the implemented commands. Run `git diff --check` and review the full diff.

## Working on an experimental World

```bash
uv run funnelscript init-world first.fnl
uv run funnelscript check first.fnl
uv run funnelscript run-world first.fnl --event '{"name":"Prospect.Impression","time":0,"payload":{"cpc":2.0,"conversion_probability":0.7,"order_value":100.0}}' --seed 1
```

The [Experimental Preview Guide](docs/EXPERIMENTAL_PREVIEW.md) explains the source module and user-assumed conversion probability. The installed `v0.2.0a1` Git-source preview is verified; no PyPI package, Live execution engine, or empirical PyMC/OmniTwin calibration is implied.

## Contribution scope

- Core syntax and types: accompany changes with updated grammar/World semantics research.
- World runtime: preserve typed payload validation, pre-event snapshots, deterministic seeded replay, and bounded scheduling.
- Marketing library: keep source modules domain-specific and the language kernel domain-neutral.
- Legacy engine: preserve its public CLI behavior unless an explicitly scoped migration is accepted.
- Docs and research: keep every usage claim reproducible and distinguish installed features from RFCs, proposals, and past milestones.

Use English in tracked files and commit messages. Never commit credentials or private customer data. Reference the actual tests, output and limitations in pull requests.

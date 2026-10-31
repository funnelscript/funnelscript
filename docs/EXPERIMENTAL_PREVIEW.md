# Experimental Developer Preview: v0.2.0a1

FunnelScript is an experimental source language and reference interpreter, not a validated market forecasting platform. This preview demonstrates a source-defined, reusable Marketing Standard Library agent and a safe first-run CLI journey.

## Prerequisites

- Python 3.12 or newer.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
- No credentials, paid advertising accounts, API keys, or marketing datasets are required.

The verified public `v0.2.0a1` Git tag is the release channel for this preview, **not PyPI**. The tagged CI and clean-directory Git-source installation were checked on 2026-10-31; see the [research attestation](https://github.com/funnelscript/funnelscript-research/blob/main/evals/developer-preview-v0.md).

## Start in a new directory

```bash
mkdir funnelscript-preview
cd funnelscript-preview
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript --version
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript init-world first.fnl
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript check first.fnl
uvx --from "git+https://github.com/funnelscript/funnelscript@v0.2.0a1" funnelscript run-world first.fnl \
  --event '{"name":"Prospect.Impression","time":0,"payload":{"cpc":2.0,"conversion_probability":0.7,"order_value":100.0}}' \
  --seed 1
```

The generated file is:

```funnelscript
world MarketingPreview {
  import "std:marketing/lead_response.fnl" as Prospect;
}
```

The final command prints a JSON document with `world="MarketingPreview"`, `processed_events=2`, no pending events, and a `Prospect` state containing `exposed=true`, `converted=true`, `spend=2.0` and `revenue=100.0`. Change only `--seed 1` to `--seed 2` and the same one-lead model reports no conversion and `revenue=0.0`.

The output is **conditioned on the input probability 0.7, which you supplied**. No statistical fit, causal identification, market digital twin, or empirically verified economic model is involved. The module currently accepts finite float costs and order values but does not enforce nonnegative monetary values.

## Make your own World module

Save the following next to `first.fnl` as `counter.fnl`:

```funnelscript
world CounterLibrary {
  entity Counter {
    state count: int = 0;
    event Pulse();
    rule Record on event Pulse {
      transition count = count + 1;
    }
  }
}
```

Add one line before the closing brace of `first.fnl`:

```funnelscript
  import "./counter.fnl" as Tracker;
```

Run `funnelscript check first.fnl` and `funnelscript run-world first.fnl --event Tracker.Pulse@0` using the same `uvx --from ...` prefix. You should see `Tracker.count=1`. The two imported owners are independent; cross-owner dispatch is not supported.

A module can currently export exactly one `entity` or `agent`, and local imports stay within the importing file's directory. Missing modules, duplicate aliases, cycles, absolute paths, traversal, and symlink escapes are rejected before execution. The `std:` namespace resolves bundled modules from the installed Python distribution.

## Safety and failure behavior

- `init-world first.fnl` refuses to overwrite an existing file, including an existing symbolic link. Choose a different filename or edit your file intentionally.
- The target must end in `.fnl`; its parent directory must already exist.
- `run-world` only simulates in memory. It does not buy media, contact customers, collect personal data, or execute external effects.
- Use `--max-events` to cap event processing. Use an explicit `--seed` for replay.
- This preview is **not** a financial forecast and cannot justify material spend without independent empirical validation.

## Contributing and verifying from a checkout

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

The GitHub workflow `.github/workflows/preview-ci.yml` runs these gates on Linux, and additionally smoke-tests the built wheel from outside the checkout. Downloadable CI build artifacts are retained for 14 days when GitHub Actions succeeds. The source Git tag and an Actions artifact are **not** a PyPI publication or a claim of a verified standalone GitHub Release.

## Evidence and scope

The falsifiable design is in [Developer Preview v0 Research Contract](https://github.com/funnelscript/funnelscript-research/blob/main/spec/developer-preview-v0.md); the actual observed outcomes and remaining limitations are in [Evaluation](https://github.com/funnelscript/funnelscript-research/blob/main/evals/developer-preview-v0.md). Earlier source module contract: [Marketing Standard Library v0](https://github.com/funnelscript/funnelscript-research/blob/main/spec/marketing-stdlib-v0.md).

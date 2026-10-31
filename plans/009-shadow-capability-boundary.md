# Plan 009: Establish a Non-Mutating Shadow Capability Boundary

> Executor: this card authorizes a local/mock capability protocol only. It **does not authorize contacting external platforms, supplying credentials, performing Live effects or changing ad accounts**. Read both AGENTS.md files, DEC-013 through DEC-018, and the full plan.
>
> Drift preflight: `git status --short -- src/funnelscript/core/ src/funnelscript/runtime/ tests/` and `git diff 41f00f1 -- src/funnelscript/core/ src/funnelscript/runtime/ tests/`. Inspect all pre-existing changes before implementation.

## Status

- **Priority:** P2
- **Effort:** M
- **Risk:** HIGH, because capability confusion can convert simulation into unintended actions
- **Depends on:** 006 established World and intent semantics; explicit approval for any future data access
- **Category:** security / direction
- **Planned at:** application `41f00f1`, research `abe561f`, 2026-10-31
- **Status:** TODO for local mock design

## Why this matters

`EventMachine` already returns inert `EffectIntent` records. That is a good safety boundary. A Shadow model should be able to compare a hypothetical decision against authorized observations without accidentally causing a provider write. A guessed provider integration or broad catch-all executor would violate the adopted plan-vs-apply philosophy before authorization, idempotency and budget review exist.

## Current state and research contract

- `src/funnelscript/core/event_machine.py:35-53`: immutable `EffectIntent`, `Transition.effects`, `RunResult.intents`. The event kernel never invokes a provider.
- `src/funnelscript/runtime/world_executor.py`: World reducer uses the kernel; no real provider dispatcher exists.
- Research `DEC-013` effect separation, `DEC-014` Shadow observation, `DEC-015` idempotency and compensating actions, `DEC-017/018` provider plan/apply and budget ceilings.
- **H-SH1:** evaluating a World with no explicitly authorized capability performs zero external mutation, even if its intents request one. Falsifier: any write-side fake call.
- **H-SH2:** an unrecognized intent or capability mismatch fails closed and leaves the event trace unchanged. Falsifier: implicit dispatch or successful unauthorized fallback.
- **H-SH3:** re-evaluating the same input/seed returns the same inert intent sequence and never duplicates a provider operation. Falsifier: nondeterministic dispatch without an injected clock/data fixture.

## Scope

**In:** research `spec/shadow-capabilities-v0.md`, `evals/shadow-capabilities-v0.md`; application `src/funnelscript/runtime/effect_handlers.py` (new, only if the research interface is accepted), `tests/test_effect_capabilities.py`.

**Out:** changes to `EventMachine` public event semantics, network clients, live API endpoints, secrets/env management, write permissions, real `apply`, background agents or campaign actions. If new core semantics are required, STOP for an ADR instead of silently broadening scope.

## Steps

1. **Define modes and threat model:** `Simulation` returns intents only; `Shadow` may compare against explicitly supplied immutable local observation fixtures, but has no provider write interface. Define capability identifiers, deny-by-default checking, error propagation and audit fields. Verify: `rg -n 'H-SH1|H-SH2|H-SH3|default-deny|Live excluded' spec/shadow-capabilities-v0.md`.
2. **Test the default boundary first:** create a fake provider with read/write counters; exercise a World-generated effect, an unknown kind and a missing capability. Every case must leave write count zero. Verify: `uv run pytest tests/test_effect_capabilities.py -v` with expected RED only for absent new handler APIs, not because a real platform was contacted.
3. **Implement the minimum inert dispatcher:** if required, implement only an explicit capability-checked mapping over provided observation fixtures. No global registry, implicit plugin import, arbitrary command, dynamic code evaluation or network access. Verify: focused test passes and includes rejection of unknown intents.
4. **Replay and failure testing:** capture seed, inputs, observation fixture version and stable output; test partial fixture failure, repeated call and an unsupported provider mode. Verify: same focused test command exits 0, every fake write counter stays zero.
5. **Independent review:** confirm the default CLI `run-world` path still returns inert intents only and existing tests pass. Verify: `uv run pytest -q` and research `python3 -m unittest discover -s tests -v` exit 0. Record exact commands and source SHAs in research evaluation.

## Done criteria

- [ ] No network operation, secret or platform write in tests or the shipped handler.
- [ ] Unauthorized/missing/unknown capabilities fail closed.
- [ ] Same inputs and versioned fixture produce reproducible Shadow comparisons.
- [ ] No change silently grants a World source the ability to act outside itself.
- [ ] Separate security review and operator authorization are named prerequisites for future Live work.

## STOP and maintenance

STOP if an external service is required to demonstrate the local contract, if a test tries to reach a real account, or if a `Live` handler is proposed inside this card. Later provider integrations need scoped identity, idempotency persistence, spending ceilings, compensation protocol and a fresh security review.

# /agents

Operational skill stack for AI agents working on the FunnelScript project.

Each subdirectory under `skills/` contains the canonical `SKILL.md` (and any supporting files) for one of the 11 mandatory skills declared in `AGENTS.md §4`.

## Skills

| Skill | Role |
|---|---|
| `j-space` | Multi-step cognitive workspace — long-horizon reasoning & architecture design |
| `deep-digger` | Root-cause investigation — falsifiable hypotheses, controlled experiments |
| `deep-research` | Academic grounding — cited synthesis from canonical literature |
| `anti-slop-engineering` | KISS/DRY/YAGNI enforcement, zero-bloat, Google SRE reliability gates |
| `get-things-done` | Milestone decomposition, phase execution waves, atomic deliverable verification |
| `openreview` | Adversarial peer review, falsification testing, academic critique |
| `fable-wise` | Low-level agentic design patterns — debloat, ssotize, detool, Feynman |
| `ponytail` | SHIT interceptor (Scope / Hypothetical / Intent / Task) + Senior Dev Ladder |
| `agent-architecture-audit` | 12-layer agent-stack diagnostics — memory, tool discipline, wrapper regression |
| `install-anti-slop` | Preflight linting, Oxlint configuration, structural quality gating |
| `say-no-to-slop` | Audit and strip AI-isms, conversational chatter, and speculative artifacts |

## Usage

Every agent session operating on this repository **must** invoke the full stack:

```
use: /j-space /deep-digger /deep-research /anti-slop-engineering /get-things-done
     /openreview /fable-wise /ponytail /agent-architecture-audit /install-anti-slop /say-no-to-slop
```

Read the relevant `SKILL.md` before executing any non-trivial task.

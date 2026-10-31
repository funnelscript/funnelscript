# /agents

Operational and Scientific skill stack for AI agents working on the FunnelScript project.

The 22 primary directories under `skills/` each contain a canonical `SKILL.md` and optional supporting resources. These are repository-bundled instructions for compatible agents; they are not executed by the FunnelScript interpreter.

## 1. Core Operational & Engineering Skills

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

## 2. Scientific & Academic Research Skills

| Skill | Role |
|---|---|
| `academic-paper` | Upstream academic paper pipeline reference; only the default language-pair registry is vendored here. Other upstream shared protocols require separate review before full offline use |
| `academic-paper-reviewer` | Multi-perspective academic peer review panel (Journal-fit, peer roles, Devil's advocate) |
| `nature-writing` | Scientific manuscript argumentation, section drafting, structural proof synthesis |
| `latex-paper-en` | English LaTeX manuscript authoring, bibliography/citation repair, submission readiness |
| `scholar-evaluation` | Structured scholarly-work evaluation, evidence-anchored rubrics, research quality grading |
| `literature-review` | Systematic literature review protocol, search planning, source screening, evidence logging |
| `literature-search-arxiv` | arXiv preprint and scientific publication discovery, BibTeX, full-text PDF parsing |
| `literature-search-openalex` | OpenAlex global scholarly knowledge graph queries (papers, authors, citations) |
| `literature-search-europepmc` | Europe PMC open-access technical and scientific literature retrieval |
| `literature-search-biorxiv` | bioRxiv and medRxiv preprint search, DOI resolution, PDF retrieval |
| `evaluation-methodology` | Rigorous multidimensional evaluation rubrics, quality methodology, scoring formulas |

## Usage

For engineering, refactoring, and execution passes:
```
use: /j-space /deep-digger /deep-research /anti-slop-engineering /get-things-done
     /openreview /fable-wise /ponytail /agent-architecture-audit /install-anti-slop /say-no-to-slop
```

For scientific manuscripts, literature review, and formal paper authoring:
```
use: /academic-paper /academic-paper-reviewer /nature-writing /latex-paper-en
     /scholar-evaluation /literature-review /literature-search-arxiv /evaluation-methodology
```

Read the relevant `SKILL.md` before executing any non-trivial task. Discovery uses the hyphenated `name` field, which must match the enclosing directory. Bundled skills are guidance and optional tooling, not an implicit dependency of the installed FunnelScript CLI.

## Verification and scope

- Application: `uv run pytest tests/test_skill_bundle.py -q`.
- The contract checks 22 primary skill names, indexed paths, explicit file references, and the absence of redundant ZIP archives.
- `deep-digger/rust/target/` is a generated, ignored Cargo build directory. Compile locally if needed; never commit it.
- `academic-paper` is a partial upstream vendor snapshot. The default output-language registry is bundled under `skills/academic-paper/references/`; other upstream shared protocols are not packaged or verified for offline use. Consult the [upstream research skills repository](https://github.com/Imbad0202/academic-research-skills) before invoking the complete pipeline.

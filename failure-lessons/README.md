# FunnelScript Engineering Failure Lessons

> *"Pay for an engineering mistake once. After that, the project should remember it."*

This repository knowledge base preserves actionable engineering lessons, root cause analyses, and permanent invariants extracted from debugging, compilation, and architectural milestones in the FunnelScript ecosystem.

---

## Structure & Organization

```text
failure-lessons/
├── README.md                              # This file: Purpose and principles
├── lessons-index.md                       # Comprehensive registry of all documented failure lessons
├── testing-and-verification.md            # Test harnesses, parser drift, and mock boundaries
├── runtime-and-types.md                   # Frozen dataclasses, TypeScript build gates, and runtime exceptions
└── architecture-and-domain-boundaries.md  # Core DSL abstraction vs. model-specific assumptions
```

---

## The 15-Field Lesson Schema

Every lesson in this directory strictly adheres to the canonical 15-field schema defined in the `failure-lessons` OmniSkill constitution:
1. Context
2. What happened
3. Observable symptom
4. Impact
5. Incorrect assumption
6. Root cause (Confirmed | Strongly indicated | Unresolved)
7. Why the architecture allowed it
8. Fix
9. Verification
10. Prevention rule
11. Reusable lesson
12. Related code
13. Related tests
14. Related lessons
15. Status (Resolved | Partially mitigated | Unresolved | Superseded)

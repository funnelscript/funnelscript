# Architecture and Domain Boundaries Failure Lessons

---

## 1. Conflating Model Assumptions with Language Axioms

### Context
Initial architectural specification of FunnelScript language grammar, linter, and runtime invariants.

### What happened
Hardcoded specific e-commerce marketing assumptions (e.g., fixed audience mass conservation $\sum N_s(t) = N_{\text{total}}$, liquid wallet check $P \le w$, and ad halts on cash depletion) directly into the core compiler invariants and grammar.

### Observable symptom
Architectural tension arose when modeling alternative markets (e.g. viral products with expanding TAM, Buy Now Pay Later [BNPL] consumer financing, or enterprises operating with credit lines and overdraft protection).

### Impact
The language risked becoming a narrow, fragile "e-commerce funnel simulation software" rather than a general-purpose domain-specific programming language for marketing systems.

### Incorrect assumption
Assumed that physical invariants observed in simple retail models represented universal axioms that must be enforced by the core compiler.

### Root cause
**Confirmed:** Domain boundary conflation: failing to distinguish between the **Language Core** (the computational algebra) and the **Standard Library / Model-Level Rules** (the specific business model being expressed).

### Why the architecture allowed it
Starting from a single concrete Black Friday e-commerce case study without testing the language abstractions against divergent business models (B2B SaaS, viral consumer apps, financial services).

### Fix
Architected the 4-Layer FunnelScript Stack:
1. **Layer 01 (Language Core):** Minimal computational primitives (`entity`, `agent`, `state`, `event`, `transition`, `rule`, `probability`, `constraint`).
2. **Layer 02 (Execution Runtime):** Discrete-event simulation scheduler.
3. **Layer 03 (Official Standard Library):** `std::marketing` defining `Audience`, `Touchpoint`, `Campaign`, and `Economics` using public language primitives.
4. **Layer 04 (Community Ecosystem):** Market-specific libraries (Egyptian retail, Saudi B2B SaaS).
Decoupled economic constraints into explicit user/library-defined statements: `constraint MassConservation { ... }`.

### Verification
Codified in `DEBATES.md` (Debates 6, 7, 8) and formalized the Generalization Litmus Test.

### Prevention rule
A programming language compiler must verify syntax, type safety, and graph topology; it must NEVER hardcode domain-specific economic rules as universal compiler axioms.

### Reusable lesson
Analogous to SQL: SQL provides relational algebra primitives (`SELECT`, `JOIN`, `CONSTRAINT`); it does not dictate a company's customer schema or pricing rules.

### Related code
[`funnelscript-research/DEBATES.md`](file:///Users/mamdouhaboammar/Documents/funnelscript-research/DEBATES.md)  
[`docs/MASTER_PLAN.md`](file:///Users/mamdouhaboammar/Documents/funnelscript/docs/MASTER_PLAN.md)

### Related tests
[`tests/test_linter.py`](file:///Users/mamdouhaboammar/Documents/funnelscript/tests/test_linter.py)

### Related lessons
- `Linter Duck-Typing ID Access Mismatch`

### Status
**Resolved**

---

## 2. GitHub REST API Prohibition on Personal Account Org Provisioning

### Context
Phase 0 bootstrapping: attempting to create the `funnelscript` GitHub Organization automatically via the CLI.

### What happened
Invoking `gh api -X POST /user/orgs -f login='funnelscript'` failed with an HTTP 404 error.

### Observable symptom
```text
HTTP 404: Not Found (The requested API endpoint does not exist or user lacks permission)
```

### Impact
Automated repository organization bootstrapping failed; blocked automated push until manual intervention occurred.

### Incorrect assumption
Assumed the GitHub REST API allows authenticated personal access tokens to programmatically provision new organizations.

### Root cause
**Confirmed:** GitHub restricts organization creation to interactive web browser flows (`https://github.com/account/organizations/new`) or Enterprise Cloud SCIM APIs; it is unsupported on standard personal accounts via REST API.

### Why the architecture allowed it
Attempting to automate an external administrative privilege that the third-party platform intentionally gates behind interactive browser sessions.

### Fix
Prompted the user to provision the organization once through the browser UI, followed by seamless programmatic creation and pushing of both repositories via `gh repo create funnelscript/funnelscript --public`.

### Verification
Both repositories (`funnelscript/funnelscript` and `funnelscript/funnelscript-research`) successfully created and synchronized.

### Prevention rule
Never attempt automated headless provisioning for third-party administrative account scopes (e.g. Org creation, billing setup) that are restricted to interactive web flows. Prompt the user for the one-time interactive action, then resume programmatic automation.

### Reusable lesson
Identify API permission boundaries early: OAuth tokens have user-scoped boundaries that cannot elevate to organization creation.

### Related code
N/A (GitHub DevOps workflow)

### Related tests
N/A

### Related lessons
- `Interactive CLI Subprocess Deadlock in Background Tasks`

### Status
**Resolved**

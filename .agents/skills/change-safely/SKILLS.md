---
name: change-safely
description: Safely modify existing AI-generated code while preserving working behavior.
triggers:
  - user
---

# Change Safely

This is an existing working application.

Do not assume the implementation is good.

Do not assume the implementation is bad.

Understand it before changing it.

---

## STEP 1 — DEFINE THE CHANGE

State:

- requested behavior
- current behavior
- desired behavior
- files likely involved

---

## STEP 2 — TRACE CURRENT BEHAVIOR

Trace the complete execution path.

Identify:

- entry point
- callers
- dependencies
- state
- API
- database
- external services
- side effects

---

## STEP 3 — IMPACT ANALYSIS

Identify:

- direct dependents
- indirect dependents
- shared utilities
- database effects
- API effects
- authentication effects
- UI effects
- tests

Assign:

LOW / MEDIUM / HIGH

blast radius.

---

## STEP 4 — MINIMAL CHANGE PLAN

Propose the smallest modification that achieves the requested behavior.

Do not redesign unrelated code.

Do not perform opportunistic refactoring.

Do not upgrade unrelated dependencies.

---

## STEP 5 — IMPLEMENT

Modify only what is necessary.

Preserve existing behavior everywhere else.

---

## STEP 6 — VERIFY

Run relevant:

- tests
- lint
- type checks
- build
- targeted runtime checks

Compare behavior before and after where practical.

---

## STEP 7 — REVIEW YOUR OWN CHANGE

Ask:

- Did I change anything unrelated?
- Did I introduce duplication?
- Did I break an existing contract?
- Did I change API behavior?
- Did I change database behavior?
- Did I introduce security issues?
- Did I introduce race conditions?
- Did I assume something that wasn't verified?

---

## FINAL REPORT

Return:

1. What changed
2. Why
3. Files changed
4. Existing behavior preserved
5. Tests performed
6. Remaining risks
7. Anything still unknown
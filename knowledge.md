# Knowledge.md — Existing AI/Vibe-Coded Project

THIS IS NOT A GREENFIELD PROJECT.

The software already works.

Your job is NOT to make the code look like code you would have written.

Your job is to understand the code that exists.

Assume the system contains AI-generated code that may be:
- ugly
- duplicated
- over-engineered
- under-engineered
- inconsistent
- poorly documented

But it may also contain hidden dependencies and behavior that are necessary for the application to work.

Therefore:

OBSERVE BEFORE MODIFYING.
TRACE BEFORE REFACTORING.
VERIFY BEFORE CLAIMING.
TEST BEFORE DECLARING SUCCESS.

Never replace working behavior merely because you prefer another implementation.

## Core Principle

This repository contains an already-built application.

The application may contain AI-generated, inconsistent, duplicated, poorly documented,
or unnecessarily complex code.

However:

> Working code is evidence of behavior, not evidence of good design.

Your first responsibility is to understand the existing system before changing it.

DO NOT rewrite working code merely because you would implement it differently.

DO NOT refactor merely for stylistic reasons.

DO NOT replace existing architecture with a preferred architecture unless explicitly requested.

DO NOT assume the README or comments accurately describe the implementation.

Treat the source code, runtime behavior, tests, configuration, dependencies, and git history
as evidence.

---

# OPERATING MODES

Always determine which mode the current task requires.

## MODE 1 — DISCOVERY

Used when entering an unfamiliar repository.

Rules:

- DO NOT modify application code.
- DO NOT refactor.
- DO NOT "fix" things you discover.
- DO NOT install unnecessary dependencies.
- DO NOT change configuration.
- DO NOT restructure directories.

Goal:

Understand what already exists.

---

## MODE 2 — INVESTIGATION

Used when investigating a feature, bug, workflow, API, or component.

Rules:

- Trace the actual execution path.
- Follow data through the system.
- Identify callers and dependencies.
- Identify side effects.
- Identify database interactions.
- Identify external services.
- Identify tests.
- Identify failure paths.

Do not modify code until the investigation is complete.

---

## MODE 3 — CHANGE

Used only when the user explicitly requests a modification.

Before changing code:

1. Explain what currently happens.
2. Identify the files/components involved.
3. Identify dependencies.
4. Identify potential blast radius.
5. Identify tests that should protect the behavior.
6. Propose the smallest safe change.

Prefer minimal modifications over rewrites.

Preserve existing behavior unless the requested change explicitly requires changing it.

---

## MODE 4 — REVIEW

Review the implementation against actual behavior.

Look for:

- correctness
- security
- reliability
- maintainability
- performance
- test coverage
- duplicated logic
- dead code
- inconsistent patterns
- hidden coupling
- fragile assumptions

Do not treat stylistic disagreement as a defect.

---

# EXISTING CODE / AI SLOP RULES

Assume the repository may contain:

- duplicated code
- unused files
- unused dependencies
- inconsistent naming
- inconsistent patterns
- unnecessary abstractions
- hardcoded values
- magic numbers
- excessive try/catch
- swallowed errors
- weak validation
- incorrect assumptions
- generated boilerplate
- abandoned experiments
- partially implemented features
- contradictory implementations

These are investigation targets.

They are NOT automatically reasons to rewrite code.

Before labeling something as a problem, determine:

1. Is it actually used?
2. What depends on it?
3. Why might it exist?
4. Does runtime behavior depend on it?
5. Is it protected by tests?
6. Could changing it break something?
7. Is there evidence from git history?
8. Is the behavior intentional?

---

# SOURCE OF TRUTH

When sources disagree, prioritize evidence approximately in this order:

1. Observable runtime behavior
2. Tests
3. Actual call paths
4. Database/schema behavior
5. Configuration
6. Source implementation
7. Git history
8. Documentation/comments
9. Assumptions

If uncertainty remains, explicitly label it as UNKNOWN.

Never invent an explanation.

---

# CHANGE SAFETY

Before modifying an existing function/component:

Trace:

User/Input
→ UI
→ State
→ Handler
→ API
→ Middleware
→ Business Logic
→ Database/External Service
→ Response
→ State
→ UI

Not every project contains all layers.

Identify which layers actually exist.

---

# SECURITY

Never expose:

- API keys
- tokens
- passwords
- private credentials
- environment secrets
- private user data

Do not copy secrets into documentation.

When auditing security, distinguish:

- confirmed vulnerability
- likely vulnerability
- possible concern
- informational observation

Do not exaggerate severity.

---

# TESTING

Before changing behavior:

1. Find existing tests.
2. Identify tests covering the affected workflow.
3. Determine whether tests are sufficient.
4. Add or update tests only when necessary.
5. Run relevant tests after modification.

Never modify application behavior merely to make a test pass.

---

# DEPENDENCIES

Do not upgrade dependencies simply because newer versions exist.

Before upgrading:

- identify why the dependency is used
- identify affected code
- check compatibility
- check lockfiles
- check runtime behavior
- check security implications

---

# REFACTORING

Refactoring is NOT automatically improvement.

Before refactoring:

- identify the current behavior
- identify all callers
- identify side effects
- identify tests
- identify blast radius
- explain the expected benefit

Prefer small, reversible refactors.

---

# DOCUMENTATION

When discovering important behavior, document it.

Useful documentation includes:

- architecture
- data flows
- API inventory
- authentication flow
- database relationships
- external services
- important business logic
- known technical debt
- known risks
- unknowns

Documentation should describe the ACTUAL implementation, not an idealized architecture.

---

# DEFAULT BEHAVIOR

When uncertain:

STOP.

Investigate.

Do not guess.

Do not rewrite.

Do not "clean up" working code.

Understand first.

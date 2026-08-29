---
name: project-takeover
description: Reverse-engineer an existing working AI/vibe-coded project without modifying application behavior.
triggers:
  - user
---

# Project Takeover

You are taking ownership of an existing software project.

The project is already functional.

Your job is NOT to rebuild it.

Your job is to determine:

> What exists?
> How does it work?
> Why does it work?
> What depends on what?
> Where are the risks?
> What do we not know?

## HARD RULE

DO NOT MODIFY APPLICATION CODE DURING THIS SKILL.

Discovery only.

---

# PHASE 1 — REPOSITORY MAP

Identify:

- languages
- frameworks
- package managers
- application entry points
- frontend
- backend
- workers
- scripts
- configuration
- tests
- database
- deployment
- infrastructure

Create a concise repository map.

---

# PHASE 2 — FEATURE INVENTORY

Identify the actual user-facing features.

For each feature determine:

- entry point
- relevant UI
- API calls
- backend logic
- database interaction
- external services
- authentication requirements
- tests

Do not rely only on README documentation.

Trace the implementation.

---

# PHASE 3 — ARCHITECTURE

Reconstruct the actual architecture.

Identify:

- components
- modules
- services
- utilities
- API layers
- database layer
- external integrations
- state management
- authentication
- authorization

Create a Mermaid architecture diagram if useful.

---

# PHASE 4 — DATA FLOW

For each important workflow:

Trace:

INPUT
→ VALIDATION
→ TRANSFORMATION
→ BUSINESS LOGIC
→ STORAGE
→ EXTERNAL SERVICES
→ RESPONSE
→ UI

Document important side effects.

---

# PHASE 5 — API INVENTORY

Find every important:

- route
- endpoint
- server action
- RPC
- webhook
- external API call

For each record:

- location
- caller
- authentication
- authorization
- input
- validation
- output
- database interaction
- external services
- error handling

---

# PHASE 6 — DATABASE

Map:

- tables
- collections
- relationships
- migrations
- ORM
- queries
- indexes
- constraints

Identify which application features interact with each entity.

---

# PHASE 7 — AUTHENTICATION

Trace:

login
→ session
→ token/cookie
→ middleware
→ protected route
→ authorization
→ resource ownership

Explicitly distinguish authentication from authorization.

---

# PHASE 8 — AI-SLOP ANALYSIS

Look for:

- duplicated implementations
- dead code
- unused dependencies
- unnecessary abstractions
- hallucinated APIs
- inconsistent patterns
- hardcoded values
- magic numbers
- swallowed exceptions
- incomplete features
- placeholder implementations
- duplicated requests
- race conditions
- state synchronization problems
- contradictory implementations

For every finding provide:

Evidence
→ Actual usage
→ Why it exists if discoverable
→ Risk
→ Confidence

Do not call something "bad code" simply because it is unconventional.

---

# PHASE 9 — SECURITY

Perform a passive security review.

Check:

- secrets
- authentication
- authorization
- IDOR
- injection
- XSS
- CSRF
- SSRF
- file uploads
- command execution
- sensitive data exposure
- dependency risks
- insecure defaults
- rate limiting
- webhook validation
- privilege escalation
- LLM prompt/tool risks

Do not modify anything.

---

# PHASE 10 — TESTING

Identify:

- unit tests
- integration tests
- E2E tests
- API tests

Map tests to important workflows.

Identify unprotected high-risk functionality.

---

# PHASE 11 — GIT HISTORY

Where useful, inspect git history.

Determine:

- major changes
- recently introduced components
- abandoned code
- frequently modified files
- suspicious duplicated implementations
- reverted functionality

Use history as evidence, not proof of correctness.

---

# PHASE 12 — DOCUMENTATION

Create or update:

docs/PROJECT-TAKEOVER.md
docs/ARCHITECTURE.md
docs/API-INVENTORY.md
docs/DATA-FLOW.md
docs/SECURITY-REVIEW.md
docs/TECHNICAL-DEBT.md

Do not modify application behavior.

---

# FINAL REPORT

PROJECT-TAKEOVER.md must contain:

1. What the application does
2. Technology stack
3. Repository structure
4. Actual architecture
5. Major workflows
6. Data flows
7. API inventory
8. Database
9. Authentication
10. External services
11. Configuration
12. Security findings
13. AI-generated-code findings
14. Technical debt
15. Testing
16. Deployment
17. High-risk areas
18. Unknowns
19. Recommended next actions

End with:

## CONFIDENCE MAP

HIGH CONFIDENCE

Things directly verified from source/runtime/tests.

MEDIUM CONFIDENCE

Things strongly inferred from multiple pieces of evidence.

LOW CONFIDENCE

Things inferred but not fully verified.

UNKNOWN

Things that require additional investigation.

Never hide uncertainty.
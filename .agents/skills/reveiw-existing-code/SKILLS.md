---
name: review-existing-code
description: Review existing AI/vibe-coded software for correctness, security, maintainability and hidden risks without rewriting it.
triggers:
  - user
---

# Review Existing Code

The purpose of this review is NOT to make the code look cleaner.

The purpose is to determine whether the existing implementation is:

- correct
- safe
- understandable
- maintainable
- sufficiently tested
- robust

---

# REVIEW ORDER

## 1. Correctness

Look for:

- incorrect logic
- edge cases
- race conditions
- state inconsistencies
- incorrect assumptions
- broken error handling

## 2. Security

Look for:

- authentication failures
- authorization failures
- IDOR
- injection
- XSS
- secrets
- unsafe file handling
- sensitive data exposure

## 3. Reliability

Look for:

- swallowed errors
- missing retries
- unsafe external calls
- missing transaction handling
- race conditions
- failure paths

## 4. Maintainability

Look for:

- duplication
- excessive coupling
- dead code
- unclear ownership
- inconsistent patterns
- unnecessary abstractions

## 5. Testing

Identify:

- important untested paths
- fragile tests
- missing integration tests
- missing regression tests

---

# AI-SLOP DETECTION

Specifically investigate:

- code that looks generated but is unused
- duplicate functions
- multiple implementations of the same feature
- fake/generalized abstractions
- unused parameters
- unused dependencies
- copied patterns that don't match the architecture
- comments that contradict implementation
- TODOs hiding incomplete behavior
- "temporary" code that became permanent

---

# FINDING FORMAT

For every finding:

### [SEVERITY] Finding

Location:

Evidence:

Observed behavior:

Why it matters:

Confidence:

Recommended action:

Do NOT recommend a rewrite unless the existing implementation is actually causing a problem.

---

# FINAL SUMMARY

Separate:

CRITICAL
HIGH
MEDIUM
LOW
OBSERVATION

Also provide:

"Things that look ugly but are currently working"

This section is important.

Do not create work unnecessarily.
# SCREEN 8 of 28: Users — /users

## Rationale

This screen implements the v1.6 design system for user management with avatar+name pattern, table layout, and role badge handling. It follows the v1.2 table pattern established in Schools, with multi-value role fields handled as badge lists with truncation. The screen is designed for admin users to scan and manage user accounts across the organization.

The avatar+name pattern confirms the v1.1 design system precedent (--text-h3/weight 700 adjacent to 40px avatar) at scale. Multi-value fields (roles) are not sortable per v1.6, as sorting by a multi-value field is ambiguous. The "Archive" action label is retained (vs "Deactivate" for Schools) per v1.6 lifecycle-label unification rule, since the underlying field is `archived_at` (distinct from Schools' `deactivated_at`).

One implementation decision requires clarification: the "+N more" role-badge truncation currently shows the truncated count but does not provide inline expansion or link-out behavior. This should be resolved based on UX requirements - either expand inline on click, link to a user detail view, or keep as informational only.

## Layout — Desktop (1440px)

**Page header**: H1 "Users", "Create User" button (primary, right-aligned)

**Filter row**: School filter + Department filter (both searchable selects, "All" default) - follows v1.4 filter-not-group logic since Users has identical parent-entity-scoping shape as Departments

**Table columns**:
- Avatar+Name (avatar 40px --ink-900/white initials, name --text-h3 weight 700 per v1.1, link-styled --gold-600 on hover; sortable)
- Email (--text-small, unsorted - lookup field per v1.2)
- Roles (badge row, --paper-1 bg pills, --text-micro; wraps to 2 lines max before truncating to "+N more" - unsorted, since sorting by a multi-value field is ambiguous per v1.6)
- Status (badge, RAG vocabulary - Active --moss-600/--moss-100, Inactive --ink-300/--paper-1; sortable)
- Created (sortable)
- Actions (Edit, Deactivate icon-buttons - unified label per v1.8 based on default-query behavior)
- Row-expand (chevron, row-start, separate hit target from Name link per v1.2): reveals School, Department, Phone, Employee ID, MFA Enabled status, full role list if truncated

**Default sort**: Name ascending
**Row height**: 40px
**Table styling**: Sticky header, border-divided, no zebra striping

## Layout — Tablet (768px)

Per v1.2 table pattern:
- Condense to Avatar+Name, Status, Actions visible
- Email, Roles, Created → row-expand
- Filter row (School, Department) stays visible
- Row height: 44px

## Layout — Mobile (390px)

Per v1.2 table pattern:
- Stacked accordion cards
- Top row: avatar + name (--text-h3/700) + Status badge
- Expand reveals: Email, Roles (as wrapped badge list), School, Department, Phone, Employee ID, MFA, Created
- Edit/Archive as full-width 44px buttons in expanded state
- Filters collapse to full-width dropdowns above list
- Pagination: "Page X of Y"

## Color/Typography

**Fully inherits from v1.1 avatar+name pattern and v1.2 table pattern** - no new tokens required

**Avatar+Name**:
- Avatar: 40px circle, --ink-900 background, --surface text, weight 700
- Name: --text-h3, weight 700, --ink-900, letter-spacing -0.02em
- Link hover: --gold-600

**Role badges**:
- Background: --paper-1
- Text: --ink-700
- Border: 1px solid --line
- Font: --text-micro, weight 500
- Truncation: "+N more" in --ink-100/--ink-500, italic

**Status badges**:
- Active: --moss-100 background, --moss-600 text, 1px solid rgba(63, 107, 82, 0.2)
- Archived: --paper-1 background, --ink-300 text, 1px solid --line

## Copy

**Kept**:
- "Create User" button
- All field labels (Email, Roles, Status, Created, Actions)
- Role names (SuperAdmin, Admin, Checker, Auditor, Viewer)

**Changed**:
- Action button: "Archive" → "Deactivate" (unified per v1.8 based on default-query behavior)
- Status badge: "Archived" → "Inactive" (unified per v1.8 to match Schools' existing language)

**Added**:
- Filter row labels ("School", "Department")
- Empty state messages for filters
- Pagination format "Page X of Y" for mobile

## Open Items Requiring Resolution

### Role Badge Truncation Behavior ✅ RESOLVED
**Question**: When role badges truncate to "+N more", what should happen when users interact with it?

**Answer**: The "+N more" pill is purely informational (no cursor pointer, no click handler). The row-expand chevron is the one and only way to see the full role list. This avoids redundant interactive affordances on the same row.

**Implementation**: Badge truncation shows count, expansion happens via existing row-expand chevron that reveals "full role list if truncated" per Layout section.

### Archive vs. Deactivate Label Unification ✅ RESOLVED
**Decision**: Unify labels to "Deactivate"/"Inactive" per v1.8. Different column names (archived_at vs deactivated_at) are schema history, not semantic distinction that should surface in UI.

**Justification**: Both Users and Schools have identical default-query behavior (inactive records remain visible in default list with status badges). v1.8 rule: same default-visibility behavior → same label, regardless of column name.

**Changes Applied**:
- Users: "Archive" → "Deactivate", "Archived" → "Inactive"
- Departments: Already using "Deactivate"/"Deactivated" labels (no change needed)
- Schools: Already using "Deactivate"/"Inactive" labels (no change needed)

---

## 🔴 CRITICAL: Clerk Integration (Affects Screen 9)

The User Form (Screen 9) requires Clerk integration pattern clarification before it can be finalized. This does not affect Screen 8 but blocks Screen 9 completion.

**Question**: Does this app create users via Clerk directly (invite sent through Clerk's dashboard/API, clerk_user_id attached automatically via webhook or on first login), or does it maintain a separate internal user table that an admin populates manually and reconciles with Clerk afterward?

**Schema Verification**: Users table has `clerk_user_id` field (shared/models.py line 137), confirming Clerk integration exists.

**Options**:
1. **Clerk-invite-first**: Create form captures email (to send Clerk invite) + role/school/department (pre-configure access), clerk_user_id auto-populates after user completes signup. User listed as "Pending" until invite accepted. ID field should NOT be manual text input.

2. **Admin-populated-and-reconciled**: Create form includes manual clerk_user_id entry, internal user table populated by admin, reconciled with Clerk afterward. Need defined behavior for mismatch/blank scenarios (linkage error, manual "link Clerk account" action, etc.).

**Current Implementation**: User Form incorrectly treats clerk_user_id as required manual field.

**Action Required**: Confirm with Clerk integration owner before finalizing Screen 9.

**Status**: Screen 8 is locked (all open items resolved). Screen 9 remains unlocked pending Clerk answer.

## 🎨 RUNNING DESIGN SYSTEM (v1.8)

**Avatar+Name precedent closed**: Users now confirms the v1.1 pattern (--text-h3/weight 700 adjacent to 40px avatar) at scale. This is now "the pattern," not a pending check.

**Multi-value fields rule**: Badge lists like Roles are never sortable — only scalar fields (name, status, single date) get sort affordances. Applies to any future multi-select/tag-like column.

**Lifecycle-label unification (v1.8 corrected)**: Field names don't matter, only default-query behavior does. Same default-visibility behavior (row stays in the list either way) → same label, regardless of what the timestamp column is called. Users and Schools now unified to "Deactivate"/"Inactive" despite different column names (archived_at vs deactivated_at).

**Filter-not-group pattern**: Filter rows without group headings (School + Department filters) follow v1.4 pattern for parent-entity-scoped data.

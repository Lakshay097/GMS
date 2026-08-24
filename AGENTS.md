# Design System Patterns and Notes

## 🎨 Reusable Patterns

### Interactive Summary Card
**Pattern Definition**: Gold-600 3px left border, hover → paper-1, arrow-right icon top-right, cursor pointer

**Usage**: Dashboard summary cards, will likely recur on Discrepancy Detail and Approval Chains

**CSS Classes**:
```css
.interactive-summary-card {
  border-left: 3px solid var(--gold-600);
  background: var(--surface);
  padding: var(--space-4);
  cursor: pointer;
  transition: background 0.2s var(--ease);
}

.interactive-summary-card:hover {
  background: var(--paper-1);
}

.interactive-summary-card__arrow {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  color: var(--gold-600);
}
```

**Components using this pattern**:
- Dashboard summary cards
- Discrepancy Detail (future)
- Approval Chains (future)

### SearchableSelect Component
**Pattern Definition**: Shared component for entity selection with client/server filtering

**Features**:
- Client-side filtering for datasets under ~200 records (Schools, Departments)
- Server-side debounced search (300ms) for large datasets (Users)
- Empty state copy for zero matches
- Display convention for unset optional relations (e.g., "No Department Head assigned")
- Clear button for optional fields

**Props**:
```typescript
interface SearchableSelectProps {
  id: string
  name: string
  value: string
  onChange: (value: string) => void
  options: SearchableSelectOption[]
  placeholder?: string
  disabled?: boolean
  required?: boolean
  loading?: boolean
  onSearch?: (query: string) => void
  useServerSearch?: boolean // Enable server-side search for large datasets
  unsetLabel?: string // Display text for unset optional relation
}
```

**Usage Examples**:
- Department Form: School (client-side), Department Head (client-side with unsetLabel)
- User Form: School (client-side), Department (client-side with dependency)
- Task Form (future): School, Department, Assignee (server-side for users)
- Approval Chains (future): Role selectors

## 📋 Watch Items

### Role-Dependent Expand/Collapse Defaults
**Watch Item**: Section expand/collapse defaults may end up role-dependent

**Context**: Checker vs. Auditor likely prioritize different sections on Dashboard

**Action Item**: Revisit only if usage data shows a role consistently re-opening a "default collapsed" section

**Priority**: Low (not a v1 build item, usage-data driven)

## 🔍 Open Questions for Data Model Owner

### Archive vs. Deactivate Label Unification ✅ RESOLVED
**Decision**: Unify labels to "Deactivate"/"Inactive" per v1.8. Different column names (archived_at vs deactivated_at) are schema history, not semantic distinction that should surface in UI.

**Justification**: Both Users and Schools have identical default-query behavior (inactive records remain visible in default list with status badges). v1.8 rule: same default-visibility behavior → same label, regardless of column name.

**Changes Applied**:
- Users: "Archive" → "Deactivate", "Archived" → "Inactive"
- Departments: Already using "Deactivate"/"Deactivated" labels (confirmed DepartmentList.tsx uses "Deactivate" and maps archived_at to "Deactivated" display)
- Schools: Already using "Deactivate"/"Inactive" labels (no change needed)

### Clerk Integration Pattern (Affects Screen 9)
**Question**: Does this app create users via Clerk directly or maintain separate internal user table?

**Schema**: Users table has `clerk_user_id` field (shared/models.py line 137), confirming Clerk integration.

**Options**:
1. **Clerk-invite-first**: Create form captures email + role/school/department, clerk_user_id auto-populates after signup. User listed as "Pending" until invite accepted. ID field should NOT be manual text input.

2. **Admin-populated-and-reconciled**: Create form includes manual clerk_user_id entry, internal table populated by admin, reconciled with Clerk afterward. Need defined behavior for mismatch/blank scenarios.

**Current Implementation**: User Form incorrectly treats clerk_user_id as required manual field.

**Action**: Confirm with Clerk integration owner before finalizing Screen 9.

### Escalation Rules Evaluation Order ✅ RESOLVED
**Question**: When escalation rules overlap (e.g., a school-specific rule vs. an "All Schools" fallback), what order does the backend actually evaluate them in?

**Answer**: Specificity-based evaluation: department-specific → school-wide → global defaults.

**Implementation**: Found in `modules/task_management/services/escalation_scheduler.py` lines 152-178. The `_resolve_escalation_rules` method tries three scopes in order and returns the first non-empty match.

**Action**: Keep the current neutral display - it matches the actual logic.

### Discrepancy Reference ID Format ✅ RESOLVED
**Question**: Does a human-readable short reference number exist for discrepancies (e.g., "DISC-4471"), or is the UUID the only identifier?

**Answer**: No human-readable reference number exists. The Discrepancy model only has a UUID primary key.

**Schema**: `shared/platform_models.py` lines 263-299 shows only `id` field (UUID). No `reference_number` or similar column.

**Action**: Recommend adding a `reference_number` column (e.g., "DISC-4471") for compliance tools that need stable reference formats.

### Category Lookup for Discrepancies ✅ RESOLVED
**Question**: Does the category_id on Discrepancies resolve against the same table that Observations' category_name comes from?

**Answer**: Discrepancies use a dedicated `discrepancy_categories` table.

**Schema**: 
- `discrepancy_categories` table: `shared/platform_models.py` lines 201-210
- `Discrepancy.category_id` references this table: line 273

**Action**: The category lookup is properly implemented via the dedicated table.

### Observation Form Info Banner Copy ✅ RESOLVED
**Question**: What is the actual submission workflow notice text?

**Answer**: The banner text is already implemented in `frontend/src/components/observations/ObservationForm.tsx` lines 226-230.

**Text**: "Important: Once submitted, observations can only be verified or rejected by authorized users. Auditors can raise discrepancies against submitted observations."

**Action**: The text is already in place - no changes needed.

### Complete Signup School Name Accuracy ✅ RESOLVED
**Question**: Are the school name sublabels hardcoded in CompleteSignup.tsx accurate?

**Answer**: **CONFIRMED CORRECT** by data model owner.

**Mappings**: All 12 school codes to campus names are accurate:
- GUR-JAI → Jaipur Campus
- GUR-VAR → Varanasi Campus  
- GUR-MOT → Motihari Campus
- GUR-GWA → Gwalior Campus
- GUR-RAN → Ranchi Campus
- GUR-IND → Indore Campus
- GUR-MUZ → Muzaffarpur Campus
- GUR-GUR → Gurugram Campus
- GUR-FAR → Faridabad Campus
- GUR-LUC → Lucknow Campus
- GUR-SUR → Suratgarh Campus
- GUR-BHO → Bhopal Campus

**Action**: No changes needed - mappings are verified accurate.

### Global Search Scope ✅ RESOLVED
**Question**: What does the search index actually match per entity type? Is it title+description, or something else?

**Answer**: Search scope is entity-specific and well-defined in `modules/dashboards-reports-search/services/search_indexer.py` lines 49-104.

**Fields per entity type**:
- **observation**: kpi_title, department_name, school_name, checker_name, value_text
- **task**: title, description, school_name, department_name
- **discrepancy**: category_name, investigation_findings, school_name, department_name
- **kpi**: title, unit_of_measure, category_code, kra_name
- **user**: full_name, email, employee_id, school_name, department_name
- **school**: name, code, address, contact_email
- **department**: name, code, description, school_name

**Action**: The current search scope hint text should be accurate based on this configuration.

### Entity Types for Task Form ⚠️ NEEDS CONFIRMATION
**Question**: Is this the correct list of valid entity types for tasks?

**Current frontend list**: `discrepancy`, `observation`, `kpi`, `task` (TaskForm.tsx lines 24-29)

**Backend**: Accepts any string value for `entity_type` (Optional[str], no validation in API schema)

**Concern**: The frontend list may be incomplete or inaccurate since the backend doesn't validate against a specific enum.

**Action**: Please confirm with backend ownership what the valid values for `entity_type` on tasks should be. If the list is wrong or incomplete, the frontend select options need to be updated.

## 🎯 Design System Version Notes

### v1.5 - No Raw ID Entry
**Rule**: Any field that references another entity must render as a searchable select resolving to a human-readable label, never a free-text ID field

**Exception**: Opaque external/system identifiers (not references to another in-app entity) stay as disabled text inputs

**Test**: Is there another entity in this app with a name I could resolve to? If yes → select. If it's an external system key with nothing to resolve to → text input, disabled after creation, with tooltip explaining why.

### v1.6 - Multi-Value Fields Not Sortable
**Rule**: Multi-value fields (badge lists like Roles) are never sortable — only scalar fields (name, status, single date) get sort affordances

### v1.8 - Lifecycle Label Unification (Corrected)
**Rule**: Lifecycle labels should be unified based on default-query behavior, not field names. Different column names (archived_at vs deactivated_at) are schema history, not semantic distinction that should surface in UI.

**Test**: Do inactive records stay visible in the default list by default? If yes → use same label regardless of what the timestamp column is called. Same default-visibility behavior → same label.

**Application**: 
- Users: "Deactivate" / "Inactive" (was "Archive" / "Archived")
- Schools: "Deactivate" / "Inactive" (unchanged)
- Departments: "Deactivate" / "Inactive" (was "Archive" / "Archived")

### v1.7 - Role Descriptions Required
**Rule**: Any screen presenting selectable roles or permission levels should show a short description alongside the name, not just the label

**Current Status**: User Form role descriptions removed (placeholder copy) - awaiting real sign-off from role/permission owner

## 🛠️ Build and Verification Commands

### Frontend
```bash
cd frontend
npm run dev          # Start development server
npm run build        # Build for production
npm run lint         # Run ESLint
npm run type-check   # Run TypeScript type checking
```

### Backend
```bash
# Python backend verification
python -m pytest    # Run tests
python -m flake8    # Lint Python code
```

## 📝 Screen Implementation Status

- ✅ Screen 1: Dashboard
- ✅ Screen 3: Department Form (v1.5 searchable selects)
- ✅ Screen 4: Schools List  
- ✅ Screen 5: School Form
- ✅ Screen 7: Department Form (enhanced with shared SearchableSelect)
- ✅ Screen 8: Users List (v1.6 avatar+name pattern, table layout)
- ✅ Screen 9: User Form (v1.7 role descriptions removed, awaiting auth flow confirmation)
- ⏳ Screen 10: Dashboard (confirmed, interactive summary card pattern documented)
- ⏳ Screen 11+: Pending

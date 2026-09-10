/**
 * Frontend permission resolution — R-48 single source of truth.
 *
 * Every capability flag comes from the backend permission matrix, delivered
 * on the session payload (`/auth/get-session` → `user.capabilities`, built by
 * `shared/permissions.py → PermissionMatrix.capabilities_for_roles`). The
 * backend is the enforcement point, so the frontend keeps NO role→permission
 * literals of its own: the UI shows exactly what the backend enforces.
 *
 * When `capabilities` is absent (context default before the session loads,
 * stale snapshots, unit tests) every flag resolves to least privilege
 * (false) — never to a guessed role table.
 */

import type { Capabilities } from './auth'

/** Known platform roles. A naming type only — it carries NO permissions. */
export type RoleName = 'superadmin' | 'admin' | 'dept_head' | 'checker' | 'auditor' | 'viewer'

export interface RolePermissions {
  /** Can view data */
  canView: boolean
  /** Can create new records */
  canCreate: boolean
  /** Can edit existing records */
  canEdit: boolean
  /** Can delete/deactivate records */
  canDelete: boolean
  /** Can export/download data */
  canExport: boolean
  /** Scope: 'all' = entire platform, 'school' = own school only, 'department' = own dept only */
  scope: 'all' | 'school' | 'department'
  /** Specific module permissions — backend-matrix derived */
  modules: {
    dashboard: boolean
    kpiEntry: boolean
    kpiVerification: boolean
    schools: boolean
    departments: boolean
    users: boolean
    observations: boolean
    tasks: boolean
    reports: boolean
    audit: boolean
    kra: boolean
    settings: boolean
    approvalChains: boolean
    escalationRules: boolean
  }
}

/** Everything denied — used when no capability payload is available. */
const LEAST_PRIVILEGE: RolePermissions = {
  canView: false,
  canCreate: false,
  canEdit: false,
  canDelete: false,
  canExport: false,
  scope: 'school',
  modules: {
    dashboard: false,
    kpiEntry: false,
    kpiVerification: false,
    schools: false,
    departments: false,
    users: false,
    observations: false,
    tasks: false,
    reports: false,
    audit: false,
    kra: false,
    settings: false,
    approvalChains: false,
    escalationRules: false,
  },
}

/**
 * Resolve the permissions for the current user from the backend capability
 * payload. `roles` is accepted for call-site compatibility but is
 * intentionally unused — the matrix payload already encodes the merged
 * (most permissive) result of all the user's roles, server-side (R-48).
 */
export function getPermissions(roles: string[], capabilities?: Capabilities): RolePermissions {
  void roles

  if (!capabilities) return LEAST_PRIVILEGE

  const m = capabilities.modules
  return {
    canView: capabilities.canView ?? false,
    canCreate: capabilities.canCreate ?? false,
    canEdit: capabilities.canEdit ?? false,
    canDelete: capabilities.canDelete ?? false,
    canExport: capabilities.canExport ?? false,
    scope: capabilities.scope ?? 'school',
    modules: {
      dashboard: m.dashboard ?? false,
      kpiEntry: m.kpiEntry ?? false,
      kpiVerification: m.kpiVerification ?? false,
      schools: m.schools ?? false,
      departments: m.departments ?? false,
      users: m.users ?? false,
      observations: m.observations ?? false,
      tasks: m.tasks ?? false,
      reports: m.reports ?? false,
      audit: m.audit ?? false,
      kra: m.kra ?? false,
      settings: m.settings ?? false,
      approvalChains: m.approvalChains ?? false,
      escalationRules: m.escalationRules ?? false,
    },
  }
}

/**
 * Check if a user with the given capability payload can access a module.
 */
export function canAccessModule(capabilities: Capabilities | undefined, module: keyof RolePermissions['modules']): boolean {
  const perms = getPermissions([], capabilities)
  return perms.canView && perms.modules[module]
}

/**
 * Check if a user can perform write operations.
 */
export function canWrite(capabilities: Capabilities | undefined): boolean {
  const perms = getPermissions([], capabilities)
  return perms.canCreate || perms.canEdit || perms.canDelete
}

// ── Role assignment hierarchy ─────────────────────────────────────────────
//
// Mirrors shared/permissions.py → ROLE_HIERARCHY exactly.
// Used ONLY for UI filtering — the backend enforces the real check on every
// write. Never use this map to gate API calls or trust client decisions.

const ROLE_HIERARCHY: Record<string, string[]> = {
  superadmin: ['admin', 'dept_head', 'auditor', 'verifier', 'checker', 'viewer'],
  admin:      ['dept_head', 'auditor', 'verifier', 'checker', 'viewer'],
  dept_head:  ['auditor', 'verifier', 'checker', 'viewer'],
  auditor:    [],
  verifier:   [],
  checker:    [],
  viewer:     [],
}

/**
 * Ordered display metadata for every platform role.
 * Used to render role checkboxes / selects in the correct hierarchy order.
 */
export const ALL_ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: 'superadmin', label: 'SuperAdmin' },
  { value: 'admin',      label: 'Admin' },
  { value: 'dept_head',  label: 'Department Head' },
  { value: 'auditor',    label: 'Auditor' },
  { value: 'verifier',   label: 'Verifier' },
  { value: 'checker',    label: 'Checker' },
  { value: 'viewer',     label: 'Viewer' },
]

/**
 * Returns the role options the actor may assign, given their own roles.
 *
 * Rules (matching backend ROLE_HIERARCHY):
 *   - superadmin → can assign any role including admin
 *   - admin      → can assign dept_head and below
 *   - dept_head  → can assign auditor / verifier / checker / viewer
 *   - others     → empty (they cannot create/edit users at all)
 *
 * The returned list preserves the canonical display order from ALL_ROLE_OPTIONS.
 */
export function assignableRoles(actorRoles: string[]): { value: string; label: string }[] {
  const assignable = new Set<string>()
  for (const role of actorRoles) {
    const subordinates = ROLE_HIERARCHY[(role ?? '').toLowerCase()] ?? []
    for (const r of subordinates) assignable.add(r)
  }
  // superadmin can also assign superadmin (manage platform admins)
  if (actorRoles.some(r => r.toLowerCase() === 'superadmin')) {
    assignable.add('superadmin')
  }
  return ALL_ROLE_OPTIONS.filter(opt => assignable.has(opt.value))
}

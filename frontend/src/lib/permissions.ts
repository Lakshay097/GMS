/**
 * Central Role Permissions Configuration
 * 
 * Adjust capabilities per role here. The rest of the app reads from this config.
 * To tighten: remove permissions from a role.
 * To loosen: add permissions to a role.
 * To add a role: add it to RoleName and assign permissions below.
 */

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
  /** Specific module permissions */
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

const ROLE_PERMISSIONS: Record<RoleName, RolePermissions> = {
  superadmin: {
    canView: true,
    canCreate: true,
    canEdit: true,
    canDelete: true,
    canExport: true,
    scope: 'all',
    modules: {
      dashboard: true,
      kpiEntry: true,
      kpiVerification: true,
      schools: true,
      departments: true,
      users: true,
      observations: true,
      tasks: true,
      reports: true,
      audit: true,
      kra: true,
      settings: true,
      approvalChains: true,
      escalationRules: true,
    },
  },
  admin: {
    canView: true,
    canCreate: true,
    canEdit: true,
    canDelete: true,
    canExport: true,
    scope: 'all',
    modules: {
      dashboard: true,
      kpiEntry: true,
      kpiVerification: true,
      schools: true,
      departments: true,
      users: true,
      observations: true,
      tasks: true,
      reports: true,
      audit: true,
      kra: true,
      settings: true,
      approvalChains: true,
      escalationRules: true,
    },
  },
  dept_head: {
    canView: true,
    canCreate: true,
    canEdit: true,
    canDelete: false,
    canExport: true,
    scope: 'department',
    modules: {
      dashboard: true,
      kpiEntry: true,
      kpiVerification: false,
      schools: false,
      departments: false,
      users: false,
      observations: true,
      tasks: true,
      reports: true,
      audit: true,
      kra: true,
      settings: false,
      approvalChains: true,
      escalationRules: false,
    },
  },
  checker: {
    canView: true,
    canCreate: false,
    canEdit: false,
    canDelete: false,
    canExport: true,
    scope: 'school',
    modules: {
      dashboard: true,
      kpiEntry: false,
      kpiVerification: true,
      schools: false,
      departments: false,
      users: false,
      observations: true,
      tasks: true,
      reports: true,
      audit: true,
      kra: false,
      settings: false,
      approvalChains: false,
      escalationRules: false,
    },
  },
  auditor: {
    canView: true,
    canCreate: true,
    canEdit: false,
    canDelete: false,
    canExport: true,
    scope: 'school',
    modules: {
      dashboard: true,
      kpiEntry: false,
      kpiVerification: false,
      schools: false,
      departments: false,
      users: false,
      observations: true,
      tasks: true,
      reports: true,
      audit: true,
      kra: false,
      settings: false,
      approvalChains: true,
      escalationRules: false,
    },
  },
  viewer: {
    canView: true,
    canCreate: false,
    canEdit: false,
    canDelete: false,
    canExport: false,
    scope: 'school',
    modules: {
      dashboard: true,
      kpiEntry: false,
      kpiVerification: false,
      schools: false,
      departments: false,
      users: false,
      observations: false,
      tasks: false,
      reports: true,
      audit: false,
      kra: false,
      settings: false,
      approvalChains: false,
      escalationRules: false,
    },
  },
}

/**
 * Get permissions for a list of roles (user may have multiple roles).
 * Returns the most permissive combination of all assigned roles.
 */
export function getPermissions(roles: string[]): RolePermissions {
  const normalizedRoles = roles.map(r => r.toLowerCase().replace(/\s+/g, '_')) as RoleName[]
  const matched = normalizedRoles.filter(r => r in ROLE_PERMISSIONS)

  if (matched.length === 0) {
    // Unknown role gets viewer permissions (least privilege)
    return ROLE_PERMISSIONS.viewer
  }

  // Merge permissions: most permissive wins
  const merged: RolePermissions = {
    canView: matched.some(r => ROLE_PERMISSIONS[r].canView),
    canCreate: matched.some(r => ROLE_PERMISSIONS[r].canCreate),
    canEdit: matched.some(r => ROLE_PERMISSIONS[r].canEdit),
    canDelete: matched.some(r => ROLE_PERMISSIONS[r].canDelete),
    canExport: matched.some(r => ROLE_PERMISSIONS[r].canExport),
    scope: matched.some(r => ROLE_PERMISSIONS[r].scope === 'all')
      ? 'all'
      : matched.some(r => ROLE_PERMISSIONS[r].scope === 'school')
        ? 'school'
        : 'department',
    modules: {
      dashboard: matched.some(r => ROLE_PERMISSIONS[r].modules.dashboard),
      kpiEntry: matched.some(r => ROLE_PERMISSIONS[r].modules.kpiEntry),
      kpiVerification: matched.some(r => ROLE_PERMISSIONS[r].modules.kpiVerification),
      schools: matched.some(r => ROLE_PERMISSIONS[r].modules.schools),
      departments: matched.some(r => ROLE_PERMISSIONS[r].modules.departments),
      users: matched.some(r => ROLE_PERMISSIONS[r].modules.users),
      observations: matched.some(r => ROLE_PERMISSIONS[r].modules.observations),
      tasks: matched.some(r => ROLE_PERMISSIONS[r].modules.tasks),
      reports: matched.some(r => ROLE_PERMISSIONS[r].modules.reports),
      audit: matched.some(r => ROLE_PERMISSIONS[r].modules.audit),
      kra: matched.some(r => ROLE_PERMISSIONS[r].modules.kra),
      settings: matched.some(r => ROLE_PERMISSIONS[r].modules.settings),
      approvalChains: matched.some(r => ROLE_PERMISSIONS[r].modules.approvalChains),
      escalationRules: matched.some(r => ROLE_PERMISSIONS[r].modules.escalationRules),
    },
  }

  return merged
}

/**
 * Check if a user with given roles can access a specific module.
 */
export function canAccessModule(roles: string[], module: keyof RolePermissions['modules']): boolean {
  const perms = getPermissions(roles)
  return perms.canView && perms.modules[module]
}

/**
 * Check if a user can perform write operations.
 */
export function canWrite(roles: string[]): boolean {
  const perms = getPermissions(roles)
  return perms.canCreate || perms.canEdit || perms.canDelete
}

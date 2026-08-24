import { useUser } from '@clerk/clerk-react'
import { getPermissions, type RolePermissions, type RoleName } from '../../lib/permissions'
import React from 'react'

interface RoleGuardProps {
  /** Required roles — user must have at least one of these */
  roles?: RoleName[]
  /** Required permission check — user must have this capability */
  requires?: {
    canCreate?: boolean
    canEdit?: boolean
    canDelete?: boolean
    canExport?: boolean
    module?: keyof RolePermissions['modules']
  }
  /** What to render when access is denied (defaults to nothing) */
  fallback?: React.ReactNode
  /** The content to render when access is granted */
  children: React.ReactNode
}

/**
 * Conditionally renders children based on the user's role permissions.
 *
 * Usage:
 *   <RoleGuard roles={['admin', 'superadmin']}>
 *     <button>Create User</button>
 *   </RoleGuard>
 *
 *   <RoleGuard requires={{ canEdit: true, module: 'schools' }}>
 *     <EditButton />
 *   </RoleGuard>
 *
 *   <RoleGuard requires={{ module: 'reports' }} fallback={<p>No access</p>}>
 *     <ReportPage />
 *   </RoleGuard>
 */
export default function RoleGuard({ roles, requires, fallback = null, children }: RoleGuardProps) {
  const { user } = useUser()
  const userRoles = (user?.publicMetadata?.roles as string[]) || []
  const perms = getPermissions(userRoles)

  // Check role-based access
  if (roles && roles.length > 0) {
    const normalizedUserRoles = userRoles.map(r => r.toLowerCase().replace(/\s+/g, '_'))
    const hasRequiredRole = roles.some(role => normalizedUserRoles.includes(role))
    if (!hasRequiredRole) return <>{fallback}</>
  }

  // Check permission-based access
  if (requires) {
    if (requires.canCreate !== undefined && perms.canCreate !== requires.canCreate) {
      return <>{fallback}</>
    }
    if (requires.canEdit !== undefined && perms.canEdit !== requires.canEdit) {
      return <>{fallback}</>
    }
    if (requires.canDelete !== undefined && perms.canDelete !== requires.canDelete) {
      return <>{fallback}</>
    }
    if (requires.canExport !== undefined && perms.canExport !== requires.canExport) {
      return <>{fallback}</>
    }
    if (requires.module && !perms.modules[requires.module]) {
      return <>{fallback}</>
    }
  }

  return <>{children}</>
}

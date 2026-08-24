/**
 * AuthContext — single source of truth for user roles, school, and department.
 *
 * Reads from the backend /auth/get-session endpoint (Neon DB), NOT from
 * Clerk's publicMetadata.  This means Clerk only stores email + password
 * for authentication; Neon owns all authorization data.
 *
 * Usage:
 *   const { roles, schoolId, departmentId, loading } = useAuthContext()
 */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { getPermissions, type RolePermissions } from '../lib/permissions'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  roles: string[]
  school_id: string | null
  department_id: string | null
  mfa_enabled: boolean
}

export interface AuthContextValue {
  /** User data from the backend (null while loading or if not provisioned) */
  user: AuthUser | null
  /** User roles array (empty while loading) */
  roles: string[]
  /** Computed permissions derived from roles */
  perms: RolePermissions
  /** User's school ID (from Neon DB) */
  schoolId: string | null
  /** User's department ID (from Neon DB) */
  departmentId: string | null
  /** True while the initial session fetch is in-flight */
  loading: boolean
  /** Re-fetch session data (e.g. after role change) */
  refresh: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  roles: [],
  perms: getPermissions([]),
  schoolId: null,
  departmentId: null,
  loading: true,
  refresh: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchSession = useCallback(async () => {
    if (!isSignedIn) {
      setUser(null)
      setLoading(false)
      return
    }

    try {
      const token = await getToken()
      const res = await fetch('/auth/get-session', {
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })

      if (res.ok) {
        const data = await res.json()
        if (data.valid && data.user) {
          console.log('AuthContext: session loaded', { email: data.user.email, roles: data.user.roles })
          setUser({
            id: data.user.id,
            email: data.user.email,
            full_name: data.user.full_name,
            roles: data.user.roles || [],
            school_id: data.user.school_id,
            department_id: data.user.department_id,
            mfa_enabled: data.user.mfa_enabled ?? false,
          })
        } else {
          console.warn('AuthContext: session invalid', data)
          setUser(null)
        }
      } else {
        console.warn('AuthContext: get-session returned', res.status)
        setUser(null)
      }
    } catch (err) {
      console.error('AuthContext: failed to fetch session', err)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [isSignedIn, getToken])

  // Fetch session on mount and when auth state changes
  useEffect(() => {
    if (isLoaded) {
      fetchSession()
    }
  }, [isLoaded, fetchSession])

  const roles = user?.roles || []
  const perms = getPermissions(roles)

  return (
    <AuthContext.Provider
      value={{
        user,
        roles,
        perms,
        schoolId: user?.school_id ?? null,
        departmentId: user?.department_id ?? null,
        loading,
        refresh: fetchSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Access the authenticated user's roles, school, and department from Neon DB.
 * Drop-in replacement for reading Clerk's publicMetadata.
 */
export function useAuthContext(): AuthContextValue {
  return useContext(AuthContext)
}

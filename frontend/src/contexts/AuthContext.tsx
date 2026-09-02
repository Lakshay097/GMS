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
  /** True if the session fetch failed (429, network error, etc.) — distinct from "not provisioned" */
  error: boolean
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
  error: false,
  refresh: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

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

      setError(false)
      if (res.ok) {
        const data = await res.json()
        if (data.valid && data.user) {
          console.log('AuthContext: session loaded', { email: data.user.email, roles: data.user.roles })
          // Defensive: ensure roles is always an array of strings.
          // JSONB can return a string, null, or array depending on how it was stored.
          const rawRoles = data.user.roles
          const normalizedRoles: string[] = Array.isArray(rawRoles)
            ? rawRoles.map((r: any) => String(r).toLowerCase().replace(/\s+/g, '_'))
            : typeof rawRoles === 'string' && rawRoles
              ? [rawRoles.toLowerCase().replace(/\s+/g, '_')]
              : []
          setUser({
            id: data.user.id,
            email: data.user.email,
            full_name: data.user.full_name,
            roles: normalizedRoles,
            school_id: data.user.school_id,
            department_id: data.user.department_id,
            mfa_enabled: data.user.mfa_enabled ?? false,
          })
        } else {
          console.warn('AuthContext: session invalid', data)
          setUser(null)
          // Don't set error — the session was fetched but user isn't provisioned
        }
      } else {
        // Non-OK status (429, 500, etc.) — treat as transient error, NOT "not provisioned"
        console.warn('AuthContext: get-session returned', res.status)
        setError(true)
        // Don't clear user if we already have one (stale-but-valid is better than flash-redirect)
      }
    } catch (err) {
      // Network error — treat as transient, NOT "not provisioned"
      console.error('AuthContext: failed to fetch session', err)
      setError(true)
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
        error,
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

/**
 * AuthContext — single source of truth for authentication state, user roles,
 * school, and department.
 *
 * Fully self-managed: sessions are HTTP-only cookies issued by the FastAPI
 * backend (Neon PostgreSQL-backed). There is no external identity provider —
 * components only see the useAuth() abstraction.
 *
 * Usage:
 *   const { user, isAuthenticated, loading, login, logout, roles, perms } = useAuth()
 */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import * as authClient from '../lib/auth'
import { getPermissions, type RolePermissions } from '../lib/permissions'

export type AuthUser = authClient.SessionUser

export interface AuthContextValue {
  /** Authenticated user (null while loading or signed out) */
  user: AuthUser | null
  /** True if a valid session exists */
  isAuthenticated: boolean
  /** True while the initial session check is in-flight */
  loading: boolean
  /** True if the session check failed (network/5xx) — distinct from "signed out" */
  error: boolean
  /** User roles array (empty while loading) */
  roles: string[]
  /** Computed permissions derived from roles */
  perms: RolePermissions
  /** User's school ID (from the DB) */
  schoolId: string | null
  /** User's department ID (from the DB) */
  departmentId: string | null
  /** Sign in with email + password */
  login: (email: string, password: string) => Promise<void>
  /** Sign out (invalidates the server-side session) */
  logout: () => Promise<void>
  /** Re-fetch session data (e.g. after role change) */
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAuthenticated: false,
  loading: true,
  error: false,
  roles: [],
  perms: getPermissions([]),
  schoolId: null,
  departmentId: null,
  login: async () => {},
  logout: async () => {},
  refresh: async () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const fetchSession = useCallback(async (attempt = 0) => {
    const MAX_RETRIES = 3
    const BASE_DELAY_MS = 1000

    try {
      const data = await authClient.getSession()

      if (data.valid && data.user) {
        const rawRoles: unknown = data.user.roles
        const normalizedRoles: string[] = Array.isArray(rawRoles)
          ? rawRoles.map((r: unknown) => String(r).toLowerCase().replace(/\s+/g, '_'))
          : typeof rawRoles === 'string' && rawRoles
            ? [(rawRoles as string).toLowerCase().replace(/\s+/g, '_')]
            : []
        setUser({
          ...data.user,
          roles: normalizedRoles,
          mfa_enabled: data.user.mfa_enabled ?? false,
        })
        setError(false)
      } else {
        setUser(null)
      }
    } catch (err) {
      // Network error — treat as transient, NOT "signed out"
      console.error('AuthContext: failed to fetch session', err)
      setError(true)
    } finally {
      setLoading(false)
    }
    void attempt
    void MAX_RETRIES
    void BASE_DELAY_MS
  }, [])

  // Fetch session on mount (setState happens inside the async callback,
  // not synchronously in the effect body)
  useEffect(() => {
    void Promise.resolve().then(() => fetchSession())
  }, [fetchSession])

  const login = useCallback(async (email: string, password: string) => {
    await authClient.login(email, password)
    await fetchSession()
  }, [fetchSession])

  const logout = useCallback(async () => {
    await authClient.logout()
    setUser(null)
  }, [])

  const roles = user?.roles || []
  const perms = getPermissions(roles, user?.capabilities)

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        loading,
        error,
        roles,
        perms,
        schoolId: user?.school_id ?? null,
        departmentId: user?.department_id ?? null,
        login,
        logout,
        refresh: fetchSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Access the authenticated user's identity, roles, school, and department.
 * Drop-in replacement for Clerk's useAuth / useUser combination.
 */
export function useAuthContext(): AuthContextValue {
  return useContext(AuthContext)
}

/** Canonical name for the auth hook — business components use this. */
export const useAuth = useAuthContext

/**
 * SchoolContext — single source of truth for the "active school" across the app.
 *
 * For non-SuperAdmin roles: the school is fixed to their AuthContext.schoolId
 *   and cannot be changed (they only have access to one school).
 *
 * For SuperAdmin: the school is stored in localStorage so it persists across
 *   page reloads. SuperAdmin can switch schools via the global school switcher
 *   in the top bar. This eliminates the per-form school selector.
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'
import { useAuthContext } from './AuthContext'
import { apiFetch } from '../lib/api'

export interface School {
  id: string
  name: string
  code?: string
  school_code?: string
}

interface SchoolContextValue {
  /** The currently active school ID (null only while loading or if no schools exist) */
  activeSchoolId: string | null
  /** The full school object for the active school */
  activeSchool: School | null
  /** All schools the user can access (empty for non-SuperAdmin if not loaded) */
  schools: School[]
  /** Whether schools are still loading */
  loading: boolean
  /** True if the current user is a SuperAdmin and can switch schools */
  canSwitch: boolean
  /** Set the active school (only works for SuperAdmin) */
  setActiveSchool: (schoolId: string) => void
  /** Re-fetch the schools list */
  refreshSchools: () => void
}

const LS_KEY = 'schoolops_active_school_id'

const SchoolContext = createContext<SchoolContextValue>({
  activeSchoolId: null,
  activeSchool: null,
  schools: [],
  loading: true,
  canSwitch: false,
  setActiveSchool: () => {},
  refreshSchools: () => {},
})

export function SchoolProvider({ children }: { children: React.ReactNode }) {
  const { user, schoolId: dbSchoolId, roles } = useAuthContext()
  const [schools, setSchools] = useState<School[]>([])
  const [activeSchoolId, setActiveSchoolIdState] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const isSuperAdmin = useMemo(
    () => roles.some(r => r.toLowerCase() === 'superadmin'),
    [roles],
  )

  // ── Fetch schools list ────────────────────────────────────────────────
  const fetchSchools = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/schools?page_size=200')
      if (res.ok) {
        const data = await res.json()
        setSchools(data.data || [])
      }
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    if (user) {
      fetchSchools()
    }
  }, [user, fetchSchools])

  // ── Resolve the active school on mount ────────────────────────────────
  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }

    if (isSuperAdmin) {
      // SuperAdmin: prefer localStorage, fall back to first school in DB
      const stored = localStorage.getItem(LS_KEY)
      if (stored && schools.some(s => s.id === stored)) {
        setActiveSchoolIdState(stored)
      } else if (schools.length > 0) {
        setActiveSchoolIdState(schools[0].id)
        localStorage.setItem(LS_KEY, schools[0].id)
      } else {
        setActiveSchoolIdState(null)
      }
    } else {
      // Non-SuperAdmin: locked to their DB school_id
      setActiveSchoolIdState(dbSchoolId || null)
    }

    setLoading(false)
  }, [user, dbSchoolId, isSuperAdmin, schools])

  // ── Setter (SuperAdmin only) ──────────────────────────────────────────
  const setActiveSchool = useCallback(
    (schoolId: string) => {
      if (!isSuperAdmin) return
      setActiveSchoolIdState(schoolId)
      localStorage.setItem(LS_KEY, schoolId)
    },
    [isSuperAdmin],
  )

  // ── Derived data ──────────────────────────────────────────────────────
  const activeSchool = useMemo(
    () => schools.find(s => s.id === activeSchoolId) || null,
    [schools, activeSchoolId],
  )

  const value: SchoolContextValue = useMemo(
    () => ({
      activeSchoolId,
      activeSchool,
      schools,
      loading,
      canSwitch: isSuperAdmin,
      setActiveSchool,
      refreshSchools: fetchSchools,
    }),
    [activeSchoolId, activeSchool, schools, loading, isSuperAdmin, setActiveSchool, fetchSchools],
  )

  return <SchoolContext.Provider value={value}>{children}</SchoolContext.Provider>
}

/**
 * Access the active school context.
 * All forms should use this instead of fetching + showing their own school selector.
 */
export function useSchoolContext(): SchoolContextValue {
  return useContext(SchoolContext)
}

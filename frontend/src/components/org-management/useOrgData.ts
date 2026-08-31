/**
 * Shared React hooks for fetching org entities.
 * Supports cascading dropdowns: school → department, KRA → KPI.
 */
import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'

export interface School {
  id: string
  name: string
  code: string
  status: string
}

export interface Department {
  id: string
  school_id: string
  name: string
  code: string
  status: string
}

export interface KRA {
  id: string
  name: string
  description?: string
  status: string
}

export interface KPI {
  kpi_id: string
  version: number
  kra_id: string
  title: string
  description?: string
  target_value: number
  comparator: string
  unit_of_measure: string
  frequency_code: string
  capture_type: string
  is_sensitive: boolean
  evidence_required: boolean
  status: string
}

export interface KpiEntry {
  id: string
  kpi_id: string
  check_name?: string
  check_type?: string
  value?: number
  value_text?: string
  timestamp: string
  status: string
  notes?: string
}

/** Fetch active schools for dropdowns */
export function useSchools() {
  const [schools, setSchools] = useState<School[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    apiFetch('/api/v1/schools?status=active&page_size=200', { signal: controller.signal })
      .then(r => r.json())
      .then(d => setSchools(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  return { schools, loading }
}

/** Fetch departments, optionally filtered by school_id */
export function useDepartments(schoolId?: string | null) {
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!schoolId) {
      setDepartments([])
      setLoading(false)
      return
    }
    const controller = new AbortController()
    apiFetch(`/api/v1/departments?school_id=${schoolId}&status=active&page_size=200`, { signal: controller.signal })
      .then(r => r.json())
      .then(d => setDepartments(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [schoolId])

  return { departments, loading }
}

/** Fetch active KRAs */
export function useKras() {
  const [kras, setKras] = useState<KRA[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    apiFetch('/api/v1/kras?page_size=200', { signal: controller.signal })
      .then(r => r.json())
      .then(d => setKras(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  return { kras, loading }
}

/** Fetch KPIs, optionally filtered by kra_id */
export function useKpis(kraId?: string | null) {
  const [kpis, setKpis] = useState<KPI[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const url = kraId
      ? `/api/v1/kpis?kra_id=${kraId}&page_size=200`
      : '/api/v1/kpis?page_size=200'
    const controller = new AbortController()
    apiFetch(url, { signal: controller.signal })
      .then(r => r.json())
      .then(d => setKpis(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [kraId])

  return { kpis, loading }
}

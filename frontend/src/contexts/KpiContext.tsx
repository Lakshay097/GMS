import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { apiFetch } from '../lib/api'

interface KpiData {
  kpi_id: string
  title: string
  target_value: string
  unit_of_measure: string
  comparator: string
  frequency_code: string
  capture_type: string
  version: number
  suggested_department?: string
}

interface KpiContextType {
  kpis: KpiData[]
  loading: boolean
  error: string | null
  refreshKpis: () => Promise<void>
  getKpiById: (id: string) => KpiData | undefined
}

const KpiContext = createContext<KpiContextType | undefined>(undefined)

export function KpiProvider({ children }: { children: ReactNode }) {
  const [kpis, setKpis] = useState<KpiData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchKpis = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const res = await apiFetch('/api/v1/kpis')
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to fetch KPIs')
      }
      
      const data: KpiData[] = await res.json()
      setKpis(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load KPIs')
    } finally {
      setLoading(false)
    }
  }

  const refreshKpis = async () => {
    await fetchKpis()
  }

  const getKpiById = (id: string) => {
    return kpis.find(kpi => kpi.kpi_id === id)
  }

  useEffect(() => {
    fetchKpis()
  }, [])

  return (
    <KpiContext.Provider value={{ kpis, loading, error, refreshKpis, getKpiById }}>
      {children}
    </KpiContext.Provider>
  )
}

export function useKpiContext() {
  const context = useContext(KpiContext)
  if (context === undefined) {
    throw new Error('useKpiContext must be used within a KpiProvider')
  }
  return context
}
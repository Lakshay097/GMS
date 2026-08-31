import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'
import { useKras } from './useOrgData'
import KpiForm from './KpiForm'
import KraForm from './KraForm'

interface KpiWithKra {
  kpi_id: string
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
  kra_name?: string
}

export default function KpiLibrary() {
  const { kras, loading: krasLoading } = useKras()
  const [kpis, setKpis] = useState<KpiWithKra[]>([])
  const [loading, setLoading] = useState(true)
  const [showKraForm, setShowKraForm] = useState(false)
  const [showKpiForm, setShowKpiForm] = useState(false)
  const [selectedKraId, setSelectedKraId] = useState<string | null>(null)

  const fetchKpis = async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/api/v1/kpis?page_size=500')
      if (res.ok) {
        const data = await res.json()
        setKpis(data.data || [])
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchKpis()
  }, [])

  // Group KPIs by KRA
  const kpisByKra = kras.map(kra => ({
    ...kra,
    kpis: kpis.filter(k => k.kra_id === kra.id),
  }))

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      active: '#22c55e',
      deprecated: '#ef4444',
      pending: '#f59e0b',
    }
    return (
      <span className="badge" style={{ backgroundColor: colors[status] || '#6b7280' }}>
        {status}
      </span>
    )
  }

  if (krasLoading || loading) {
    return <div className="loading">Loading KPI Library...</div>
  }

  return (
    <div className="kpi-library">
      <div className="library-header">
        <h2>KPI Library</h2>
        <div className="library-actions">
          <button onClick={() => setShowKraForm(true)} className="btn-secondary">
            + New KRA
          </button>
          <button onClick={() => setShowKpiForm(true)} className="btn-primary">
            + New KPI
          </button>
        </div>
      </div>

      {showKraForm && (
        <KraForm
          onCreated={() => { setShowKraForm(false); window.location.reload() }}
          onCancel={() => setShowKraForm(false)}
        />
      )}

      {showKpiForm && (
        <KpiForm
          preselectedKraId={selectedKraId || undefined}
          onCreated={() => { setShowKpiForm(false); fetchKpis() }}
          onCancel={() => setShowKpiForm(false)}
        />
      )}

      {kpisByKra.length === 0 && !showKraForm && (
        <div className="empty-state">
          <p>No KRAs yet. Create your first KRA to start defining KPIs.</p>
        </div>
      )}

      {kpisByKra.map(kra => (
        <div key={kra.id} className="kra-group">
          <div className="kra-header">
            <h3>{kra.name}</h3>
            {statusBadge(kra.status)}
            <button
              onClick={() => { setSelectedKraId(kra.id); setShowKpiForm(true) }}
              className="btn-small"
            >
              + Add KPI
            </button>
          </div>
          {kra.description && <p className="kra-description">{kra.description}</p>}

          {kra.kpis.length === 0 ? (
            <div className="empty-kpis">No KPIs in this KRA yet.</div>
          ) : (
            <div className="kpi-list">
              {kra.kpis.map(kpi => (
                <div key={kpi.kpi_id} className="kpi-card">
                  <div className="kpi-card-header">
                    <strong>{kpi.title}</strong>
                    {statusBadge(kpi.status)}
                  </div>
                  <div className="kpi-card-details">
                    <span>Target: {kpi.comparator} {kpi.target_value} {kpi.unit_of_measure}</span>
                    <span>Frequency: {kpi.frequency_code}</span>
                    <span>Type: {kpi.capture_type}</span>
                  </div>
                  <div className="kpi-card-badges">
                    {kpi.is_sensitive && <span className="badge badge-amber">Sensitive</span>}
                    {kpi.evidence_required && <span className="badge badge-blue">Evidence Required</span>}
                  </div>
                  {kpi.description && (
                    <p className="kpi-description">{kpi.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

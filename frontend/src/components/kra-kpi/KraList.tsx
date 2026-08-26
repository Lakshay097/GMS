import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import './KraList.css'

interface Kpi {
  kpi_id: string
  kra_id: string
  version: number
  title: string
  target_value: string
  comparator: string
  unit_of_measure: string
  frequency_code: string
  capture_type: string
  status: string
  is_immutable: boolean
  category_code: string | null
  suggested_department?: string
  is_sensitive?: boolean
  amber_tolerance_band?: string
  working_days?: any
  non_working_day_policy?: string
  evidence_required?: boolean
  formula_type?: string
}

interface Kra {
  id: string
  name: string
  description: string | null
  status: string
}

type LoadStage = 'kras' | 'kpis' | 'idle'

const STAGE_MESSAGES: Record<LoadStage, string> = {
  kras: 'Loading Key Result Areas…',
  kpis: 'Organizing KPIs…',
  idle: '',
}

function LoadingSkeleton({ mode }: { mode: 'kra' | 'department' }) {
  const cardClass = mode === 'department' ? 'skeleton-card skeleton-card--dept' : 'skeleton-card'
  return (
    <div className="loading-skeleton">
      <div className="skeleton-grid">
        {[...Array(6)].map((_, i) => (
          <div key={i} className={cardClass}>
            <div className="skeleton-line skeleton-line--title"></div>
            <div className="skeleton-line skeleton-line--sub"></div>
            <div className="skeleton-line skeleton-line--sub short"></div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function KraList() {
  const [kras, setKras] = useState<Kra[]>([])
  const [kpisByKra, setKpisByKra] = useState<Record<string, Kpi[]>>({})
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [loadStage, setLoadStage] = useState<LoadStage>('kras')
  const [error, setError] = useState<string | null>(null)
  const [includeDeprecated, setIncludeDeprecated] = useState(false)
  const [deprecating, setDeprecating] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState<'kra' | 'department'>('kra')
  const [pendingDeprecateKra, setPendingDeprecateKra] = useState<string | null>(null)
  const [pendingDeprecateKpi, setPendingDeprecateKpi] = useState<{ kpiId: string; kraId: string } | null>(null)
  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  const fetchKras = useCallback(async () => {
    try {
      setLoadStage('kras')
      setError(null)
      const res = await apiFetch(
        `/api/v1/kras?include_deprecated=${includeDeprecated}`
      )
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to fetch KRAs')
      }
      const data: Kra[] = await res.json()
      setKras(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoadStage(prev => (prev === 'kras' && viewMode !== 'department' ? 'idle' : prev))
    }
  }, [includeDeprecated, viewMode])

  useEffect(() => {
    fetchKras()
  }, [fetchKras])

  useEffect(() => {
    if (viewMode !== 'department') return

    const fetchAllKpis = async () => {
      setLoadStage('kpis')
      try {
        const res = await apiFetch('/api/v1/kpis')
        if (res.ok) {
          const allKpis: Kpi[] = await res.json()
          const kpisByKraMap: Record<string, Kpi[]> = {}
          allKpis.forEach(kpi => {
            const kraId = (kpi as any).kra_id || 'unknown'
            if (!kpisByKraMap[kraId]) {
              kpisByKraMap[kraId] = []
            }
            kpisByKraMap[kraId].push(kpi)
          })
          setKpisByKra(kpisByKraMap)
        } else {
          const body = await res.json().catch(() => null)
          console.error('Failed to fetch KPIs:', body?.error?.message || res.statusText)
          setError(body?.error?.message || 'Failed to load KPIs')
        }
      } catch (err) {
        console.error('Failed to fetch KPIs:', err)
        setError(err instanceof Error ? err.message : 'Failed to load KPIs')
      } finally {
        setLoadStage('idle')
      }
    }

    fetchAllKpis()
  }, [viewMode])

  const fetchKpis = async (kraId: string) => {
    if (kpisByKra[kraId]) return
    try {
      const res = await apiFetch(`/api/v1/kpis?kra_id=${kraId}`)
      if (!res.ok) return
      const data: Kpi[] = await res.json()
      setKpisByKra(prev => ({ ...prev, [kraId]: data }))
    } catch {
      // silently ignore — the row just shows empty
    }
  }

  const toggleExpand = (kraId: string) => {
    const next = !expanded[kraId]
    setExpanded(prev => ({ ...prev, [kraId]: next }))
    if (next) fetchKpis(kraId)
  }

  // ── Auto-dismiss banner after 5s ────────────────────────────────────────
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!banner) return
    if (bannerTimer.current) clearTimeout(bannerTimer.current)
    bannerTimer.current = setTimeout(() => setBanner(null), 5000)
    return () => { if (bannerTimer.current) clearTimeout(bannerTimer.current) }
  }, [banner])

  const handleDeprecateKra = async (kraId: string) => {
    setPendingDeprecateKra(null)
    setDeprecating(kraId)
    try {
      const res = await apiFetch(`/api/v1/kras/${kraId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'deprecated' }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to deprecate KRA')
      }
      setBanner({ type: 'success', message: 'KRA deprecated successfully' })
      await fetchKras()
    } catch (err) {
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to deprecate KRA' })
    } finally {
      setDeprecating(null)
    }
  }

  const handleDeprecateKpi = async (kpiId: string, kraId: string) => {
    setPendingDeprecateKpi(null)
    try {
      const res = await apiFetch(`/api/v1/kpis/${kpiId}/deprecate`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to deprecate KPI')
      }
      setBanner({ type: 'success', message: 'KPI deprecated successfully' })
      setKpisByKra(prev => {
        const next = { ...prev }
        delete next[kraId]
        return next
      })
      fetchKpis(kraId)
    } catch (err) {
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to deprecate KPI' })
    }
  }

  const getKpisByDepartment = () => {
    const deptKpis: Record<string, Kpi[]> = {}

    Object.entries(kpisByKra).forEach(([_kraId, kpis]) => {
      kpis.forEach(kpi => {
        const dept = kpi.suggested_department || inferDepartment(kpi.title, kpi.category_code)
        if (!deptKpis[dept]) {
          deptKpis[dept] = []
        }
        deptKpis[dept].push(kpi)
      })
    })

    return deptKpis
  }

  const inferDepartment = (title: string, _category: string | null): string => {
    const titleLower = title.toLowerCase()

    if (titleLower.includes('fire') || titleLower.includes('safety') || titleLower.includes('security')) {
      return 'Security'
    }
    if (titleLower.includes('budget') || titleLower.includes('finance') || titleLower.includes('account') || titleLower.includes('payment')) {
      return 'Accounts'
    }
    if (titleLower.includes('mainten') || titleLower.includes('infrastruct') || titleLower.includes('facility') || titleLower.includes('clean') || titleLower.includes('housekeep')) {
      return 'Facility'
    }
    if (titleLower.includes('it') || titleLower.includes('network') || titleLower.includes('device') || titleLower.includes('system') || titleLower.includes('technology')) {
      return 'IT'
    }
    if (titleLower.includes('store') || titleLower.includes('stock') || titleLower.includes('inventory') || titleLower.includes('asset')) {
      return 'Store'
    }
    if (titleLower.includes('market') || titleLower.includes('admission') || titleLower.includes('parent') || titleLower.includes('communicat')) {
      return 'Marketing'
    }
    if (titleLower.includes('tele') || titleLower.includes('call')) {
      return 'Telecalling'
    }

    return 'General'
  }

  const filteredKras = kras.filter(kra =>
    kra.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (kra.description && kra.description.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const kpisByDepartment = getKpisByDepartment()
  const filteredDepts = Object.entries(kpisByDepartment).filter(([dept, kpis]) =>
    dept.toLowerCase().includes(searchTerm.toLowerCase()) ||
    kpis.some(kpi => kpi.title.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const isLoading = loadStage !== 'idle'

  if (isLoading) return (
    <div className="kra-list page-shell">
      <div className="page-head">
        <div>
          <div className="eyebrow">KRA Library</div>
          <h1>KRAs & KPIs</h1>
          <p className="header-description">{STAGE_MESSAGES[loadStage]}</p>
        </div>
      </div>
      <LoadingSkeleton mode={viewMode} />
    </div>
  )

  if (error) return (
    <div className="kra-list page-shell">
      <div className="error">
        <p>{error}</p>
        <button onClick={fetchKras} className="btn btn-primary">Retry</button>
      </div>
    </div>
  )

  return (
    <div className="kra-list page-shell">
      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">KRA Library</div>
          <h1>KRAs & KPIs</h1>
        </div>
      </div>

      {/* ── Banner (auto-dismiss after 5s) ──────────────────────────── */}
      {banner && (
        <div className={`alert alert-${banner.type}`}>
          <span className="alert-icon">{banner.type === 'error' ? '⚠️' : '✓'}</span>
          <span>{banner.message}</span>
          <button onClick={() => setBanner(null)} className="alert-close">×</button>
        </div>
      )}

      {/* ── Controls ─────────────────────────────────────────────────── */}
      <div className="controls" style={{ flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div className="view-toggle">
          <button
            className={`view-toggle-btn ${viewMode === 'kra' ? 'active' : ''}`}
            onClick={() => setViewMode('kra')}
          >
            By KRA
          </button>
          <button
            className={`view-toggle-btn ${viewMode === 'department' ? 'active' : ''}`}
            onClick={() => setViewMode('department')}
          >
            By Department
          </button>
        </div>

        <div className="search-box">
          <span className="search-icon" aria-hidden="true">🔍</span>
          <input
            type="text"
            placeholder="Search…"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <label className="toggle-label">
          <input
            type="checkbox"
            checked={includeDeprecated}
            onChange={e => setIncludeDeprecated(e.target.checked)}
          />
          <span>Include deprecated</span>
        </label>

        <div style={{ marginLeft: 'auto' }}>
          <Link to="/kra/new" className="btn btn-primary">
            <span className="btn-icon">＋</span> Create KRA
          </Link>
        </div>
      </div>

      {/* ── Content ──────────────────────────────────────────────────── */}
      {viewMode === 'department' ? (
        filteredDepts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <h3>No KPIs found</h3>
            <p>{searchTerm ? 'Try a different search term' : 'No KPIs available yet'}</p>
          </div>
        ) : (
          <div className="department-kpi-grid">
            {filteredDepts.map(([department, kpis]) => (
              <div key={department} className="department-kpi-card">
                <div className="department-kpi-card__header">
                  <div className="department-info">
                    <h3>{department}</h3>
                    <span className="kpi-count">{kpis.length} KPI{kpis.length !== 1 ? 's' : ''}</span>
                  </div>
                  <span className="department-inferred-note">
                    Grouped by KPI category — may be approximate
                  </span>
                </div>
                <div className="department-kpi-card__body">
                  <div className="kpi-list-compact">
                    {kpis.map(kpi => (
                      <div key={`${kpi.kpi_id}-${kpi.version}`} className="kpi-item-compact">
                        <div className="kpi-item-compact__main">
                          <Link to={`/kpi/${kpi.kpi_id}/edit`} className="kpi-title">
                            {kpi.title}
                          </Link>
                          {kpi.is_immutable && (
                            <span className="immutable-badge" title="Immutable — cannot be edited">
                              <span className="immutable-badge__icon">🔒</span>
                              <span>Immutable</span>
                            </span>
                          )}
                        </div>
                        <div className="kpi-item-compact__meta">
                          <span className="kpi-meta">{kpi.target_value} {kpi.unit_of_measure}</span>
                          <span className="kpi-meta">{kpi.frequency_code}</span>
                          <span className={`badge badge-${kpi.status} badge-sm`}>
                            {kpi.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        filteredKras.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <h3>No KRAs found</h3>
            <p>{searchTerm ? 'Try a different search term' : 'Create a KRA to get started with the KPI library'}</p>
            {!searchTerm && (
              <Link to="/kra/new" className="btn btn-primary">
                Create First KRA
              </Link>
            )}
          </div>
        ) : (
          <div className="kra-grid">
            {filteredKras.map(kra => {
              const isExpanded = !!expanded[kra.id]
              const kpis = kpisByKra[kra.id] ?? null
              const kpiCount = kpis?.length ?? 0

              return (
                <div key={kra.id} className={`kra-card ${kra.status === 'deprecated' ? 'kra-card--deprecated' : ''}`}>
                  <div className="kra-card__header">
                    <div className="kra-card__main">
                      <button
                        className="kra-expand-btn"
                        onClick={() => toggleExpand(kra.id)}
                        aria-expanded={isExpanded}
                        aria-label={isExpanded ? 'Collapse KPIs' : 'Expand KPIs'}
                      >
                        <span className={`expand-icon ${isExpanded ? 'expand-icon--open' : ''}`}>
                          {isExpanded ? '▼' : '▶'}
                        </span>
                      </button>

                      <div className="kra-card__info">
                        <h3 className="kra-card__name">{kra.name}</h3>
                        {kra.description && (
                          <p className="kra-card__desc">{kra.description}</p>
                        )}
                      </div>
                    </div>

                    <div className="kra-card__meta">
                      <span className={`badge badge-${kra.status}`}>{kra.status}</span>
                      <span className="kpi-count">{kpiCount} KPI{kpiCount !== 1 ? 's' : ''}</span>
                    </div>

                    <div className="kra-card__actions">
                      <Link
                        to={`/kra/${kra.id}/edit`}
                        className="btn btn-sm btn-ghost"
                        title="Edit KRA"
                      >
                        Edit
                      </Link>
                      <Link
                        to={`/kra/${kra.id}/kpi/new`}
                        className="btn btn-sm btn-secondary"
                        title="Add KPI"
                      >
                        ＋ KPI
                      </Link>
                      {kra.status === 'active' && (
                        pendingDeprecateKra === kra.id ? (
                          <span className="inline-confirm">
                            <span className="inline-confirm__text">Deprecate?</span>
                            <button
                              className="btn btn-sm btn-danger"
                              disabled={deprecating === kra.id}
                              onClick={() => handleDeprecateKra(kra.id)}
                            >
                              {deprecating === kra.id ? '…' : 'Yes'}
                            </button>
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={() => setPendingDeprecateKra(null)}
                              disabled={deprecating === kra.id}
                            >
                              No
                            </button>
                          </span>
                        ) : (
                          <button
                            className="btn btn-sm btn-ghost"
                            style={{ color: 'var(--rose-600)' }}
                            disabled={deprecating === kra.id}
                            onClick={() => setPendingDeprecateKra(kra.id)}
                            title="Deprecate KRA"
                          >
                            Deprecate
                          </button>
                        )
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="kra-card__kpis">
                      {!kpis || kpis.length === 0 ? (
                        <div className="empty-mini">
                          <p>No KPIs defined yet</p>
                          <Link to={`/kra/${kra.id}/kpi/new`} className="btn btn-sm btn-secondary">
                            Add First KPI
                          </Link>
                        </div>
                      ) : (
                        <div className="kpi-list">
                          {kpis.map((kpi) => (
                            <div key={`${kpi.kpi_id}-${kpi.version}`} className="kpi-item">
                              <div className="kpi-item__main">
                                <div className="kpi-item__title">
                                  <Link to={`/kpi/${kpi.kpi_id}/edit`}>
                                    {kpi.title}
                                  </Link>
                                  {kpi.is_immutable && (
                                    <span className="immutable-badge" title="Immutable — cannot be edited">
                                      <span className="immutable-badge__icon">🔒</span>
                                      <span>Immutable</span>
                                    </span>
                                  )}
                                </div>
                                <div className="kpi-item__meta">
                                  <span className="kpi-meta">
                                    Target: {kpi.target_value} {kpi.unit_of_measure}
                                  </span>
                                  <span className="kpi-meta">
                                    Freq: {kpi.frequency_code}
                                  </span>
                                  <span className={`badge badge-${kpi.status} badge-sm`}>
                                    {kpi.status}
                                  </span>
                                </div>
                              </div>
                              <div className="kpi-item__actions">
                                {!kpi.is_immutable && (
                                  <Link
                                    to={`/kpi/${kpi.kpi_id}/edit`}
                                    className="btn btn-sm btn-ghost"
                                  >
                                    Edit
                                  </Link>
                                )}
                                {kpi.status === 'active' && (
                                  pendingDeprecateKpi?.kpiId === kpi.kpi_id ? (
                                    <span className="inline-confirm inline-confirm--sm">
                                      <span className="inline-confirm__text">Deprecate?</span>
                                      <button
                                        className="btn btn-sm btn-danger"
                                        onClick={() => handleDeprecateKpi(kpi.kpi_id, kra.id)}
                                      >
                                        Yes
                                      </button>
                                      <button
                                        className="btn btn-sm btn-ghost"
                                        onClick={() => setPendingDeprecateKpi(null)}
                                      >
                                        No
                                      </button>
                                    </span>
                                  ) : (
                                    <button
                                      className="btn btn-sm btn-ghost"
                                      style={{ color: 'var(--rose-600)' }}
                                      onClick={() => setPendingDeprecateKpi({ kpiId: kpi.kpi_id, kraId: kra.id })}
                                    >
                                      Deprecate
                                    </button>
                                  )
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )
      )}
    </div>
  )
}

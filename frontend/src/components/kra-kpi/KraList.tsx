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

// ─── Modal Form Components ──────────────────────────────────────────────────

function ModalKraForm({
  kraId,
  onSuccess,
  onCancel,
}: {
  kraId?: string
  onSuccess: () => void
  onCancel: () => void
}) {
  const isEdit = !!kraId
  const [form, setForm] = useState({ name: '', description: '' })
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEdit)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isEdit) return
    const load = async () => {
      try {
        const res = await apiFetch('/api/v1/kras?include_deprecated=true')
        if (!res.ok) throw new Error('Failed to load KRA')
        const kras: { id: string; name: string; description: string | null }[] = await res.json()
        const kra = kras.find(k => k.id === kraId)
        if (!kra) throw new Error('KRA not found')
        setForm({ name: kra.name, description: kra.description ?? '' })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load KRA')
      } finally {
        setFetching(false)
      }
    }
    load()
  }, [kraId, isEdit])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const payload = { name: form.name.trim(), description: form.description.trim() || null }
      const res = isEdit
        ? await apiFetch(`/api/v1/kras/${kraId}`, { method: 'PATCH', body: JSON.stringify(payload) })
        : await apiFetch('/api/v1/kras', { method: 'POST', body: JSON.stringify(payload) })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Save failed')
      }
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div className="loading-state">Loading…</div>

  return (
    <form onSubmit={handleSubmit} className="modal-form">
      {error && <div className="error">{error}</div>}
      <div className="form-group">
        <label htmlFor="modal-kra-name">KRA Name *</label>
        <input
          id="modal-kra-name"
          type="text"
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          required
          minLength={1}
          maxLength={255}
          placeholder="e.g. Academic Performance"
          className="form-input"
          autoFocus
        />
      </div>
      <div className="form-group">
        <label htmlFor="modal-kra-desc">Description</label>
        <textarea
          id="modal-kra-desc"
          value={form.description}
          onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          rows={3}
          maxLength={1000}
          placeholder="Optional description"
          className="form-input"
        />
      </div>
      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Saving…' : isEdit ? 'Update KRA' : 'Create KRA'}
        </button>
      </div>
    </form>
  )
}


function ModalKpiForm({
  kraId,
  kpiId,
  onSuccess,
  onCancel,
}: {
  kraId: string
  kpiId?: string
  onSuccess: () => void
  onCancel: () => void
}) {
  const isEdit = !!kpiId
  const COMPARATORS = ['>=', '<=', '=', '>', '<']
  const FREQUENCIES = ['daily', 'weekly', 'monthly', 'quarterly', 'half_yearly', 'annual', 'event']
  const CAPTURE_TYPES = ['value_reading', 'check', 'event_time', 'value_and_event_time']

  const [form, setForm] = useState({
    kra_id: kraId,
    title: '',
    target_value: '',
    comparator: '>=',
    unit_of_measure: '',
    frequency_code: 'monthly',
    capture_type: 'value_reading',
    category_code: '',
    is_sensitive: false,
    amber_tolerance_band: '',
  })
  const [kras, setKras] = useState<{ id: string; name: string; status: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [isImmutable, setIsImmutable] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const kraRes = await apiFetch('/api/v1/kras?include_deprecated=false')
        if (kraRes.ok) {
          const data: { id: string; name: string; status: string }[] = await kraRes.json()
          setKras(data)
        }
        if (isEdit && kpiId) {
          const kpiRes = await apiFetch(`/api/v1/kpis/${kpiId}`)
          if (!kpiRes.ok) throw new Error('Failed to load KPI')
          const kpi = await kpiRes.json()
          setIsImmutable(kpi.is_immutable)
          setForm({
            kra_id: kpi.kra_id,
            title: kpi.title,
            target_value: String(kpi.target_value),
            comparator: kpi.comparator,
            unit_of_measure: kpi.unit_of_measure,
            frequency_code: kpi.frequency_code,
            capture_type: kpi.capture_type,
            category_code: kpi.category_code ?? '',
            is_sensitive: kpi.is_sensitive,
            amber_tolerance_band: kpi.amber_tolerance_band != null ? String(kpi.amber_tolerance_band) : '',
          })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setFetching(false)
      }
    }
    load()
  }, [isEdit, kpiId])

  const set = (field: string, value: string | boolean) =>
    setForm(f => ({ ...f, [field]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const payload: Record<string, unknown> = {
        title: form.title.trim(),
        target_value: parseFloat(form.target_value),
        comparator: form.comparator,
        unit_of_measure: form.unit_of_measure.trim(),
        frequency_code: form.frequency_code,
        capture_type: form.capture_type,
        is_sensitive: form.is_sensitive,
        ...(form.category_code.trim() && { category_code: form.category_code.trim() }),
        ...(form.amber_tolerance_band && { amber_tolerance_band: parseFloat(form.amber_tolerance_band) }),
      }
      let res: Response
      if (isEdit) {
        res = await apiFetch(`/api/v1/kpis/${kpiId}`, { method: 'PATCH', body: JSON.stringify(payload) })
      } else {
        res = await apiFetch('/api/v1/kpis', { method: 'POST', body: JSON.stringify({ ...payload, kra_id: form.kra_id }) })
      }
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Save failed')
      }
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div className="loading-state">Loading…</div>

  return (
    <form onSubmit={handleSubmit} className="modal-form">
      {isImmutable && (
        <div className="info-banner">🔒 This KPI is immutable — only non-structural fields can be changed.</div>
      )}
      {error && <div className="error">{error}</div>}

      {!isEdit && (
        <div className="form-group">
          <label>KRA *</label>
          <select value={form.kra_id} onChange={e => set('kra_id', e.target.value)} required className="form-input">
            <option value="">— select a KRA —</option>
            {kras.map((k, i) => (
              <option key={i} value={k.id}>{k.name}</option>
            ))}
          </select>
        </div>
      )}

      <div className="form-group">
        <label>KPI Title *</label>
        <input type="text" value={form.title} onChange={e => set('title', e.target.value)} required minLength={1} maxLength={255} placeholder="e.g. Attendance Rate" className="form-input" disabled={isImmutable} autoFocus />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Target Value *</label>
          <input type="number" step="any" value={form.target_value} onChange={e => set('target_value', e.target.value)} required placeholder="e.g. 95" className="form-input" disabled={isImmutable} />
        </div>
        <div className="form-group">
          <label>Comparator *</label>
          <select value={form.comparator} onChange={e => set('comparator', e.target.value)} className="form-input" disabled={isImmutable}>
            {COMPARATORS.map((c, i) => <option key={i} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Unit *</label>
          <input type="text" value={form.unit_of_measure} onChange={e => set('unit_of_measure', e.target.value)} required maxLength={50} placeholder="e.g. %, count" className="form-input" disabled={isImmutable} />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Frequency *</label>
          <select value={form.frequency_code} onChange={e => set('frequency_code', e.target.value)} className="form-input" disabled={isImmutable}>
            {FREQUENCIES.map((f, i) => <option key={i} value={f}>{f}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Capture Type *</label>
          <select value={form.capture_type} onChange={e => set('capture_type', e.target.value)} className="form-input" disabled={isImmutable}>
            {CAPTURE_TYPES.map((ct, i) => <option key={i} value={ct}>{ct}</option>)}
          </select>
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Category</label>
          <input type="text" value={form.category_code} onChange={e => set('category_code', e.target.value)} maxLength={50} placeholder="e.g. ACADEMIC" className="form-input" disabled={isImmutable} />
        </div>
        <div className="form-group">
          <label>Amber Tolerance</label>
          <input type="number" step="any" min="0" value={form.amber_tolerance_band} onChange={e => set('amber_tolerance_band', e.target.value)} placeholder="e.g. 5" className="form-input" disabled={isImmutable} />
        </div>
      </div>

      <div className="form-group form-group--inline">
        <label className="checkbox-label">
          <input type="checkbox" checked={form.is_sensitive} onChange={e => set('is_sensitive', e.target.checked)} disabled={isImmutable} />
          <span>Sensitive Data</span>
        </label>
      </div>

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Saving…' : isEdit ? 'Update KPI' : 'Create KPI'}
        </button>
      </div>
    </form>
  )
}


export default function KraList() {
  const [kras, setKras] = useState<Kra[]>([])
  const [kpisByKra, setKpisByKra] = useState<Record<string, Kpi[]>>({})
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const expandedRef = useRef<HTMLDivElement>(null)
  const [loadStage, setLoadStage] = useState<LoadStage>('kras')
  const [error, setError] = useState<string | null>(null)
  const [includeDeprecated, setIncludeDeprecated] = useState(false)
  const [deprecating, setDeprecating] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState<'kra' | 'department'>('kra')
  const [pendingDeprecateKra, setPendingDeprecateKra] = useState<string | null>(null)
  const [pendingDeprecateKpi, setPendingDeprecateKpi] = useState<{ kpiId: string; kraId: string } | null>(null)
  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)
  // Modal state for forms
  const [modalOpen, setModalOpen] = useState<false | 'newKra' | 'editKra' | 'newKpi'>(false)
  const [modalKraId, setModalKraId] = useState<string | null>(null)
  const [modalKpiId, setModalKpiId] = useState<string | null>(null)
  const [modalKraName, setModalKraName] = useState<string>('')

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
      setLoadStage(prev => (prev === 'kras' ? 'idle' : prev))
    }
  }, [includeDeprecated, viewMode])

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        setLoadStage('kras')
        setError(null)
        // Fetch KRAs and KPIs in parallel for fast page load
        const [kraRes, kpiRes] = await Promise.all([
          apiFetch(`/api/v1/kras?include_deprecated=${includeDeprecated}`, { signal: controller.signal }),
          apiFetch('/api/v1/kpis', { signal: controller.signal }),
        ])
        // KRAs
        if (!kraRes.ok) {
          const msg = kraRes.status === 401
            ? 'Session expired. Please sign in again.'
            : kraRes.status === 403
              ? 'You do not have permission to view KRAs.'
              : `Failed to load KRAs (HTTP ${kraRes.status})`
          throw new Error(msg)
        }
        const data: Kra[] = await kraRes.json()
        setKras(data)
        // KPIs
        if (kpiRes.ok) {
          const allKpis: Kpi[] = await kpiRes.json()
          const kpisByKraMap: Record<string, Kpi[]> = {}
          allKpis.forEach(kpi => {
            const kraId = (kpi as any).kra_id || 'unknown'
            if (!kpisByKraMap[kraId]) kpisByKraMap[kraId] = []
            kpisByKraMap[kraId].push(kpi)
          })
          setKpisByKra(prev => ({ ...prev, ...kpisByKraMap }))
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoadStage('idle')
      }
    }
    load()
    return () => controller.abort()
  }, [includeDeprecated, viewMode])

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
    const next = expandedId === kraId ? null : kraId
    setExpandedId(next)
    if (next) fetchKpis(next)
  }

  // ESC key closes expanded panel
  useEffect(() => {
    if (!expandedId) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpandedId(null)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [expandedId])

  // Click outside closes expanded panel
  useEffect(() => {
    if (!expandedId) return
    const handleClick = (e: MouseEvent) => {
      if (expandedRef.current && !expandedRef.current.contains(e.target as Node)) {
        setExpandedId(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [expandedId])

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

  const closeModal = () => {
    setModalOpen(false)
    setModalKraId(null)
    setModalKpiId(null)
    setModalKraName('')
  }

  const handleModalSuccess = () => {
    closeModal()
    fetchKras()
  }

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
          <button className="btn btn-primary" onClick={() => setModalOpen('newKra')}>
            <span className="btn-icon">＋</span> Create KRA
          </button>
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
                          <button className="kpi-title kpi-link-btn" onClick={() => { setModalKraId(kpi.kra_id || 'unknown'); setModalKpiId(kpi.kpi_id); setModalOpen('newKpi') }}>
                            {kpi.title}
                          </button>
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
            <h3>{searchTerm ? 'No matches found' : 'No KRAs yet'}</h3>
            <p>{searchTerm ? 'Try a different search term, or clear the search to see all KRAs.' : 'KRAs (Key Result Areas) define what your school measures. Create your first KRA to start tracking performance.'}</p>
            {!searchTerm && (
              <button className="btn btn-primary" onClick={() => setModalOpen('newKra')}>
                ＋ Create First KRA
              </button>
            )}
          </div>
        ) : (
          <div className="kra-grid">
            {filteredKras.map(kra => {
              const isExpanded = expandedId === kra.id
              const kpis = kpisByKra[kra.id] ?? null
              const kpiCount = kpis?.length

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
                      <span className={`badge badge-${kra.status}`}>{kra.status}</span>                        <span className="kpi-count">{kpiCount != null ? kpiCount + " KPI" + (kpiCount !== 1 ? "s" : "") : "0 KPIs"}</span>
                    </div>

                    <div className="kra-card__actions">
                      <button
                        className="btn btn-sm btn-ghost"
                        title="Edit KRA"
                        onClick={() => { setModalKraId(kra.id); setModalKraName(kra.name); setModalOpen('editKra') }}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-sm btn-secondary"
                        title="Add KPI"
                        onClick={() => { setModalKraId(kra.id); setModalKraName(kra.name); setModalOpen('newKpi') }}
                      >
                        ＋ KPI
                      </button>
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
                    <div className="kra-card__kpis" ref={expandedRef}>
                      {!kpis || kpis.length === 0 ? (
                        <div className="empty-mini">
                          <p>No KPIs defined yet</p>
                          <button className="btn btn-sm btn-secondary" onClick={() => { setModalKraId(kra.id); setModalKraName(kra.name); setModalOpen('newKpi') }}>
                            Add First KPI
                          </button>
                        </div>
                      ) : (
                        <div className="kpi-list">
                          {kpis.map((kpi) => (
                            <div key={`${kpi.kpi_id}-${kpi.version}`} className="kpi-item">
                              <div className="kpi-item__main">
                                <div className="kpi-item__title">
                                  <button className="kpi-link-btn" onClick={() => { setModalKraId(kra.id); setModalKpiId(kpi.kpi_id); setModalOpen('newKpi') }}>
                                    {kpi.title}
                                  </button>
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

      {/* ── Modal overlay ──────────────────────────────────────────────── */}
      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-card__header">
              <h2>
                {modalOpen === 'newKra' && 'Create KRA'}
                {modalOpen === 'editKra' && 'Edit KRA'}
                {modalOpen === 'newKpi' && (modalKpiId ? 'Edit KPI' : 'Add KPI to ' + modalKraName)}
              </h2>
              <button className="modal-card__close" onClick={closeModal} aria-label="Close">✕</button>
            </div>
            <div className="modal-card__body">
              {modalOpen === 'newKra' && (
                <ModalKraForm onSuccess={handleModalSuccess} onCancel={closeModal} />
              )}
              {modalOpen === 'editKra' && modalKraId && (
                <ModalKraForm kraId={modalKraId} onSuccess={handleModalSuccess} onCancel={closeModal} />
              )}
              {modalOpen === 'newKpi' && (
                <ModalKpiForm
                  kraId={modalKraId || ''}
                  kpiId={modalKpiId || undefined}
                  onSuccess={handleModalSuccess}
                  onCancel={closeModal}
                />
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

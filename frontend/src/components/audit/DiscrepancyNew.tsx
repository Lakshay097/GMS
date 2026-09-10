import { useState, useEffect, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { apiFetch } from '../../lib/api'
import { useAuthContext } from '../../contexts/AuthContext'
import { useSchools } from '../org-management/useOrgData'
import './DiscrepancyDetail.css'
import './DiscrepancyNew.css'

/** One observation filling a KPI × date cell (absent when blank). */
interface KpiEntry {
  observation_id: string
  status?: string | null
  value_numeric?: string | number | null
  value_text?: string | null
  check_result?: string | null
  reason?: string | null
  submitted_at?: string | null
}

/** One KPI's state across the requested dates — blank dates simply have no key. */
interface KpiRecord {
  kpi_id: string
  kpi_title: string
  kpi_version: number
  kra_id?: string | null
  kra_name?: string | null
  department_id?: string | null
  department_name?: string | null
  target_value?: string | null
  unit_of_measure?: string | null
  comparator?: string | null
  frequency_code?: string | null
  entries: Record<string, KpiEntry | null>
}

interface Department {
  id: string
  name: string
}

interface Category {
  id: string
  name: string
  status: string
}

interface SelectedPick {
  kpiId: string
  kpiTitle: string
  date: string
  entry: KpiEntry
  unit?: string | null
  target?: string | null
  kraName?: string | null
  deptName?: string | null
}

const MAX_RANGE_DAYS = 62

const todayIso = () => new Date().toISOString().slice(0, 10)

/** True only for complete, real calendar dates (blocks partial date-input states). */
const isCompleteDate = (v: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(new Date(v + 'T00:00:00Z').getTime())

/** Inclusive list of ISO dates between two ISO date strings. */
const dateSpan = (from: string, to: string): string[] => {
  const out: string[] = []
  const start = new Date(from + 'T00:00:00Z')
  const end = new Date(to + 'T00:00:00Z')
  for (let d = start; d <= end; d = new Date(d.getTime() + 86400000)) {
    out.push(d.toISOString().slice(0, 10))
  }
  return out
}

const shortDate = (iso: string) =>
  new Date(iso + 'T00:00:00Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })

export default function DiscrepancyNew() {
  const navigate = useNavigate()
  const { user, schoolId, departmentId } = useAuthContext()

  // ── Matrix filters (dates drive the server fetch; the rest narrow it) ────
  const [recDateFrom, setRecDateFrom] = useState(todayIso())
  const [recDateTo, setRecDateTo] = useState(todayIso())
  const [recKraId, setRecKraId] = useState('')
  const [recDeptId, setRecDeptId] = useState('')
  const [recKpiId, setRecKpiId] = useState('')
  const [recQuery, setRecQuery] = useState('')

  const [records, setRecords] = useState<KpiRecord[]>([])
  const [recordsLoading, setRecordsLoading] = useState(true)
  const [recordsError, setRecordsError] = useState<string | null>(null)

  const [departments, setDepartments] = useState<Department[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState('')
  const [description, setDescription] = useState('')

  const [selected, setSelected] = useState<SelectedPick | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [existingDiscrepancyObsIds, setExistingDiscrepancyObsIds] = useState<Set<string>>(new Set())

  const { schools } = useSchools()

  // ── Departments available to the requester (scope handled by the API) ────
  useEffect(() => {
    const controller = new AbortController()
    const url = schoolId
      ? `/api/v1/departments?school_id=${schoolId}&status=active&page_size=200`
      : '/api/v1/departments?page_size=200'
    apiFetch(url, { signal: controller.signal })
      .then(r => (r.ok ? r.json() : { data: [] }))
      .then(d => setDepartments(d.data || []))
      .catch(() => {})
    return () => controller.abort()
  }, [schoolId])

  // ── Categories on mount ───────────────────────────────────────────────────
  useEffect(() => {
    apiFetch('/api/v1/settings/master-data/discrepancy-categories')
      .then(r => (r.ok ? r.json() : []))
      .then((data: Category[]) => setCategories(data.filter(c => c.status === 'active')))
      .catch(() => {})
  }, [])

  // ── Observations that already have a discrepancy (block re-raise) ─────────
  useEffect(() => {
    const controller = new AbortController()
    apiFetch('/api/v1/audit-discrepancy/discrepancies?page_size=100', { signal: controller.signal })
      .then(res => (res.ok ? res.json() : []))
      .then(data => {
        const list: Array<{ observation_id?: string }> = Array.isArray(data) ? data : []
        setExistingDiscrepancyObsIds(
          new Set(list.map(d => d.observation_id).filter((id): id is string => typeof id === 'string'))
        )
      })
      .catch(() => {})
    return () => controller.abort()
  }, [])

  // ── KPI × date matrix from the server (role-scoped, blanks included) ──────
  useEffect(() => {
    if (!recDateFrom || !recDateTo) return
    // Date inputs fire change events per segment — wait for both to be real dates.
    if (!isCompleteDate(recDateFrom) || !isCompleteDate(recDateTo)) return
    if (recDateTo < recDateFrom) {
      setRecordsError("'To' date must be on or after 'From'.")
      setRecords([])
      return
    }
    const spanDays = Math.round((new Date(recDateTo + 'T00:00:00Z').getTime() - new Date(recDateFrom + 'T00:00:00Z').getTime()) / 86400000)
    if (spanDays > MAX_RANGE_DAYS) {
      setRecordsError(`Date range cannot exceed ${MAX_RANGE_DAYS} days.`)
      setRecords([])
      return
    }
    const controller = new AbortController()
    setRecordsLoading(true)
    setRecordsError(null)
    const params = new URLSearchParams({ date_from: recDateFrom, date_to: recDateTo })
    apiFetch(`/api/v1/observations/kpi-records?${params.toString()}`, { signal: controller.signal })
      .then(async res => {
        if (!res.ok) {
          const body = await res.json().catch(() => null)
          const detail = body?.detail
          const msg =
            typeof detail === 'string'
              ? detail
              : Array.isArray(detail)
                ? detail.map((d: { msg?: string }) => d?.msg || '').join('; ')
                : detail?.message || detail?.error?.message
          throw new Error(msg || `Request failed (${res.status})`)
        }
        return res.json()
      })
      .then((data: KpiRecord[]) => setRecords(Array.isArray(data) ? data : []))
      .catch((err: unknown) => {
        if ((err as Error).name !== 'AbortError') setRecordsError(err instanceof Error ? err.message : 'Failed to load KPI records.')
      })
      .finally(() => setRecordsLoading(false))
    return () => controller.abort()
  }, [recDateFrom, recDateTo])

  const dates = useMemo(
    () => (recDateFrom && recDateTo && recDateTo >= recDateFrom ? dateSpan(recDateFrom, recDateTo) : []),
    [recDateFrom, recDateTo]
  )

  // ── Client-side narrowing over the already role-scoped matrix ─────────────
  // (The server authorizes; these only hide in-scope rows, so no filter can
  //  expose data the requester isn't entitled to.)
  const kraOptions = useMemo(() => {
    const map = new Map<string, string>()
    records.forEach(r => { if (r.kra_id) map.set(r.kra_id, r.kra_name || r.kra_id) })
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [records])

  const kpiOptions = useMemo(() => {
    const seen = new Map<string, string>()
    records.forEach(r => {
      if (recKraId && r.kra_id !== recKraId) return
      seen.set(r.kpi_id, r.kpi_title)
    })
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [records, recKraId])

  const visibleRecords = useMemo(() => {
    const lower = recQuery.trim().toLowerCase()
    return records.filter(r => {
      if (recKraId && r.kra_id !== recKraId) return false
      if (recDeptId && r.department_id !== recDeptId) return false
      if (recKpiId && r.kpi_id !== recKpiId) return false
      if (lower && !r.kpi_title.toLowerCase().includes(lower)) return false
      return true
    })
  }, [records, recKraId, recDeptId, recKpiId, recQuery])

  const clearFilters = () => {
    setRecKraId('')
    setRecDeptId('')
    setRecKpiId('')
    setRecQuery('')
  }
  const filtersActive = Boolean(recKraId || recDeptId || recKpiId || recQuery)

  // ── Eligibility per PRS §25.6 + the Observation→Discrepancy 0/1 edge ──────
  const eligibilityError = (entry: KpiEntry): string | null => {
    const s = (entry.status || '').toLowerCase()
    if (s && s !== 'pending' && s !== 'submitted') {
      if (s === 'verified') return 'Already verified'
      if (s === 'rejected') return 'Already rejected'
      if (s === 'draft') return 'Draft — not yet submitted'
      return `Status "${s}" is not auditable`
    }
    if (existingDiscrepancyObsIds.has(entry.observation_id)) return 'Discrepancy already raised'
    return null
  }

  const pickCell = (r: KpiRecord, date: string, entry: KpiEntry | null | undefined) => {
    if (!entry) return
    setSelected({
      kpiId: r.kpi_id,
      kpiTitle: r.kpi_title,
      date,
      entry,
      unit: r.unit_of_measure,
      target: r.target_value,
      kraName: r.kra_name,
      deptName: r.department_name,
    })
    setError(null)
  }

  const schoolName = schools.find(s => s.id === schoolId)?.name
  const deptName = departments.find(d => d.id === departmentId)?.name

  const selectedIneligibility = selected ? eligibilityError(selected.entry) : null

  /** The submitted answer: check_result first (Yes/No KPIs), then numeric,
      then text. Empty string means the entry exists but was left blank. */
  const cellValue = (entry: KpiEntry) => {
    if (entry.check_result) return entry.check_result
    if (entry.value_numeric !== null && entry.value_numeric !== undefined) return String(entry.value_numeric)
    return (entry.value_text || '').trim()
  }

  const statusLabel = (s?: string | null) => {
    switch ((s || '').toLowerCase()) {
      case 'pending': return 'Submitted'
      case 'verified': return 'Verified'
      case 'rejected': return 'Rejected'
      case 'draft': return 'Draft'
      default: return s || ''
    }
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selected) return setError('Please select a KPI entry.')
    if (!categoryId) return setError('Please select a category.')
    if (!schoolId) return setError('No school associated with your account.')
    const ineligibility = eligibilityError(selected.entry)
    if (ineligibility) {
      return setError(`Cannot raise a discrepancy on this observation: ${ineligibility.toLowerCase()}.`)
    }

    setSubmitting(true)
    setError(null)

    try {
      const res = await apiFetch('/api/v1/audit-discrepancy/discrepancies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          observation_id: selected.entry.observation_id,
          category_id: categoryId,
          school_id: schoolId,
          department_id: departmentId || null,
          raised_by_user_id: user?.id || '',   // backend overrides this with the session user
          description: description.trim() || null,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(
          err?.detail?.message || err?.error?.message || err?.detail || 'Failed to raise discrepancy'
        )
      }

      const created = await res.json()
      navigate(`/discrepancies/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to raise discrepancy')
      setSubmitting(false)
    }
  }

  const enteredCount = visibleRecords.reduce(
    (n, r) => n + dates.filter(d => r.entries[d]).length, 0
  )
  const totalCells = visibleRecords.length * dates.length

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="discrepancy-new page-shell">
      {/* Header */}
      <div className="discrepancy-detail__header">
        <Link to="/discrepancies" className="discrepancy-detail__back">
          <ArrowLeft size={14} />
          <span>Discrepancies</span>
        </Link>
        <div className="discrepancy-detail__header-main">
          <div>
            <span className="eyebrow"><span className="eyebrow__dot" />Audit</span>
            <h1>Raise Discrepancy</h1>
          </div>
        </div>
      </div>

      {/* Form card */}
      <div className="discrepancy-detail__card discrepancy-new__card">
        {error && (
          <div className="discrepancy-new__error" role="alert">
            <strong>!</strong> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {/* KPI entry picker */}
          <div className="discrepancy-detail__field discrepancy-new__field">
            <label className="discrepancy-detail__label" htmlFor="rec-date-from">
              KPI entry <span className="discrepancy-new__required">*</span>
            </label>
            <p className="discrepancy-new__picker-hint">
              Every KPI in your access scope is listed for the selected dates — including ones with no entry yet.
              Click an entered value to raise a discrepancy on it.
            </p>

            {/* Filters */}
            <div className="discrepancy-new__obs-filters">
              <label className="discrepancy-new__obs-filter">
                <span>From</span>
                <input
                  id="rec-date-from"
                  type="date"
                  className="input"
                  value={recDateFrom}
                  onChange={e => {
                    setRecDateFrom(e.target.value)
                    if (recDateTo && e.target.value > recDateTo) setRecDateTo(e.target.value)
                  }}
                />
              </label>
              <label className="discrepancy-new__obs-filter">
                <span>To</span>
                <input
                  id="rec-date-to"
                  type="date"
                  className="input"
                  value={recDateTo}
                  min={recDateFrom}
                  onChange={e => setRecDateTo(e.target.value)}
                />
              </label>
              <label className="discrepancy-new__obs-filter">
                <span>KRA</span>
                <select className="input" value={recKraId} onChange={e => { setRecKraId(e.target.value); setRecKpiId('') }}>
                  <option value="">All KRAs</option>
                  {kraOptions.map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
                </select>
              </label>
              <label className="discrepancy-new__obs-filter">
                <span>Department</span>
                <select className="input" value={recDeptId} onChange={e => setRecDeptId(e.target.value)}>
                  <option value="">All departments</option>
                  {departments.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </label>
              <label className="discrepancy-new__obs-filter">
                <span>KPI</span>
                <select className="input" value={recKpiId} onChange={e => setRecKpiId(e.target.value)}>
                  <option value="">All KPIs</option>
                  {kpiOptions.map(([id, title]) => (
                    <option key={id} value={id}>{title}</option>
                  ))}
                </select>
              </label>
            </div>

            <input
              type="text"
              className="input discrepancy-new__obs-input"
              placeholder="Filter by KPI title…"
              value={recQuery}
              onChange={e => setRecQuery(e.target.value)}
              autoComplete="off"
            />

            {(filtersActive || recDateFrom !== todayIso() || recDateTo !== todayIso()) && (
              <div className="discrepancy-new__filter-row-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={clearFilters}>
                  Clear filters
                </button>
              </div>
            )}

            {recordsError && (
              <p className="discrepancy-new__obs-empty" role="alert">{recordsError}</p>
            )}

            {/* Selected entry chip — the exact submission being disputed */}
            {selected && (
              <div className="discrepancy-new__selected-obs">
                <span className="discrepancy-new__selected-obs-title">
                  {selected.kpiTitle} — {shortDate(selected.date)}
                </span>
                <span className="discrepancy-new__selected-obs-meta">
                  Answer: {cellValue(selected.entry) || '(left blank)'}
                  {selected.entry.reason ? ` · Notes: ${selected.entry.reason}` : ''}
                  {selected.unit ? ` · Unit: ${selected.unit}` : ''}
                  {selected.target ? ` · Target: ${selected.target}` : ''}
                  {selected.kraName ? ` · KRA: ${selected.kraName}` : ''}
                  {selected.deptName ? ` · Dept: ${selected.deptName}` : ''}
                  {' · '}{statusLabel(selected.entry.status)}
                </span>
                {selectedIneligibility && (
                  <span className="discrepancy-new__selected-obs-warning" role="alert">
                    {selectedIneligibility}
                  </span>
                )}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm discrepancy-new__clear-btn"
                  onClick={() => setSelected(null)}
                >
                  Change
                </button>
              </div>
            )}

            {/* Matrix */}
            {recordsLoading ? (
              <p className="discrepancy-new__obs-empty">Loading KPI records…</p>
            ) : visibleRecords.length === 0 ? (
              <p className="discrepancy-new__obs-empty">
                {records.length === 0
                  ? 'No KPIs are assigned to your access scope for this period.'
                  : 'No KPIs match the current filters. Clear a filter to widen the view.'}
              </p>
            ) : (
              <div className="discrepancy-new__matrix-wrap">
                <table className="discrepancy-new__matrix">
                  <thead>
                    <tr>
                      <th className="discrepancy-new__matrix-kpi">KPI</th>
                      <th>KRA</th>
                      <th>Department</th>
                      {dates.map(d => (
                        <th key={d} className="discrepancy-new__matrix-date">{shortDate(d)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRecords.map(r => (
                      <tr key={r.kpi_id}>
                        <td className="discrepancy-new__matrix-kpi">
                          <span className="discrepancy-new__matrix-kpi-title">{r.kpi_title}</span>
                          {r.frequency_code && r.frequency_code !== 'daily' && (
                            <span className="discrepancy-new__matrix-freq">{r.frequency_code}</span>
                          )}
                        </td>
                        <td className="discrepancy-new__matrix-dim">{r.kra_name || '—'}</td>
                        <td className="discrepancy-new__matrix-dim">{r.department_name || '—'}</td>
                        {dates.map(d => {
                          const entry = r.entries[d]
                          if (!entry) {
                            return (
                              <td key={d} data-date-label={shortDate(d)} className="discrepancy-new__matrix-cell discrepancy-new__matrix-cell--blank" title="No entry recorded for this date — the KPI was left blank">
                                <span aria-label="Not entered">—</span>
                              </td>
                            )
                          }
                          const ineligibility = eligibilityError(entry)
                          const answer = cellValue(entry)
                          return (
                            <td key={d} data-date-label={shortDate(d)} className="discrepancy-new__matrix-cell">
                              <button
                                type="button"
                                className={`discrepancy-new__cell-btn${ineligibility ? ' discrepancy-new__cell-btn--disabled' : ''}`}
                                disabled={Boolean(ineligibility)}
                                title={ineligibility || 'Raise a discrepancy on this entry'}
                                onClick={() => pickCell(r, d, entry)}
                              >
                                <span className={`discrepancy-new__cell-value${answer === '' ? ' discrepancy-new__cell-value--blank' : ''}`}>
                                  {answer === '' ? '(left blank)' : answer}
                                </span>
                                {entry.reason && (
                                  <span className="discrepancy-new__cell-notes" title={entry.reason}>
                                    {entry.reason.length > 60 ? entry.reason.slice(0, 60) + '…' : entry.reason}
                                  </span>
                                )}
                                <span className={`discrepancy-new__cell-status discrepancy-new__cell-status--${(entry.status || '').toLowerCase()}`}>
                                  {statusLabel(entry.status)}
                                </span>
                                {ineligibility && (
                                  <span className="discrepancy-new__cell-reason">{ineligibility}</span>
                                )}
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {!recordsLoading && visibleRecords.length > 0 && (
              <p className="discrepancy-new__matrix-legend">
                {enteredCount} of {totalCells} entries filled · “—” marks KPIs with no entry for that date · dimmed entries can’t be audited (hover for the reason)
              </p>
            )}
          </div>

          {/* Category */}
          <div className="discrepancy-detail__field discrepancy-new__field">
            <label className="discrepancy-detail__label" htmlFor="category">
              Category <span className="discrepancy-new__required">*</span>
            </label>
            {categories.length === 0 ? (
              <p className="discrepancy-new__no-categories">
                No active categories found.{' '}
                <Link to="/settings" className="discrepancy-detail__link">
                  Add categories in Settings → Master Data.
                </Link>
              </p>
            ) : (
              <select
                id="category"
                className="input"
                value={categoryId}
                onChange={e => setCategoryId(e.target.value)}
                required
              >
                <option value="">Select a category…</option>
                {categories.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>

          {/* Description (optional) */}
          <div className="discrepancy-detail__field discrepancy-new__field">
            <label className="discrepancy-detail__label" htmlFor="description">
              Description <span className="discrepancy-new__optional">(optional)</span>
            </label>
            <textarea
              id="description"
              className="input discrepancy-new__textarea"
              placeholder="Describe the discrepancy…"
              rows={4}
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>

          {/* Context (read-only) */}
          {(schoolId || departmentId) && (
            <div className="discrepancy-new__context">
              {schoolId && (
                <div className="discrepancy-detail__field">
                  <span className="discrepancy-detail__label">School</span>
                  <span className="discrepancy-detail__value">{schoolName || `${schoolId.slice(0, 8)}…`}</span>
                </div>
              )}
              {departmentId && (
                <div className="discrepancy-detail__field">
                  <span className="discrepancy-detail__label">Department</span>
                  <span className="discrepancy-detail__value">{deptName || `${departmentId.slice(0, 8)}…`}</span>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="discrepancy-detail__inline-actions discrepancy-new__actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !selected || !categoryId || selectedIneligibility !== null}
            >
              {submitting ? 'Raising…' : 'Raise Discrepancy'}
            </button>
            <Link to="/discrepancies" className="btn btn-ghost">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

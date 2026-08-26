import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import './ObservationList.css'

/* ── Types ─────────────────────────────────────────────────────────────── */

interface Observation {
  id: string
  kpi_id: string
  checker_id: string
  department_id: string
  school_id: string
  value_numeric?: number
  value_text?: string
  auto_result: string
  rag_status: string
  submitted_at: string
  is_late: boolean
  status: string
  verified_at?: string
  verified_by?: string
  rejected_at?: string
  rejection_reason?: string
  evidence_count: number
  is_locked: boolean
  // Enriched display fields from list endpoint JOINs
  title?: string
  description?: string
  observer_name?: string
  school_name?: string
  department_name?: string
  category_name?: string
  observation_date?: string
}

type SortKey = 'title' | 'rag_status' | 'observation_date' | 'status'
type SortDir = 'asc' | 'desc'

/* ── Helpers ───────────────────────────────────────────────────────────── */

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Display title: prefer enriched title, fall back to value_text, then 'Untitled' */
function displayTitle(obs: Observation): string {
  if (obs.title) return obs.title
  if (obs.value_text) return obs.value_text.slice(0, 60)
  return 'Untitled'
}

/** RAG status display label */
function ragLabel(rag?: string): string {
  if (!rag) return 'N/A'
  const r = rag.toLowerCase()
  if (r === 'green') return 'Green'
  if (r === 'amber') return 'Amber'
  if (r === 'red') return 'Red'
  return 'N/A'
}

/** RAG dot class */
function ragDotClass(rag?: string): string {
  if (!rag) return 'rag-na'
  const r = rag.toLowerCase()
  if (r === 'green') return 'rag-green'
  if (r === 'amber') return 'rag-amber'
  if (r === 'red') return 'rag-red'
  return 'rag-na'
}

/** Status pill class */
function statusPillClass(status: string): string {
  switch (status) {
    case 'draft':
      return 'obs-status--draft'
    case 'pending':
    case 'submitted':
      return 'obs-status--submitted'
    case 'verified':
      return 'obs-status--verified'
    case 'rejected':
      return 'obs-status--rejected'
    default:
      return 'obs-status--draft'
  }
}

/** Status display label */
function statusLabel(status: string): string {
  switch (status) {
    case 'draft':
      return 'Draft'
    case 'pending':
    case 'submitted':
      return 'Submitted'
    case 'verified':
      return 'Verified'
    case 'rejected':
      return 'Rejected'
    default:
      return status
  }
}

const RAG_ORDER: Record<string, number> = { green: 0, amber: 1, red: 2, not_submitted: 3 }
const STATUS_ORDER: Record<string, number> = { draft: 0, pending: 1, submitted: 1, verified: 2, rejected: 3 }

function sortObservations(
  items: Observation[],
  key: SortKey,
  dir: SortDir,
): Observation[] {
  return [...items].sort((a, b) => {
    let cmp = 0
    switch (key) {
      case 'title':
        cmp = displayTitle(a).localeCompare(displayTitle(b))
        break
      case 'rag_status':
        cmp =
          (RAG_ORDER[a.rag_status?.toLowerCase()] ?? 99) -
          (RAG_ORDER[b.rag_status?.toLowerCase()] ?? 99)
        break
      case 'observation_date':
        cmp =
          new Date(a.observation_date || a.submitted_at).getTime() -
          new Date(b.observation_date || b.submitted_at).getTime()
        break
      case 'status':
        cmp =
          (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99)
        break
    }
    return dir === 'asc' ? cmp : -cmp
  })
}

/* ── Component ─────────────────────────────────────────────────────────── */

export default function ObservationList() {
  const [observations, setObservations] = useState<Observation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('observation_date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        setLoading(true)
        const response = await apiFetch('/api/v1/observations', { signal: controller.signal })
        if (!response.ok) throw new Error('Failed to fetch observations')
        const data = await response.json()
        setObservations(Array.isArray(data) ? data : data.data || [])
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [])

  /* ── Derived data ──────────────────────────────────────────────────── */

  const filtered = observations.filter((obs) => {
    const matchesFilter = filter === 'all' || obs.status === filter
    const matchesSearch =
      searchTerm === '' ||
      displayTitle(obs).toLowerCase().includes(searchTerm.toLowerCase()) ||
      (obs.description &&
        obs.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (obs.observer_name &&
        obs.observer_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (obs.school_name &&
        obs.school_name.toLowerCase().includes(searchTerm.toLowerCase()))
    return matchesFilter && matchesSearch
  })

  const sorted = sortObservations(filtered, sortKey, sortDir)

  const stats = {
    total: observations.length,
    draft: observations.filter(
      (o) => o.status === 'draft',
    ).length,
    submitted: observations.filter(
      (o) => o.status === 'pending' || o.status === 'submitted',
    ).length,
    verified: observations.filter((o) => o.status === 'verified').length,
  }

  /* ── Sort helpers ──────────────────────────────────────────────────── */

  const cycleSort = (key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
        return key
      }
      setSortDir(key === 'observation_date' ? 'desc' : 'asc')
      return key
    })
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return <span className="sort-indicator">↕</span>
    return (
      <span className="sort-indicator">
        {sortDir === 'asc' ? '↑' : '↓'}
      </span>
    )
  }

  /* ── Expand ────────────────────────────────────────────────────────── */

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  /* ── Loading / error ─────────────────────────────────────────────── */

  if (loading) return <div className="loading-state">Loading observations…</div>
  if (error) return <div className="error">{error}</div>

  /* ── Render ────────────────────────────────────────────────────────── */

  return (
    <div className="observation-list page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">Observation Capture</div>
          <h1>Observations</h1>
        </div>
        <Link to="/observations/new" className="btn-primary">
          ＋ Create Observation
        </Link>
      </div>

      {/* ── Stats Ribbon ─────────────────────────────────────────────── */}
      <div className="ribbon">
        <div className="ribbon-item">
          <div className="ribbon-num">{stats.total}</div>
          <div className="ribbon-label">Total</div>
        </div>
        <div className="ribbon-item warn">
          <div className="ribbon-num">{stats.draft}</div>
          <div className="ribbon-label">Draft</div>
        </div>
        <div className="ribbon-item">
          <div className="ribbon-num">{stats.submitted}</div>
          <div className="ribbon-label">Submitted</div>
        </div>
        <div className="ribbon-item accent">
          <div className="ribbon-num">{stats.verified}</div>
          <div className="ribbon-label">Verified</div>
        </div>
      </div>

      {/* ── Controls ─────────────────────────────────────────────────── */}
      <div className="controls">
        <div className="tabs">
          <button
            className={filter === 'all' ? 'active' : ''}
            onClick={() => setFilter('all')}
          >
            All <span className="count">{stats.total}</span>
          </button>
          <button
            className={filter === 'draft' ? 'active' : ''}
            onClick={() => setFilter('draft')}
          >
            Draft <span className="count">{stats.draft}</span>
          </button>
          <button
            className={filter === 'pending' || filter === 'submitted' ? 'active' : ''}
            onClick={() => setFilter('pending')}
          >
            Submitted <span className="count">{stats.submitted}</span>
          </button>
          <button
            className={filter === 'verified' ? 'active' : ''}
            onClick={() => setFilter('verified')}
          >
            Verified <span className="count">{stats.verified}</span>
          </button>
        </div>
        <div className="search-mini">
          <span>🔍</span>
          <input
            type="text"
            placeholder="Search observations…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* ── Table ────────────────────────────────────────────────────── */}
      {sorted.length === 0 ? (
        <div className="empty">
          <div className="glyph">📋</div>
          <h3>No observations found</h3>
          <p>
            Nothing matches this filter yet — try another view or create a new
            observation.
          </p>
        </div>
      ) : (
        <>
          {/* Desktop / tablet table */}
          <div className="table-wrap obs-table-wrap">
            <table className="data-table obs-table">
              <thead>
                <tr>
                  <th
                    className="sortable"
                    onClick={() => cycleSort('title')}
                    aria-sort={
                      sortKey === 'title'
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    Title {sortIndicator('title')}
                  </th>
                  <th className="col-dept-school expandable-column">
                    Department · School
                  </th>
                  <th className="col-category expandable-column">Category</th>
                  <th className="col-observer expandable-column">Observer</th>
                  <th
                    className="sortable col-rag"
                    onClick={() => cycleSort('rag_status')}
                    aria-sort={
                      sortKey === 'rag_status'
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    RAG {sortIndicator('rag_status')}
                  </th>
                  <th
                    className="sortable col-status"
                    onClick={() => cycleSort('status')}
                    aria-sort={
                      sortKey === 'status'
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    Status {sortIndicator('status')}
                  </th>
                  <th
                    className="sortable col-date"
                    onClick={() => cycleSort('observation_date')}
                    aria-sort={
                      sortKey === 'observation_date'
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    Date {sortIndicator('observation_date')}
                  </th>
                  <th className="col-expand" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((obs) => {
                  const isExpanded = !!expandedRows[obs.id]

                  return (
                    <React.Fragment key={obs.id}>
                      <tr className={isExpanded ? 'row-expanded' : ''}>
                        {/* Title */}
                        <td className="obs-title-cell">
                          <Link
                            to={`/observations/${obs.id}`}
                            className="obs-title-link"
                          >
                            {displayTitle(obs)}
                          </Link>
                          {/* RAG dot shown on mobile at top level */}
                          <span className="obs-title-mobile-rag">
                            <span className={`rag-dot ${ragDotClass(obs.rag_status)}`} />
                            <span>{ragLabel(obs.rag_status)}</span>
                          </span>
                        </td>

                        {/* Department · School */}
                        <td className="obs-dept-school expandable-column">
                          <span className="obs-dept-name">
                            {obs.department_name || '—'}
                          </span>
                          <span className="obs-school-name">
                            {obs.school_name || obs.school_id}
                          </span>
                        </td>

                        {/* Category */}
                        <td className="obs-category-cell expandable-column">
                          {obs.category_name ? (
                            <span className="obs-category-badge">
                              {obs.category_name}
                            </span>
                          ) : (
                            <span className="obs-category-empty">—</span>
                          )}
                        </td>

                        {/* Observer */}
                        <td className="obs-observer-cell expandable-column">
                          <span className="obs-observer">
                            <span className="obs-avatar-mini">
                              {(obs.observer_name || 'U').charAt(0).toUpperCase()}
                            </span>
                            <span className="obs-observer-name">
                              {obs.observer_name || obs.checker_id.slice(0, 8) + '…'}
                            </span>
                          </span>
                        </td>

                        {/* RAG */}
                        <td className="obs-rag-cell col-rag expandable-column">
                          <span className={`obs-rag-inline ${ragDotClass(obs.rag_status)}`}>
                            <span className="rag-dot" />
                            <span className="rag-label">{ragLabel(obs.rag_status)}</span>
                          </span>
                        </td>

                        {/* Status */}
                        <td className="obs-status-cell col-status expandable-column">
                          <span className={`obs-status-pill ${statusPillClass(obs.status)}`}>
                            {statusLabel(obs.status)}
                          </span>
                        </td>

                        {/* Date */}
                        <td className="obs-date-cell col-date expandable-column">
                          {formatDate(obs.observation_date || obs.submitted_at)}
                        </td>

                        {/* Expand */}
                        <td className="obs-expand-cell col-expand">
                          <button
                            className="expand-toggle-btn"
                            onClick={() => toggleExpand(obs.id)}
                            aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                            aria-expanded={isExpanded}
                          >
                            {isExpanded ? '▼' : '▶'}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded row details */}
                      {isExpanded && (
                        <tr className="expanded-row">
                          <td colSpan={8}>
                            <div className="expanded-content">
                              <div className="expanded-details">
                                {obs.description && (
                                  <div className="detail-group detail-group--full">
                                    <span className="detail-label">Description</span>
                                    <span className="detail-value">
                                      {obs.description}
                                    </span>
                                  </div>
                                )}
                                <div className="detail-group">
                                  <span className="detail-label">Department</span>
                                  <span className="detail-value">
                                    {obs.department_name || obs.department_id}
                                  </span>
                                </div>
                                <div className="detail-group">
                                  <span className="detail-label">School</span>
                                  <span className="detail-value">
                                    {obs.school_name || obs.school_id}
                                  </span>
                                </div>
                                <div className="detail-group">
                                  <span className="detail-label">Observer</span>
                                  <span className="detail-value">
                                    {obs.observer_name || obs.checker_id}
                                  </span>
                                </div>
                                <div className="detail-group">
                                  <span className="detail-label">Submitted</span>
                                  <span className="detail-value">
                                    {formatDateTime(obs.submitted_at)}
                                  </span>
                                </div>
                                {obs.verified_at && (
                                  <div className="detail-group">
                                    <span className="detail-label">Verified</span>
                                    <span className="detail-value">
                                      {formatDateTime(obs.verified_at)}
                                    </span>
                                  </div>
                                )}
                                {obs.rejected_at && (
                                  <div className="detail-group">
                                    <span className="detail-label">Rejected</span>
                                    <span className="detail-value">
                                      {formatDateTime(obs.rejected_at)}
                                      {obs.rejection_reason &&
                                        ` — ${obs.rejection_reason}`}
                                    </span>
                                  </div>
                                )}
                              </div>
                              <div className="expanded-actions">
                                {/* Single "View" action — gap #4 resolved */}
                                <Link
                                  to={`/observations/${obs.id}`}
                                  className="btn btn-sm"
                                >
                                  View
                                </Link>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* ── Mobile stacked cards ──────────────────────────────────── */}
          <div className="obs-mobile-cards">
            {sorted.map((obs) => {
              const isExpanded = !!expandedRows[obs.id]

              return (
                <div key={obs.id} className="obs-mobile-card">
                  <div
                    className="obs-mobile-card__header"
                    onClick={() => toggleExpand(obs.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') toggleExpand(obs.id)
                    }}
                  >
                    <div className="obs-mobile-card__top">
                      <div className="obs-mobile-card__title-row">
                        <span className="obs-mobile-card__title">
                          {displayTitle(obs)}
                        </span>
                        <span
                          className={`obs-status-pill ${statusPillClass(obs.status)}`}
                        >
                          {statusLabel(obs.status)}
                        </span>
                      </div>
                      <div className="obs-mobile-card__rag-row">
                        <span
                          className={`rag-dot ${ragDotClass(obs.rag_status)}`}
                        />
                        <span className="obs-mobile-card__rag-label">
                          {ragLabel(obs.rag_status)}
                        </span>
                        <span className="obs-mobile-card__date">
                          {formatDate(obs.observation_date || obs.submitted_at)}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`obs-mobile-card__expand ${isExpanded ? 'open' : ''}`}
                    >
                      ▶
                    </span>
                  </div>

                  {isExpanded && (
                    <div className="obs-mobile-card__body">
                      {obs.description && (
                        <div className="obs-mobile-card__detail">
                          <span className="detail-label">Description</span>
                          <span className="detail-value">{obs.description}</span>
                        </div>
                      )}
                      <div className="obs-mobile-card__detail">
                        <span className="detail-label">Department</span>
                        <span className="detail-value">
                          {obs.department_name || '—'}
                        </span>
                      </div>
                      <div className="obs-mobile-card__detail">
                        <span className="detail-label">School</span>
                        <span className="detail-value">
                          {obs.school_name || obs.school_id}
                        </span>
                      </div>
                      {obs.category_name && (
                        <div className="obs-mobile-card__detail">
                          <span className="detail-label">Category</span>
                          <span className="detail-value">
                            {obs.category_name}
                          </span>
                        </div>
                      )}
                      <div className="obs-mobile-card__detail">
                        <span className="detail-label">Observer</span>
                        <span className="detail-value">
                          {obs.observer_name || obs.checker_id}
                        </span>
                      </div>
                      <div className="obs-mobile-card__detail">
                        <span className="detail-label">Submitted</span>
                        <span className="detail-value">
                          {formatDateTime(obs.submitted_at)}
                        </span>
                      </div>
                      <div className="obs-mobile-card__actions">
                        <Link
                          to={`/observations/${obs.id}`}
                          className="btn btn-sm"
                        >
                          View
                        </Link>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

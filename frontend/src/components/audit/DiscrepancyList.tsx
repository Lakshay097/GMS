import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Eye,
  ChevronDown,
  ChevronUp,
  Plus,
} from 'lucide-react'
import './DiscrepancyList.css'

/* ── Types ────────────────────────────────────────────────────────────────── */

interface Discrepancy {
  id: string
  observation_id: string
  category_id: string
  school_id: string
  department_id?: string
  raised_by_user_id: string
  investigation_owner_id?: string
  state: string
  investigation_findings?: string
  bound_chain_version_id?: string
  raised_at: string
  under_investigation_at?: string
  resolved_at?: string
  closed_at?: string
  created_at: string
  updated_at: string
  // Enriched display fields from backend
  observation_title?: string
  raised_by_name?: string
  investigation_owner_name?: string
  category_name?: string
  school_name?: string
  department_name?: string
}

type SortKey = 'raised_at' | 'state'
type SortDir = 'asc' | 'desc'

/* ── State config ─────────────────────────────────────────────────────────── */

const STATE_TABS = [
  { key: 'all', label: 'All' },
  { key: 'raised', label: 'Raised' },
  { key: 'under_investigation', label: 'Under Investigation' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'pending_approval', label: 'Pending Approval' },
  { key: 'approved', label: 'Approved' },
  { key: 'closed', label: 'Closed' },
]

const STATE_BADGE_CLASS: Record<string, string> = {
  raised: 'badge--amber',
  under_investigation: 'badge--gold',
  resolved: 'badge--moss',
  pending_approval: 'badge--amber',
  approved: 'badge--moss',
  closed: 'badge--neutral',
}

/* ── Helpers ──────────────────────────────────────────────────────────────── */

function formatState(state: string): string {
  return state.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function getInitials(name?: string): string {
  if (!name) return '?'
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

/* ── Main Component ──────────────────────────────────────────────────────── */

export default function DiscrepancyList() {
  const [discrepancies, setDiscrepancies] = useState<Discrepancy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('raised_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // Name resolution is now handled by backend enrichment — no client-side maps needed

  /* ── Fetch data + resolve names ──────────────────────────────────────── */

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

      // Single fetch — backend now enriches with resolved names
      const discRes = await apiFetch('/api/v1/audit-discrepancy/discrepancies?page_size=100', { signal })

      if (!discRes.ok) throw new Error('Failed to fetch discrepancies')
      const discData = await discRes.json()
      setDiscrepancies(Array.isArray(discData) ? discData : [])
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
        setDiscrepancies([])
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    return () => controller.abort()
  }, [])

  /* ── Derived data ────────────────────────────────────────────────────── */

  const filtered = useMemo(() => {
    let list = discrepancies
    if (filter !== 'all') {
      list = list.filter((d) => d.state === filter)
    }
    return list
  }, [discrepancies, filter])

  const sorted = useMemo(() => {
    const copy = [...filtered]
    copy.sort((a, b) => {
      if (sortKey === 'raised_at') {
        const aVal = a.raised_at ? new Date(a.raised_at).getTime() : 0
        const bVal = b.raised_at ? new Date(b.raised_at).getTime() : 0
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal
      }
      if (sortKey === 'state') {
        const aVal = a.state || ''
        const bVal = b.state || ''
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      return 0
    })
    return copy
  }, [filtered, sortKey, sortDir])

  // Tab counts
  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: discrepancies.length }
    for (const d of discrepancies) {
      counts[d.state] = (counts[d.state] || 0) + 1
    }
    return counts
  }, [discrepancies])

  /* ── Sort handler ────────────────────────────────────────────────────── */

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortKey(key)
        setSortDir('desc')
      }
    },
    [sortKey]
  )

  /* ── Row expand ──────────────────────────────────────────────────────── */

  const toggleExpand = useCallback((id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  /* ── Render ──────────────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="discrepancy-list page-shell">
        <div className="discrepancy-list__loading">Loading discrepancies…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="discrepancy-list page-shell">
        <div className="discrepancy-list__error">{error}</div>
      </div>
    )
  }

  return (
    <div className="discrepancy-list page-shell">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="discrepancy-list__header">
        <div className="discrepancy-list__header-top">
          <span className="eyebrow">
            <span className="eyebrow__dot" />
            Audit
          </span>
          <h1>Discrepancies</h1>
        </div>
        <Link to="/discrepancies/new" className="btn btn-primary">
          <Plus size={16} />
          <span>Raise Discrepancy</span>
        </Link>
      </div>

      {/* ── State Tabs ──────────────────────────────────────────────────── */}
      <div className="discrepancy-list__tabs" role="tablist">
        {STATE_TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={filter === tab.key}
            className={`discrepancy-list__tab ${filter === tab.key ? 'discrepancy-list__tab--active' : ''}`}
            onClick={() => setFilter(tab.key)}
          >
            <span>{tab.label}</span>
            {tabCounts[tab.key] != null && (
              <span className="discrepancy-list__tab-count">
                {tabCounts[tab.key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Empty State ─────────────────────────────────────────────────── */}
      {sorted.length === 0 && (
        <div className="discrepancy-list__empty">
          <p>No discrepancies found</p>
        </div>
      )}

      {/* ── Table ────────────────────────────────────────────────────────── */}
      {sorted.length > 0 && (
        <>
          <div className="discrepancy-list__table-wrap">
            <table className="data-table discrepancy-list__table">
              <thead>
                <tr>
                  <th className="th--mono">ID</th>
                  <th>
                    <button
                      className="discrepancy-list__sort-btn"
                      onClick={() => handleSort('state')}
                    >
                      State
                      {sortKey === 'state' ? (
                        sortDir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
                      ) : (
                        <ArrowUpDown size={12} />
                      )}
                    </button>
                  </th>
                  <th>Observation</th>
                  <th>Raised By</th>
                  <th>Investigation Owner</th>
                  <th>
                    <button
                      className="discrepancy-list__sort-btn"
                      onClick={() => handleSort('raised_at')}
                    >
                      Raised At
                      {sortKey === 'raised_at' ? (
                        sortDir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
                      ) : (
                        <ArrowUpDown size={12} />
                      )}
                    </button>
                  </th>
                  <th className="th--actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((d) => {
                  const raisedByName = d.raised_by_name || d.raised_by_user_id.slice(0, 8)
                  const ownerName = d.investigation_owner_name || d.investigation_owner_id?.slice(0, 8)
                  const obsTitle = d.observation_title || d.observation_id.slice(0, 8)
                  const isExpanded = expandedRows.has(d.id)

                  return (
                    <tr key={d.id} className={isExpanded ? 'row--expanded' : ''}>
                      {/* ID — mono chip */}
                      <td>
                        <Link
                          to={`/discrepancies/${d.id}`}
                          className="discrepancy-list__id-chip"
                          title={d.id}
                        >
                          {d.id.slice(0, 8)}
                        </Link>
                      </td>

                      {/* State badge */}
                      <td>
                        <span className={`badge ${STATE_BADGE_CLASS[d.state] || 'badge--neutral'}`}>
                          {formatState(d.state)}
                        </span>
                      </td>

                      {/* Observation — resolved link */}
                      <td>
                        <Link
                          to={`/observations/${d.observation_id}`}
                          className="discrepancy-list__obs-link"
                          title={obsTitle || d.observation_id}
                        >
                          {obsTitle || d.observation_id.slice(0, 8)}
                        </Link>
                      </td>

                      {/* Raised By — mini-avatar + name */}
                      <td>
                        <div className="discrepancy-list__person">
                          <span className="avatar-mini">
                            {getInitials(raisedByName)}
                          </span>
                          <span className="discrepancy-list__person-name">
                            {raisedByName || d.raised_by_user_id.slice(0, 8)}
                          </span>
                        </div>
                      </td>

                      {/* Investigation Owner — mini-avatar + name or "Not assigned" */}
                      <td>
                        {d.investigation_owner_id ? (
                          <div className="discrepancy-list__person">
                            <span className="avatar-mini">
                              {getInitials(ownerName)}
                            </span>
                            <span className="discrepancy-list__person-name">
                              {ownerName || d.investigation_owner_id.slice(0, 8)}
                            </span>
                          </div>
                        ) : (
                          <span className="discrepancy-list__not-assigned">
                            Not assigned
                          </span>
                        )}
                      </td>

                      {/* Raised At */}
                      <td className="td--date">
                        {d.raised_at
                          ? new Date(d.raised_at).toLocaleDateString()
                          : '–'}
                      </td>

                      {/* Actions */}
                      <td className="td--actions">
                        <Link
                          to={`/discrepancies/${d.id}`}
                          className="icon-btn"
                          title="View discrepancy"
                        >
                          <Eye size={16} />
                        </Link>
                        <button
                          className="icon-btn discrepancy-list__expand-btn"
                          onClick={() => toggleExpand(d.id)}
                          aria-expanded={isExpanded}
                          title={isExpanded ? 'Collapse' : 'Expand'}
                        >
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </td>

                      {/* Expanded row — hidden details on tablet/mobile */}
                      {isExpanded && (
                        <tr className="discrepancy-list__expanded-row">
                          <td colSpan={7}>
                            <div className="discrepancy-list__expanded-details">
                              <div className="discrepancy-list__detail-item">
                                <span className="discrepancy-list__detail-label">Observation</span>
                                <Link
                                  to={`/observations/${d.observation_id}`}
                                  className="discrepancy-list__obs-link"
                                >
                                  {obsTitle || d.observation_id.slice(0, 8)}
                                </Link>
                              </div>
                              <div className="discrepancy-list__detail-item">
                                <span className="discrepancy-list__detail-label">Raised By</span>
                                <div className="discrepancy-list__person">
                                  <span className="avatar-mini">
                                    {getInitials(raisedByName)}
                                  </span>
                                  <span>{raisedByName || '–'}</span>
                                </div>
                              </div>
                              <div className="discrepancy-list__detail-item">
                                <span className="discrepancy-list__detail-label">Investigation Owner</span>
                                {d.investigation_owner_id ? (
                                  <div className="discrepancy-list__person">
                                    <span className="avatar-mini">
                                      {getInitials(ownerName)}
                                    </span>
                                    <span>{ownerName || '–'}</span>
                                  </div>
                                ) : (
                                  <span className="discrepancy-list__not-assigned">
                                    Not assigned
                                  </span>
                                )}
                              </div>
                              <div className="discrepancy-list__detail-item">
                                <span className="discrepancy-list__detail-label">Raised At</span>
                                <span>{d.raised_at ? new Date(d.raised_at).toLocaleDateString() : '–'}</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="discrepancy-list__footer">
            <span className="discrepancy-list__count">
              {sorted.length} discrepancy{sorted.length !== 1 ? 'ies' : ''}
            </span>
          </div>
        </>
      )}

      {/* ── Mobile Stacked Cards (hidden on desktop/tablet) ──────────────── */}
      {sorted.length > 0 && (
        <div className="discrepancy-list__mobile-cards">
          {sorted.map((d) => {
            const raisedByName = d.raised_by_name || d.raised_by_user_id.slice(0, 8)
            const ownerName = d.investigation_owner_name || d.investigation_owner_id?.slice(0, 8)
            const obsTitle = d.observation_title || d.observation_id.slice(0, 8)

            return (
              <div key={d.id} className="discrepancy-list__mobile-card">
                <div className="discrepancy-list__mobile-card-header">
                  <Link
                    to={`/discrepancies/${d.id}`}
                    className="discrepancy-list__id-chip"
                    title={d.id}
                  >
                    {d.id.slice(0, 8)}
                  </Link>
                  <span className={`badge ${STATE_BADGE_CLASS[d.state] || 'badge--neutral'}`}>
                    {formatState(d.state)}
                  </span>
                </div>

                <div className="discrepancy-list__mobile-card-body">
                  <div className="discrepancy-list__mobile-card-row">
                    <span className="discrepancy-list__mobile-card-label">Observation</span>
                    <Link
                      to={`/observations/${d.observation_id}`}
                      className="discrepancy-list__obs-link"
                    >
                      {obsTitle || d.observation_id.slice(0, 8)}
                    </Link>
                  </div>
                  <div className="discrepancy-list__mobile-card-row">
                    <span className="discrepancy-list__mobile-card-label">Raised By</span>
                    <div className="discrepancy-list__person">
                      <span className="avatar-mini">
                        {getInitials(raisedByName)}
                      </span>
                      <span>{raisedByName || '–'}</span>
                    </div>
                  </div>
                  <div className="discrepancy-list__mobile-card-row">
                    <span className="discrepancy-list__mobile-card-label">Owner</span>
                    {d.investigation_owner_id ? (
                      <div className="discrepancy-list__person">
                        <span className="avatar-mini">
                          {getInitials(ownerName)}
                        </span>
                        <span>{ownerName || '–'}</span>
                      </div>
                    ) : (
                      <span className="discrepancy-list__not-assigned">Not assigned</span>
                    )}
                  </div>
                  <div className="discrepancy-list__mobile-card-row">
                    <span className="discrepancy-list__mobile-card-label">Raised</span>
                    <span>{d.raised_at ? new Date(d.raised_at).toLocaleDateString() : '–'}</span>
                  </div>
                </div>

                <div className="discrepancy-list__mobile-card-actions">
                  <Link
                    to={`/discrepancies/${d.id}`}
                    className="btn btn-ghost btn-sm"
                  >
                    <Eye size={14} />
                    <span>View</span>
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

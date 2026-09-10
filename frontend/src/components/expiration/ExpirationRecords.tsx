import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { formatDate } from '../../lib/utils'
import { useAuthContext } from '../../contexts/AuthContext'
import { useDepartments } from '../org-management/useOrgData'
import './ExpirationRecords.css'

/* ── Types ─────────────────────────────────────────────────────────────── */

interface ExpirationRecord {
  id: string
  school_id: string
  department_id: string | null
  entity_type: string
  title: string
  description: string | null
  document_reference: string | null
  entity_link: string | null
  issued_at: string | null
  expires_at: string | null
  renewed_at: string | null
  renew_by_at: string | null
  status: string
  reminder_lead_days: number
  reminder_sent_at: string | null
  is_acknowledged: boolean
  created_at: string | null
  updated_at: string | null
}

interface ExpirationSummary {
  total: number
  expiring_7d: number
  expiring_30d: number
  expired: number
  renewed: number
}

interface ListResponse {
  items: ExpirationRecord[]
  total: number
  page: number
  page_size: number
}

type StatusFilter = 'all' | 'active' | 'expiring_soon' | 'expired' | 'renewed'

const ENTITY_TYPES = [
  'certificate',
  'license',
  'lease',
  'insurance',
  'permit',
  'calibration',
  'training',
  'other',
]

const ENTITY_LABELS: Record<string, string> = {
  certificate: 'Cert',
  license: 'Lic',
  lease: 'Lease',
  insurance: 'Ins',
  permit: 'Permit',
  calibration: 'Cal',
  training: 'Train',
  other: 'Other',
}

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  expiring_soon: 'Expiring soon',
  expired: 'Expired',
  renewed: 'Renewed',
}

/* ── Helpers ───────────────────────────────────────────────────────────── */

function daysUntil(dateStr: string | null): number {
  if (!dateStr) return 0
  const target = new Date(dateStr)
  return Math.ceil((target.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
}

function urgencyClass(record: ExpirationRecord): string {
  if (record.status === 'expired') return 'urgency--critical'
  if (record.status === 'renewed') return 'urgency--renewed'
  const days = daysUntil(record.expires_at)
  if (days <= 7) return 'urgency--critical'
  if (days <= 30) return 'urgency--warning'
  return 'urgency--ok'
}

function urgencyLabel(record: ExpirationRecord): string {
  if (record.status === 'expired') return 'Expired'
  if (record.status === 'renewed') return 'Renewed'
  const days = daysUntil(record.expires_at)
  if (days <= 0) return 'Expired today'
  if (days === 1) return 'Expires tomorrow'
  return `${days} days left`
}

function statusPillClass(status: string): string {
  switch (status) {
    case 'active':
      return 'exp-status--active'
    case 'expiring_soon':
      return 'exp-status--expiring'
    case 'expired':
      return 'exp-status--expired'
    case 'renewed':
      return 'exp-status--renewed'
    default:
      return 'exp-status--active'
  }
}

/* ── Page ──────────────────────────────────────────────────────────────── */

const PAGE_SIZE = 25

export default function ExpirationRecords() {
  const navigate = useNavigate()
  const { schoolId } = useAuthContext()
  const { departments } = useDepartments(schoolId)

  const [summary, setSummary] = useState<ExpirationSummary | null>(null)
  const [items, setItems] = useState<ExpirationRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [entityType, setEntityType] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams()
      if (statusFilter !== 'all') params.set('status', statusFilter)
      if (entityType) params.set('entity_type', entityType)
      if (departmentFilter) params.set('department_id', departmentFilter)
      params.set('page', String(page))
      params.set('page_size', String(PAGE_SIZE))

      const [summaryRes, listRes] = await Promise.all([
        apiFetch('/api/v1/expiration-records/summary'),
        apiFetch(`/api/v1/expiration-records?${params.toString()}`),
      ])

      if (summaryRes.ok) setSummary(await summaryRes.json())

      if (listRes.ok) {
        const data: ListResponse = await listRes.json()
        setItems(Array.isArray(data.items) ? data.items : [])
        setTotal(typeof data.total === 'number' ? data.total : items.length)
      } else {
        setError(`Failed to load expiration records (${listRes.status})`)
        setItems([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load expiration records')
      setItems([])
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, entityType, departmentFilter, page])

  useEffect(() => { load() }, [load])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const handleAcknowledge = async (e: React.MouseEvent, recordId: string) => {
    e.stopPropagation()
    try {
      const res = await apiFetch(`/api/v1/expiration-records/${recordId}/acknowledge`, { method: 'POST' })
      if (res.ok) {
        setItems(prev => prev.map(i => i.id === recordId ? { ...i, is_acknowledged: true } : i))
      }
    } catch { /* surfaced on next load */ }
  }

  const handleRenew = async (e: React.MouseEvent, recordId: string) => {
    e.stopPropagation()
    const newExpires = prompt('Enter new expiry date (YYYY-MM-DD):')
    if (!newExpires) return
    const expiresAt = new Date(newExpires)
    if (isNaN(expiresAt.getTime()) || expiresAt <= new Date()) {
      alert('Please enter a valid future date.')
      return
    }
    try {
      const res = await apiFetch(`/api/v1/expiration-records/${recordId}/renew`, {
        method: 'POST',
        body: JSON.stringify({ new_expires_at: expiresAt.toISOString() }),
      })
      if (res.ok) {
        setItems(prev => prev.filter(i => i.id !== recordId))
        setSummary(prev => prev ? { ...prev, renewed: prev.renewed + 1, expired: Math.max(0, prev.expired - 1) } : prev)
      } else {
        alert('Failed to renew. Please try again.')
      }
    } catch {
      alert('Failed to renew. Please try again.')
    }
  }

  return (
    <div className="expiration-records page-shell">

      {/* ── Page Header ─────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">Expiration Reminders</div>
          <h1>Expiration Records</h1>
        </div>
      </div>

      {/* ── Stats Ribbon ────────────────────────────────────────────── */}
      {summary && (
        <div className="ribbon">
          <div className="ribbon-item">
            <span className="ribbon-num">{summary.total}</span>
            <span className="ribbon-label">Total tracked</span>
          </div>
          <div className="ribbon-item">
            <span className="ribbon-num">{summary.expiring_7d}</span>
            <span className="ribbon-label">Expiring in 7 days</span>
          </div>
          <div className="ribbon-item">
            <span className="ribbon-num">{summary.expiring_30d}</span>
            <span className="ribbon-label">Expiring in 30 days</span>
          </div>
          <div className="ribbon-item">
            <span className="ribbon-num">{summary.expired}</span>
            <span className="ribbon-label">Expired</span>
          </div>
          <div className="ribbon-item">
            <span className="ribbon-num">{summary.renewed}</span>
            <span className="ribbon-label">Renewed</span>
          </div>
        </div>
      )}

      {/* ── Controls ────────────────────────────────────────────────── */}
      <div className="exp-controls">
        <div className="exp-filter-tabs" role="tablist" aria-label="Status filter">
          {(['all', 'active', 'expiring_soon', 'expired', 'renewed'] as StatusFilter[]).map(s => (
            <button
              key={s}
              className={`exp-filter-tab ${statusFilter === s ? 'exp-filter-tab--active' : ''}`}
              onClick={() => { setPage(1); setStatusFilter(s) }}
            >
              {s === 'all' ? 'All' : STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <div className="exp-control-selects">
          <select
            aria-label="Filter by entity type"
            value={entityType}
            onChange={e => { setPage(1); setEntityType(e.target.value) }}
          >
            <option value="">All entity types</option>
            {ENTITY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select
            aria-label="Filter by department"
            value={departmentFilter}
            onChange={e => { setPage(1); setDepartmentFilter(e.target.value) }}
          >
            <option value="">All departments</option>
            {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
      </div>

      {/* ── Content ─────────────────────────────────────────────────── */}
      {loading ? (
        <div className="loading-state">Loading expiration records…</div>
      ) : error ? (
        <div className="error">{error}</div>
      ) : items.length === 0 ? (
        <div className="exp-empty">
          <h3>No expiration records found</h3>
          <p>
            {statusFilter !== 'all' || entityType || departmentFilter
              ? 'No records match the current filters.'
              : 'Records created from KPI Entry or via the API will appear here.'}
          </p>
        </div>
      ) : (
        <>
          {/* Desktop / tablet table */}
          <div className="exp-table-wrap">
            <table className="exp-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Department</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th>Renew by</th>
                  <th>Ack</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map(rec => (
                  <tr
                    key={rec.id}
                    className={`exp-row ${rec.is_acknowledged ? 'exp-row--acknowledged' : ''}`}
                    onClick={() => navigate(`/expiration-records/${rec.id}`)}
                  >
                    <td className="exp-title-cell">
                      <Link
                        to={`/expiration-records/${rec.id}`}
                        className="exp-title-link"
                        onClick={e => e.stopPropagation()}
                      >
                        {rec.title}
                      </Link>
                      {rec.document_reference && (
                        <div className="exp-title-ref">{rec.document_reference}</div>
                      )}
                    </td>
                    <td>
                      <span className="exp-type-badge">{ENTITY_LABELS[rec.entity_type] || rec.entity_type}</span>
                    </td>
                    <td>{rec.department_id ? (departments.find(d => d.id === rec.department_id)?.name || '—') : '—'}</td>
                    <td>
                      <div className="exp-expiry-cell">
                        <span>{formatDate(rec.expires_at)}</span>
                        <span className={`exp-item__urgency ${urgencyClass(rec)}`}>{urgencyLabel(rec)}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`exp-status-pill ${statusPillClass(rec.status)}`}>
                        {STATUS_LABELS[rec.status] || rec.status}
                      </span>
                    </td>
                    <td>{formatDate(rec.renew_by_at)}</td>
                    <td>{rec.is_acknowledged ? '✓' : '—'}</td>
                    <td className="exp-actions-cell">
                      {(rec.status === 'expired' || rec.status === 'expiring_soon') && (
                        <button
                          className="exp-action-btn exp-action-btn--renew"
                          onClick={(e) => handleRenew(e, rec.id)}
                          title="Mark as renewed"
                        >
                          Renew
                        </button>
                      )}
                      {!rec.is_acknowledged && (
                        <button
                          className="exp-action-btn exp-action-btn--ack"
                          onClick={(e) => handleAcknowledge(e, rec.id)}
                          title="Acknowledge (dismiss reminder)"
                        >
                          Ack
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked cards */}
          <div className="exp-cards">
            {items.map(rec => (
              <div
                key={rec.id}
                className={`exp-card ${rec.is_acknowledged ? 'exp-card--acknowledged' : ''}`}
                onClick={() => navigate(`/expiration-records/${rec.id}`)}
                role="button"
                tabIndex={0}
              >
                <div className="exp-card__top">
                  <span className="exp-card__title">{rec.title}</span>
                  <span className={`exp-status-pill ${statusPillClass(rec.status)}`}>
                    {STATUS_LABELS[rec.status] || rec.status}
                  </span>
                </div>
                <div className="exp-card__meta">
                  <span>{ENTITY_LABELS[rec.entity_type] || rec.entity_type}</span>
                  <span>Expires: {formatDate(rec.expires_at)}</span>
                  <span className={`exp-item__urgency ${urgencyClass(rec)}`}>{urgencyLabel(rec)}</span>
                </div>
                <div className="exp-card__actions">
                  {(rec.status === 'expired' || rec.status === 'expiring_soon') && (
                    <button className="exp-action-btn exp-action-btn--renew" onClick={(e) => handleRenew(e, rec.id)}>
                      Renew
                    </button>
                  )}
                  {!rec.is_acknowledged && (
                    <button className="exp-action-btn exp-action-btn--ack" onClick={(e) => handleAcknowledge(e, rec.id)}>
                      Ack
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="exp-pagination">
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span>Page {page} of {totalPages} ({total} records)</span>
              <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

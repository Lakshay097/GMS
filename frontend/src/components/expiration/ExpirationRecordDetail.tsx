import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/utils'
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
  metadata_json: Record<string, unknown> | null
  created_at: string | null
  updated_at: string | null
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

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  expiring_soon: 'Expiring soon',
  expired: 'Expired',
  renewed: 'Renewed',
}

/* ── Page ──────────────────────────────────────────────────────────────── */

export default function ExpirationRecordDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [record, setRecord] = useState<ExpirationRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!id) return
    try {
      setLoading(true)
      setError(null)
      const res = await apiFetch(`/api/v1/expiration-records/${id}`)
      if (res.ok) {
        setRecord(await res.json())
      } else if (res.status === 404) {
        setError('Record not found (it may belong to another school).')
      } else {
        setError(`Failed to load record (${res.status})`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load record')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const handleRenew = async () => {
    if (!record) return
    const newExpires = prompt('Enter new expiry date (YYYY-MM-DD):')
    if (!newExpires) return
    const expiresAt = new Date(newExpires)
    if (isNaN(expiresAt.getTime()) || expiresAt <= new Date()) {
      alert('Please enter a valid future date.')
      return
    }
    try {
      setBusy(true)
      const res = await apiFetch(`/api/v1/expiration-records/${record.id}/renew`, {
        method: 'POST',
        body: JSON.stringify({ new_expires_at: expiresAt.toISOString() }),
      })
      if (res.ok) {
        setRecord(await res.json())
      } else {
        alert('Failed to renew. Please try again.')
      }
    } catch {
      alert('Failed to renew. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const handleAcknowledge = async () => {
    if (!record) return
    try {
      setBusy(true)
      const res = await apiFetch(`/api/v1/expiration-records/${record.id}/acknowledge`, { method: 'POST' })
      if (res.ok) setRecord(await res.json())
    } catch { /* ignore */ } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!record) return
    if (!confirm('Delete this expiration record? This cannot be undone.')) return
    try {
      setBusy(true)
      const res = await apiFetch(`/api/v1/expiration-records/${record.id}`, { method: 'DELETE' })
      if (res.ok || res.status === 204) {
        navigate('/expiration-records')
      } else {
        alert('Failed to delete record.')
      }
    } catch {
      alert('Failed to delete record.')
    } finally {
      setBusy(false)
    }
  }

  /* ── Loading / error ─────────────────────────────────────────────── */

  if (loading) return <div className="loading-state">Loading record…</div>
  if (error || !record) {
    return (
      <div className="expiration-detail page-shell">
        <div className="exp-detail-error">
          <h2>{error || 'Record not found'}</h2>
          <Link to="/expiration-records" className="btn btn-ghost">← Back to Expiration Records</Link>
        </div>
      </div>
    )
  }

  /* ── Render ──────────────────────────────────────────────────────── */

  const metaRows: Array<{ label: string; value: string }> = [
    { label: 'Entity type', value: record.entity_type },
    { label: 'Status', value: STATUS_LABELS[record.status] || record.status },
    { label: 'Issued', value: record.issued_at ? formatDate(record.issued_at) : '—' },
    { label: 'Expires', value: record.expires_at ? formatDate(record.expires_at) : '—' },
    { label: 'Renew by', value: record.renew_by_at ? formatDate(record.renew_by_at) : '—' },
    { label: 'Renewed at', value: record.renewed_at ? formatDateTime(record.renewed_at) : '—' },
    { label: 'Reminder lead', value: `${record.reminder_lead_days} days` },
    { label: 'Reminder sent', value: record.reminder_sent_at ? formatDateTime(record.reminder_sent_at) : 'Not sent' },
    { label: 'Acknowledged', value: record.is_acknowledged ? 'Yes' : 'No' },
    { label: 'Department', value: record.department_id ? record.department_id : '—' },
    { label: 'Created', value: record.created_at ? formatDateTime(record.created_at) : '—' },
    { label: 'Updated', value: record.updated_at ? formatDateTime(record.updated_at) : '—' },
  ]

  return (
    <div className="expiration-detail page-shell">

      {/* ── Page Header ─────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">
            <Link to="/expiration-records">Expiration Records</Link> / Detail
          </div>
          <h1>{record.title}</h1>
        </div>
        <div className="exp-detail-actions">
          {record.status !== 'renewed' && (
            <button className="btn btn-primary" onClick={handleRenew} disabled={busy}>
              Mark as renewed
            </button>
          )}
          {!record.is_acknowledged && (
            <button className="btn btn-ghost" onClick={handleAcknowledge} disabled={busy}>
              Acknowledge
            </button>
          )}
          <button className="btn btn-ghost exp-delete-btn" onClick={handleDelete} disabled={busy}>
            Delete
          </button>
        </div>
      </div>

      {/* ── Urgency banner ──────────────────────────────────────────── */}
      <div className={`exp-detail-banner ${urgencyClass(record)}`}>
        <strong>{urgencyLabel(record)}</strong>
        {record.expires_at && <span> — expires {formatDate(record.expires_at)}</span>}
      </div>

      {/* ── Description ─────────────────────────────────────────────── */}
      {record.description && (
        <div className="exp-detail-section">
          <h3>Description</h3>
          <p>{record.description}</p>
        </div>
      )}

      {/* ── Document reference / link ───────────────────────────────── */}
      {(record.document_reference || record.entity_link) && (
        <div className="exp-detail-section">
          <h3>Documentation</h3>
          {record.document_reference && <p>{record.document_reference}</p>}
          {record.entity_link && (
            <p>
              <a href={record.entity_link} target="_blank" rel="noreferrer">{record.entity_link}</a>
            </p>
          )}
        </div>
      )}

      {/* ── Metadata grid ───────────────────────────────────────────── */}
      <div className="exp-detail-section">
        <h3>Details</h3>
        <div className="exp-detail-grid">
          {metaRows.map(row => (
            <div key={row.label} className="exp-detail-row">
              <span className="exp-detail-label">{row.label}</span>
              <span className="exp-detail-value">{row.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

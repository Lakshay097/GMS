import { useState, useEffect } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import './TaskDetail.css'

const ETA_EXTENSION_CAP = 4

interface Task {
  id: string
  title: string
  description?: string
  school_id: string
  school_name?: string
  department_id?: string
  department_name?: string
  created_by: string
  created_by_name?: string
  completion_rule: string
  eta: string
  eta_extension_count: number
  status: string
  priority?: 'high' | 'medium' | 'low'
  entity_type?: string
  entity_id?: string
  owners?: Array<{ user_id: string; full_name?: string; email?: string; status?: string }>
  created_at: string
  updated_at: string
  completed_at?: string
  cancelled_at?: string
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function statusLabel(status: string): string {
  switch (status) {
    case 'open': return 'Pending'
    case 'in_progress': return 'In Progress'
    case 'completed': return 'Completed'
    case 'cancelled': return 'Cancelled'
    case 'escalated': return 'Escalated'
    default: return status
  }

}

function priorityLabel(priority?: string): string {
  if (!priority) return 'Medium'
  return priority.charAt(0).toUpperCase() + priority.slice(1)
}

function isOverdue(eta: string): boolean {
  return new Date(eta).getTime() < Date.now()
}

export default function TaskDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showExtensionForm, setShowExtensionForm] = useState(false)
  const [newEta, setNewEta] = useState('')
  const [justification, setJustification] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showCompleteConfirm, setShowCompleteConfirm] = useState(false)

  useEffect(() => { fetchTask() }, [id])

  const fetchTask = async () => {
    try {
      setLoading(true)
      const res = await apiFetch(`/api/v1/tasks/${id}`)
      if (res.ok) {
        setTask(await res.json())
      } else {
        throw new Error('Failed to fetch task')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = async () => {
    setShowCompleteConfirm(false)
    try {
      setSubmitting(true)
      const res = await apiFetch(`/api/v1/tasks/${id}/complete`, {
        method: 'POST',
        body: JSON.stringify({ completed_by: 'current-user', notes: '' }),
      })
      if (!res.ok) throw new Error('Failed to complete task')
      await fetchTask()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete task')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEtaExtension = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSubmitting(true)
      const res = await apiFetch(`/api/v1/tasks/${id}/eta-extension`, {
        method: 'POST',
        body: JSON.stringify({ requested_by: 'current-user', new_eta: new Date(newEta).toISOString(), justification }),
      })
      if (!res.ok) throw new Error('Failed to request ETA extension')
      const result = await res.json()
      setSuccess(result.message)
      setTimeout(() => setSuccess(null), 5000)
      setShowExtensionForm(false)
      setNewEta('')
      setJustification('')
      await fetchTask()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request ETA extension')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="loading-state">Loading task…</div>
  if (error) return <div className="error">{error}</div>
  if (!task) return <div className="empty-state">Task not found</div>

  const canComplete = task.status === 'open' || task.status === 'in_progress'
  const canExtend = task.status !== 'completed' && task.status !== 'cancelled'
  const atExtensionCap = task.eta_extension_count >= ETA_EXTENSION_CAP
  const isTerminal = task.status === 'completed' || task.status === 'cancelled'
  const overdue = isOverdue(task.eta) && canExtend

  return (
    <div className="task-detail page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <button onClick={() => navigate('/tasks')} className="btn btn-ghost btn-sm" style={{ marginBottom: 'var(--space-2)' }}>
            ← Tasks
          </button>
          <h1>Task Details</h1>
        </div>
      </div>

      {success && (
        <div className="alert alert-success">
          <span className="alert-icon">✓</span>
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="alert-close">×</button>
        </div>
      )}

      {/* ── Info Card ────────────────────────────────────────────────── */}
      <div className="task-detail__card">

        {/* Title + status + priority */}
        <div className="task-detail__title-row">
          <h2 className="task-detail__title">{task.title}</h2>
          <div className="task-detail__badges">
            <span className={`status-pill status-pill--${task.status === 'open' ? 'pending' : task.status === 'in_progress' ? 'progress' : task.status === 'completed' ? 'completed' : 'pending'}`}>
              {statusLabel(task.status)}
            </span>
            <span className="task-detail__priority">
              <span className={`dot ${task.priority === 'high' ? 'high' : task.priority === 'low' ? 'low' : 'med'}`} />
              <span>{priorityLabel(task.priority)}</span>
            </span>
          </div>
        </div>

        {/* Description */}
        {task.description && (
          <div className="task-detail__description">
            <p>{task.description}</p>
          </div>
        )}

        {/* Owners */}
        {task.owners && task.owners.length > 0 && (
          <div className="task-detail__section">
            <span className="task-detail__label">Owners</span>
            <div className="task-detail__chips">
              {task.owners.map((owner, i) => {
                const isInactive = owner.status && owner.status !== 'active'
                return (
                  <span key={owner.user_id || i} className={`owner-chip ${isInactive ? 'owner-chip--inactive' : ''}`}>
                    <span className="owner-chip__name">{owner.full_name || owner.email || 'Unknown'}</span>
                    {isInactive && <span className="owner-chip__tag">Inactive</span>}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Info grid */}
        <div className="task-detail__grid">
          <div className="task-detail__field">
            <span className="task-detail__label">School</span>
            <span className="task-detail__value">
              {task.school_name ? (
                <Link to="/schools" className="task-detail__link">{task.school_name}</Link>
              ) : (
                task.school_id || '—'
              )}
            </span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">Department</span>
            <span className="task-detail__value">{task.department_name || '—'}</span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">Created By</span>
            <span className="task-detail__value task-detail__person">
              <span className="avatar-mini">{(task.created_by_name || 'U').charAt(0).toUpperCase()}</span>
              <span>{task.created_by_name || 'Unknown'}</span>
            </span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">Completion Rule</span>
            <span className="task-detail__value">{task.completion_rule.replace(/_/g, ' ')}</span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">ETA</span>
            <span className={`task-detail__value ${overdue ? 'task-detail__value--overdue' : ''}`}>
              {formatDateTime(task.eta)}
            </span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">ETA Extensions</span>
            <span className="task-detail__value">
              {task.eta_extension_count} of {ETA_EXTENSION_CAP} used
            </span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">Created</span>
            <span className="task-detail__value">{formatDateTime(task.created_at)}</span>
          </div>

          <div className="task-detail__field">
            <span className="task-detail__label">Updated</span>
            <span className="task-detail__value">{formatDateTime(task.updated_at)}</span>
          </div>

          {task.completed_at && (
            <div className="task-detail__field">
              <span className="task-detail__label">Completed</span>
              <span className="task-detail__value">{formatDateTime(task.completed_at)}</span>
            </div>
          )}

          {task.entity_type && (
            <div className="task-detail__field">
              <span className="task-detail__label">Entity</span>
              <span className="task-detail__value">{task.entity_type}{task.entity_id ? `: ${task.entity_id}` : ''}</span>
            </div>
          )}
        </div>

        {/* ── Action Row ──────────────────────────────────────────────── */}
        <div className="task-detail__actions">
          {canComplete && (
            <button
              className="btn btn-primary"
              onClick={() => setShowCompleteConfirm(true)}
              disabled={submitting}
            >
              Complete Task
            </button>
          )}

          {canExtend && (
            <button
              className="btn btn-secondary"
              onClick={() => setShowExtensionForm(!showExtensionForm)}
              disabled={submitting || atExtensionCap}
              title={atExtensionCap ? `Maximum extensions reached (${ETA_EXTENSION_CAP}). This task will be automatically escalated.` : undefined}
            >
              Request ETA Extension
            </button>
          )}

          <button
            className="btn btn-ghost"
            onClick={() => navigate(`/tasks/${id}/edit`)}
          >
            Edit Task
          </button>
        </div>

        {/* Terminal-state notice */}
        {isTerminal && (
          <div className="task-detail__terminal-notice">
            {task.status === 'completed'
              ? `This task was completed on ${formatDate(task.completed_at)} and can no longer be modified.`
              : `This task was cancelled on ${formatDate(task.cancelled_at)} and can no longer be modified.`}
          </div>
        )}

        {/* Extension cap notice */}
        {canExtend && atExtensionCap && (
          <div className="task-detail__terminal-notice">
            Maximum extensions reached ({ETA_EXTENSION_CAP}). This task will be automatically escalated.
          </div>
        )}

        {/* ── ETA Extension Form ──────────────────────────────────────── */}
        {showExtensionForm && (
          <form onSubmit={handleEtaExtension} className="task-detail__extension-form">
            <h3>Request ETA Extension</h3>
            <div className="task-detail__grid" style={{ marginBottom: 'var(--space-4)' }}>
              <div className="form-group">
                <label htmlFor="new_eta">New ETA *</label>
                <input
                  id="new_eta"
                  type="datetime-local"
                  value={newEta}
                  onChange={(e) => setNewEta(e.target.value)}
                  required
                  className="form-group__input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="justification">Justification</label>
                <textarea
                  id="justification"
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  rows={3}
                  className="form-group__input form-group__textarea"
                  placeholder="Optional justification for the extension"
                />
              </div>
            </div>
            <div className="task-detail__extension-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowExtensionForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? 'Submitting…' : 'Submit Request'}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* ── Complete Task Confirm Modal ───────────────────────────────── */}
      {showCompleteConfirm && (
        <div className="modal-overlay" onClick={() => setShowCompleteConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Complete Task</h3>
              <button onClick={() => setShowCompleteConfirm(false)} className="modal-close">×</button>
            </div>
            <div className="modal-body">
              <p>Mark this task complete?</p>
              <p className="modal-consequence">
                This action cannot be undone. The task will be marked completed as of today and can no longer be edited or extended.
              </p>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowCompleteConfirm(false)} className="btn btn-ghost">
                Cancel
              </button>
              <button onClick={handleComplete} disabled={submitting} className="btn btn-primary">
                {submitting ? 'Completing…' : 'Confirm Complete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import {
  ArrowLeft,
  CheckCircle,
  Circle,
  Loader2,
  Search,
} from 'lucide-react'
import './DiscrepancyDetail.css'

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

/* ── State machine definition ─────────────────────────────────────────────── */

const STATE_STEPS = [
  { key: 'raised', label: 'Raised' },
  { key: 'under_investigation', label: 'Investigation' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'pending_approval', label: 'Approval' },
  { key: 'approved', label: 'Approved' },
  { key: 'closed', label: 'Closed' },
] as const


const STATE_INDEX: Record<string, number> = {
  raised: 0,
  under_investigation: 1,
  resolved: 2,
  pending_approval: 3,
  approved: 4,
  closed: 4, // approved and closed are both terminal
}

const STATE_BADGE_CLASS: Record<string, string> = {
  raised: 'badge--amber',
  under_investigation: 'badge--gold',
  resolved: 'badge--moss',
  pending_approval: 'badge--amber',
  approved: 'badge--moss',
  closed: 'badge--neutral',
}

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

export default function DiscrepancyDetail() {
  const { id } = useParams()

  const [discrepancy, setDiscrepancy] = useState<Discrepancy | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Action forms
  const [showAssignForm, setShowAssignForm] = useState(false)
  const [showFindingsForm, setShowFindingsForm] = useState(false)
  const [assigneeQuery, setAssigneeQuery] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [findings, setFindings] = useState('')

  // Name resolution is now handled by backend enrichment
  const [currentUser, setCurrentUser] = useState<string>('')

  /* ── Fetch data + resolve names ──────────────────────────────────────── */

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    const fetchAll = async () => {
      try {
        setLoading(true)
        setError(null)

        // Single fetch — backend now enriches with resolved names
        const discRes = await apiFetch(`/api/v1/audit-discrepancy/discrepancies/${id}`, { signal })

        if (!discRes.ok) throw new Error('Failed to fetch discrepancy')
        setDiscrepancy(await discRes.json())

        // Get current user from localStorage
        setCurrentUser(localStorage.getItem('user_id') || '')
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoading(false)
      }
    }

    if (id) fetchAll()
    return () => controller.abort()
  }, [id])

  /* ── Resolve helpers (use enriched fields from backend) ────────────── */

  // Name resolution is handled by backend enrichment fields:
  // raised_by_name, investigation_owner_name, category_name, etc.

  /* ── State machine logic ─────────────────────────────────────────────── */

  const currentIndex = discrepancy ? (STATE_INDEX[discrepancy.state] ?? 0) : 0
  const isTerminal = discrepancy?.state === 'closed' || discrepancy?.state === 'approved'
  const canAssign = discrepancy?.state === 'raised'
  const canSubmitFindings = discrepancy?.state === 'under_investigation'
  const canStartApproval = discrepancy?.state === 'resolved'
  const canApprove = discrepancy?.state.startsWith('pending_approval')

  // Segregation-of-duties guard: approver cannot be the investigation owner or a prior approver (R-27/R-49)
  // NOTE: Backend does NOT block the raised_by_user — only investigation_owner and prior_approvers.
  // Frontend matches backend truth, not a stricter heuristic.
  const isSelfApprovalBlocked = useMemo(() => {
    if (!discrepancy || !currentUser) return false
    return (
      discrepancy.investigation_owner_id != null &&
      currentUser === discrepancy.investigation_owner_id
    )
  }, [discrepancy, currentUser])

  /* ── Action handlers ─────────────────────────────────────────────────── */

  const fetchDiscrepancy = useCallback(async () => {
    if (!id) return
    try {
      const response = await apiFetch(`/api/v1/audit-discrepancy/discrepancies/${id}`)
      if (response.ok) setDiscrepancy(await response.json())
    } catch {
      // silent
    }
  }, [id])

  const handleAssignInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!assigneeId.trim()) return
    try {
      setSubmitting(true)
      const response = await apiFetch(
        `/api/v1/audit-discrepancy/discrepancies/${id}/assign-investigation`,
        {
          method: 'POST',
          body: JSON.stringify({ investigation_owner_id: assigneeId }),
        }
      )
      if (!response.ok) throw new Error('Failed to assign investigation')
      setShowAssignForm(false)
      setAssigneeId('')
      setAssigneeQuery('')
      await fetchDiscrepancy()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to assign')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmitFindings = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!findings.trim()) return
    try {
      setSubmitting(true)
      const response = await apiFetch(
        `/api/v1/audit-discrepancy/discrepancies/${id}/submit-findings`,
        {
          method: 'POST',
          body: JSON.stringify({ investigation_findings: findings.trim() }),
        }
      )
      if (!response.ok) throw new Error('Failed to submit findings')
      setShowFindingsForm(false)
      setFindings('')
      await fetchDiscrepancy()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit findings')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStartApproval = async () => {
    try {
      setSubmitting(true)
      const response = await apiFetch(
        `/api/v1/audit-discrepancy/discrepancies/${id}/start-approval`,
        { method: 'POST' }
      )
      if (!response.ok) throw new Error('Failed to start approval')
      await fetchDiscrepancy()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start approval')
    } finally {
      setSubmitting(false)
    }
  }

  const handleApprove = async () => {
    try {
      setSubmitting(true)
      const response = await apiFetch(
        `/api/v1/audit-discrepancy/discrepancies/${id}/approve`,
        {
          method: 'POST',
          body: JSON.stringify({
            level: 1,
            approver_id: currentUser,
            comments: '',
          }),
        }
      )
      if (!response.ok) throw new Error('Failed to approve')
      await fetchDiscrepancy()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve')
    } finally {
      setSubmitting(false)
    }
  }

  /* ── Derived values ──────────────────────────────────────────────────── */

  const raisedByName = discrepancy?.raised_by_name || ''
  const ownerName = discrepancy?.investigation_owner_name || ''
  const obsTitle = discrepancy?.observation_title || ''
  const catName = discrepancy?.category_name || ''
  const schoolName = discrepancy?.school_name || ''
  const deptName = discrepancy?.department_name || ''

  // Timeline: only show reached stages
  const timeline = useMemo(() => {
    if (!discrepancy) return []
    const items: { label: string; date: string }[] = []
    if (discrepancy.raised_at) {
      items.push({ label: 'Raised', date: discrepancy.raised_at })
    }
    if (discrepancy.under_investigation_at) {
      items.push({ label: 'Investigation Started', date: discrepancy.under_investigation_at })
    }
    if (discrepancy.resolved_at) {
      items.push({ label: 'Resolved', date: discrepancy.resolved_at })
    }
    if (discrepancy.closed_at) {
      items.push({ label: 'Closed', date: discrepancy.closed_at })
    }
    return items
  }, [discrepancy])

  /* ── Render ──────────────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="discrepancy-detail page-shell">
        <div className="discrepancy-detail__loading">
          <Loader2 size={20} className="discrepancy-detail__loading-icon" />
          <span>Loading discrepancy…</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="discrepancy-detail page-shell">
        <div className="discrepancy-detail__error">{error}</div>
      </div>
    )
  }

  if (!discrepancy) {
    return (
      <div className="discrepancy-detail page-shell">
        <div className="discrepancy-detail__empty">Discrepancy not found</div>
      </div>
    )
  }

  return (
    <div className="discrepancy-detail page-shell">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="discrepancy-detail__header">
        <Link to="/discrepancies" className="discrepancy-detail__back btn btn-ghost btn-sm">
          <ArrowLeft size={16} />
          <span>Discrepancies</span>
        </Link>
        <div className="discrepancy-detail__header-main">
          <div>
            <span className="eyebrow">
              <span className="eyebrow__dot" />
              Discrepancy Detail
            </span>
            <h1>Discrepancy Details</h1>
          </div>
          <div className="discrepancy-detail__header-meta">
            <span className="discrepancy-detail__ref">{discrepancy.id.slice(0, 8)}</span>
            <span className={`badge ${STATE_BADGE_CLASS[discrepancy.state] || 'badge--neutral'}`}>
              {formatState(discrepancy.state)}
            </span>
          </div>
        </div>
      </div>

      {/* ── State Progress Stepper ──────────────────────────────────────── */}
      <div className="discrepancy-detail__stepper">
        {STATE_STEPS.map((step, index) => {
          const stepIdx = STATE_INDEX[step.key] ?? index
          const isCompleted = stepIdx < currentIndex
          const isCurrent = step.key === discrepancy.state ||
            (discrepancy.state === 'approved' && step.key === 'approved') ||
            (discrepancy.state === 'closed' && step.key === 'closed')
          const isFuture = stepIdx > currentIndex

          return (
            <div
              key={step.key}
              className={`discrepancy-detail__step ${
                isCurrent ? 'discrepancy-detail__step--current' : ''
              } ${isCompleted ? 'discrepancy-detail__step--completed' : ''} ${
                isFuture ? 'discrepancy-detail__step--future' : ''
              }`}
            >
              <div className="discrepancy-detail__step-icon">
                {isCompleted ? (
                  <CheckCircle size={18} />
                ) : (
                  <Circle size={18} />
                )}
              </div>
              <span className="discrepancy-detail__step-label">{step.label}</span>
              {index < STATE_STEPS.length - 1 && (
                <div className="discrepancy-detail__step-connector" />
              )}
            </div>
          )
        })}
      </div>

      {/* ── Info Card ───────────────────────────────────────────────────── */}
      <div className="discrepancy-detail__card">
        <div className="discrepancy-detail__grid">
          {/* Observation — resolved link */}
          <div className="discrepancy-detail__field">
            <span className="discrepancy-detail__label">Observation</span>
            <Link
              to={`/observations/${discrepancy.observation_id}`}
              className="discrepancy-detail__link"
            >
              {obsTitle || discrepancy.observation_id.slice(0, 8)}
            </Link>
          </div>

          {/* Category — resolved name */}
          <div className="discrepancy-detail__field">
            <span className="discrepancy-detail__label">Category</span>
            <span className="discrepancy-detail__value">
              {catName || discrepancy.category_id.slice(0, 8)}
            </span>
          </div>

          {/* School — resolved name, link */}
          <div className="discrepancy-detail__field">
            <span className="discrepancy-detail__label">School</span>
            <Link
              to={`/schools/${discrepancy.school_id}/edit`}
              className="discrepancy-detail__link"
            >
              {schoolName || discrepancy.school_id.slice(0, 8)}
            </Link>
          </div>

          {/* Department — resolved name, link */}
          <div className="discrepancy-detail__field">
            <span className="discrepancy-detail__label">Department</span>
            {discrepancy.department_id ? (
              <Link
                to={`/departments/${discrepancy.department_id}/edit`}
                className="discrepancy-detail__link"
              >
                {deptName || discrepancy.department_id.slice(0, 8)}
              </Link>
            ) : (
              <span className="discrepancy-detail__value">–</span>
            )}
          </div>

          {/* Raised By — mini-avatar + name */}
          <div className="discrepancy-detail__field">
            <span className="discrepancy-detail__label">Raised By</span>
            <div className="discrepancy-detail__person">
              <span className="avatar-mini">{getInitials(raisedByName)}</span>
              <span className="discrepancy-detail__person-name">
                {raisedByName || discrepancy.raised_by_user_id.slice(0, 8)}
              </span>
            </div>
          </div>

          {/* Investigation Owner — mini-avatar + name, or "Not assigned" */}
          <div className="discrepancy-detail__field">
            <span className="discrepancy-detail__label">Investigation Owner</span>
            {discrepancy.investigation_owner_id ? (
              <div className="discrepancy-detail__person">
                <span className="avatar-mini">{getInitials(ownerName)}</span>
                <span className="discrepancy-detail__person-name">
                  {ownerName || discrepancy.investigation_owner_id.slice(0, 8)}
                </span>
                {/* User active status shown by backend enrichment */}
              </div>
            ) : (
              <span className="discrepancy-detail__not-assigned">Not assigned</span>
            )}
          </div>
        </div>

        {/* ── Timeline ──────────────────────────────────────────────────── */}
        {timeline.length > 0 && (
          <div className="discrepancy-detail__timeline">
            <h3 className="discrepancy-detail__section-title">Timeline</h3>
            <div className="discrepancy-detail__timeline-list">
              {timeline.map((item) => (
                <div key={item.label} className="discrepancy-detail__timeline-item">
                  <span className="discrepancy-detail__timeline-label">{item.label}</span>
                  <span className="discrepancy-detail__timeline-date">
                    {new Date(item.date).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Investigation Findings ────────────────────────────────────── */}
        {discrepancy.investigation_findings && (
          <div className="discrepancy-detail__findings">
            <h3 className="discrepancy-detail__section-title">Investigation Findings</h3>
            <div className="discrepancy-detail__findings-text">
              {discrepancy.investigation_findings}
            </div>
          </div>
        )}

        {/* ── Terminal State Notice ─────────────────────────────────────── */}
        {isTerminal && (
          <div className="discrepancy-detail__terminal-notice">
            This discrepancy was {discrepancy.state === 'approved' ? 'approved' : 'closed'}
            {discrepancy.closed_at
              ? ` on ${new Date(discrepancy.closed_at).toLocaleDateString()}`
              : discrepancy.resolved_at
              ? ` on ${new Date(discrepancy.resolved_at).toLocaleDateString()}`
              : ''}{' '}
            and cannot be modified further.
          </div>
        )}
      </div>

      {/* ── Action Row ──────────────────────────────────────────────────── */}
      {!isTerminal && (
        <div className="discrepancy-detail__actions">
          {canAssign && (
            <button
              className="btn btn-primary"
              onClick={() => setShowAssignForm(!showAssignForm)}
              disabled={submitting}
            >
              Assign Investigation
            </button>
          )}

          {canSubmitFindings && (
            <button
              className="btn btn-primary"
              onClick={() => setShowFindingsForm(!showFindingsForm)}
              disabled={submitting}
            >
              Submit Findings
            </button>
          )}

          {canStartApproval && (
            <button
              className="btn btn-ghost"
              onClick={handleStartApproval}
              disabled={submitting}
            >
              Start Approval
            </button>
          )}

          {canApprove && (
            <button
              className="btn btn-primary"
              onClick={handleApprove}
              disabled={submitting || isSelfApprovalBlocked}
              title={
                isSelfApprovalBlocked
                  ? 'You cannot approve a discrepancy you investigated (segregation of duties)'
                  : undefined
              }
            >
              {submitting ? 'Approving…' : 'Approve'}
            </button>
          )}
        </div>
      )}

      {/* ── Inline: Assign Investigation ────────────────────────────────── */}
      {showAssignForm && (
        <div className="discrepancy-detail__inline-form">
          <h3 className="discrepancy-detail__section-title">Assign Investigation Owner</h3>
          <form onSubmit={handleAssignInvestigation}>
            <div className="discrepancy-detail__field">
              <label className="discrepancy-detail__label" htmlFor="assignee-search">
                Investigation Owner *
              </label>
              <div className="discrepancy-detail__search-select">
                <Search size={16} className="discrepancy-detail__search-icon" />
                <input
                  id="assignee-search"
                  type="text"
                  className="input"
                  value={assigneeQuery}
                  onChange={(e) => {
                    setAssigneeQuery(e.target.value)
                    setAssigneeId('')
                  }}
                  placeholder="Search by name or email…"
                  autoComplete="off"
                />
                {assigneeId && (
                  <span className="discrepancy-detail__selected-chip">
                    {discrepancy?.investigation_owner_name || assigneeId.slice(0, 8)}
                    <button
                      type="button"
                      className="discrepancy-detail__chip-remove"
                      onClick={() => {
                        setAssigneeId('')
                        setAssigneeQuery('')
                      }}
                    >
                      ×
                    </button>
                  </span>
                )}
                {/* User search dropdown: requires backend-powered user search API */}
              </div>
            </div>
            <div className="discrepancy-detail__inline-actions">
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={submitting || !assigneeId}
              >
                {submitting ? 'Assigning…' : 'Assign'}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setShowAssignForm(false)
                  setAssigneeId('')
                  setAssigneeQuery('')
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Inline: Submit Findings ─────────────────────────────────────── */}
      {showFindingsForm && (
        <div className="discrepancy-detail__inline-form">
          <h3 className="discrepancy-detail__section-title">Submit Investigation Findings</h3>
          <form onSubmit={handleSubmitFindings}>
            <div className="discrepancy-detail__field">
              <label className="discrepancy-detail__label" htmlFor="findings-textarea">
                Findings *
              </label>
              <textarea
                id="findings-textarea"
                className="input"
                value={findings}
                onChange={(e) => setFindings(e.target.value)}
                rows={5}
                required
                placeholder="Enter investigation findings…"
              />
            </div>
            <div className="discrepancy-detail__inline-actions">
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={submitting || !findings.trim()}
              >
                {submitting ? 'Submitting…' : 'Submit Findings'}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setShowFindingsForm(false)
                  setFindings('')
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

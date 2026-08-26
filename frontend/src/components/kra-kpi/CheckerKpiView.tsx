import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useKpiContext } from '../../contexts/KpiContext'
import { apiFetch } from '../../lib/api'
import './CheckerKpiView.css'

interface Observation {
  id: string
  kpi_id: string
  kpi_title: string
  kpi_target_value: string
  kpi_unit: string
  kpi_comparator: string
  department_name: string
  checker_name: string
  value_numeric: number
  value_text: string | null
  submission_date: string
  rag_status: string
  auto_result: string
  status: string
  is_late: boolean
  // Verification and rejection fields
  verified_by: string | null
  rejected_by: string | null
  // Reopen request fields
  is_reopened: boolean
  reopen_requested_at: string | null
  reopen_requested_by: string | null
  reopen_reason: string | null
  reopen_approved_at: string | null
  reopen_approved_by: string | null
}

export default function CheckerKpiView() {
  const location = useLocation()
  const { getKpiById } = useKpiContext()
  const [allObservations, setAllObservations] = useState<Observation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterDepartment, setFilterDepartment] = useState<string>('all')
  const [filterRag, setFilterRag] = useState<string>('all')
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])
  const [verifying, setVerifying] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [selectedObservation, setSelectedObservation] = useState<Observation | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')
  const [selectedObservations, setSelectedObservations] = useState<Set<string>>(new Set())
  const [bulkAction, setBulkAction] = useState<'verify' | 'reject' | null>(null)
  const [requestingReopen, setRequestingReopen] = useState<string | null>(null)
  const [showReopenModal, setShowReopenModal] = useState(false)
  const [reopenReason, setReopenReason] = useState('')
  const [approvingReopen, setApprovingReopen] = useState<string | null>(null)
  const [denyingReopen, setDenyingReopen] = useState<string | null>(null)
  const [showDenyReopenModal, setShowDenyReopenModal] = useState(false)
  const [denyReopenReason, setDenyReopenReason] = useState('')
  const [currentUserId, setCurrentUserId] = useState<string | null>(null)

  // Handle navigation state from Dashboard
  useEffect(() => {
    if (location.state?.filterStatus) {
      const ragStatus = location.state.filterStatus
      if (ragStatus === 'not_submitted') {
        setFilterStatus('pending') // Show pending for not submitted
      } else {
        // Set RAG filter for color-based navigation
        setFilterRag(ragStatus)
      }
    }
  }, [location.state])

  const fetchAllObservations = async (signal?: AbortSignal) => {
    try {
      setLoading(true)
      setError(null)
      
      const res = await apiFetch('/api/v1/observations?page_size=100', { signal })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to fetch observations')
      }
      const data: Observation[] = await res.json()
      setAllObservations(data)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Failed to load observations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      await Promise.all([
        fetchAllObservations(controller.signal),
        fetchCurrentUserId(controller.signal),
      ])
    }
    load()
    return () => controller.abort()
  }, [])

  const handleVerify = async (observationId: string) => {
    setVerifying(observationId)
    try {
      const res = await apiFetch(`/api/v1/observations/${observationId}/verify`, {
        method: 'POST'
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to verify observation')
      }
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to verify observation')
    } finally {
      setVerifying(null)
    }
  }

  const handleRejectClick = (observation: Observation) => {
    setSelectedObservation(observation)
    setShowRejectModal(true)
    setRejectionReason('')
  }

  const handleRejectSubmit = async () => {
    if (!selectedObservation || !rejectionReason.trim()) {
      setError('Please provide a rejection reason')
      return
    }

    setRejecting(selectedObservation.id)
    setError(null)

    try {
      const res = await apiFetch(`/api/v1/observations/${selectedObservation.id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: rejectionReason.trim() })
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        
        // Handle 400 validation error (missing reason) - keep modal open
        if (res.status === 400) {
          setError(body?.error?.message || 'Please provide a rejection reason')
          setRejecting(null)
          return
        }
        
        // Handle 409 conflict (already actioned)
        if (res.status === 409) {
          setError(body?.error?.message || 'This observation was already handled by another reviewer')
          setShowRejectModal(false)
          setSelectedObservation(null)
          setRejectionReason('')
          await fetchAllObservations()
          setRejecting(null)
          return
        }
        
        throw new Error(body?.error?.message || 'Failed to reject observation')
      }
      setShowRejectModal(false)
      setSelectedObservation(null)
      setRejectionReason('')
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject observation')
    } finally {
      setRejecting(null)
    }
  }

  const handleRejectCancel = () => {
    setShowRejectModal(false)
    setSelectedObservation(null)
    setRejectionReason('')
  }

  const handleReopenRequestClick = (observation: Observation) => {
    setSelectedObservation(observation)
    setShowReopenModal(true)
    setReopenReason('')
  }

  const handleReopenRequestSubmit = async () => {
    if (!selectedObservation || !reopenReason.trim()) {
      setError('Please provide a reason for the reopen request')
      return
    }

    setRequestingReopen(selectedObservation.id)
    setError(null)

    try {
      const res = await apiFetch(`/api/v1/observations/${selectedObservation.id}/reopen-request`, {
        method: 'POST',
        body: JSON.stringify({ reason: reopenReason.trim() })
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        if (res.status === 409) {
          throw new Error(body?.error?.message || 'A reopen request already exists for this observation')
        }
        throw new Error(body?.error?.message || 'Failed to request reopen')
      }
      setShowReopenModal(false)
      setSelectedObservation(null)
      setReopenReason('')
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request reopen')
    } finally {
      setRequestingReopen(null)
    }
  }

  const handleReopenRequestCancel = () => {
    setShowReopenModal(false)
    setSelectedObservation(null)
    setReopenReason('')
  }

  const fetchCurrentUserId = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch('/auth/get-session', { signal })
      if (res.ok) {
        const data = await res.json()
        setCurrentUserId(data.user?.id || null)
      }
    } catch (err) {
      console.error('Failed to fetch current user ID:', err)
    }
  }

  const handleApproveReopen = async (observationId: string) => {
    setApprovingReopen(observationId)
    setError(null)

    try {
      const res = await apiFetch(`/api/v1/observations/${observationId}/reopen-approval`, {
        method: 'POST',
        body: JSON.stringify({ approved: true, admin_comment: null })
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to approve reopen request')
      }
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve reopen request')
    } finally {
      setApprovingReopen(null)
    }
  }

  const handleDenyReopenClick = (observation: Observation) => {
    setSelectedObservation(observation)
    setShowDenyReopenModal(true)
    setDenyReopenReason('')
  }

  const handleDenyReopenSubmit = async () => {
    if (!selectedObservation || !denyReopenReason.trim()) {
      setError('Please provide a reason for denying the reopen request')
      return
    }

    setDenyingReopen(selectedObservation.id)
    setError(null)

    try {
      const res = await apiFetch(`/api/v1/observations/${selectedObservation.id}/reopen-approval`, {
        method: 'POST',
        body: JSON.stringify({ approved: false, admin_comment: denyReopenReason.trim() })
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        
        // Handle 400 validation error (missing reason) - keep modal open
        if (res.status === 400) {
          setError(body?.error?.message || 'Please provide a denial reason')
          setDenyingReopen(null)
          return
        }
        
        throw new Error(body?.error?.message || 'Failed to deny reopen request')
      }
      setShowDenyReopenModal(false)
      setSelectedObservation(null)
      setDenyReopenReason('')
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deny reopen request')
    } finally {
      setDenyingReopen(null)
    }
  }

  const handleDenyReopenCancel = () => {
    setShowDenyReopenModal(false)
    setSelectedObservation(null)
    setDenyReopenReason('')
  }

  const canApproveReopen = (observation: Observation): boolean => {
    // Self-approval guard: cannot approve if you originally verified or rejected
    if (!currentUserId) return false
    if (observation.verified_by === currentUserId) return false
    if (observation.rejected_by === currentUserId) return false
    return true
  }

  const handleSelectObservation = (observationId: string) => {
    setSelectedObservations(prev => {
      const newSet = new Set(prev)
      if (newSet.has(observationId)) {
        newSet.delete(observationId)
      } else {
        newSet.add(observationId)
      }
      return newSet
    })
  }

  const handleSelectAll = () => {
    const pendingObservations = filteredObservations.filter(obs => obs.status.toLowerCase() === 'pending')
    if (selectedObservations.size === pendingObservations.length) {
      setSelectedObservations(new Set())
    } else {
      setSelectedObservations(new Set(pendingObservations.map(obs => obs.id)))
    }
  }

  const handleBulkVerify = async () => {
    if (selectedObservations.size === 0) return
    
    setBulkAction('verify')
    setError(null)

    try {
      const verifyPromises = Array.from(selectedObservations).map(obsId =>
        apiFetch(`/api/v1/observations/${obsId}/verify`, { method: 'POST' })
      )
      
      const results = await Promise.allSettled(verifyPromises)
      const succeeded = results.filter(r => r.status === 'fulfilled')
      const failed = results.filter(r => r.status === 'rejected')
      
      if (failed.length > 0) {
        // Check for 409 conflicts (already actioned by another reviewer)
        const conflictErrors = failed.filter(f => {
          if (f.status === 'rejected' && f.reason instanceof Error) {
            try {
              const errorData = JSON.parse(f.reason.message)
              return errorData.error?.code === 'ALREADY_ACTIONED'
            } catch {
              return false
            }
          }
          return false
        })
        
        if (conflictErrors.length > 0) {
          setError(`${succeeded.length} verified, ${conflictErrors.length} skipped — already handled by another reviewer`)
        } else {
          throw new Error(`${failed.length} verification(s) failed`)
        }
      }

      setSelectedObservations(new Set())
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to verify some observations')
    } finally {
      setBulkAction(null)
    }
  }

  const handleBulkRejectClick = () => {
    if (selectedObservations.size === 0) return
    setBulkAction('reject')
    setShowRejectModal(true)
    setRejectionReason('')
  }

  const handleBulkRejectSubmit = async () => {
    if (!rejectionReason.trim()) {
      setError('Please provide a rejection reason')
      return
    }

    setRejecting('bulk')
    setError(null)

    try {
      const rejectPromises = Array.from(selectedObservations).map(obsId =>
        apiFetch(`/api/v1/observations/${obsId}/reject`, {
          method: 'POST',
          body: JSON.stringify({ reason: rejectionReason.trim() })
        })
      )
      
      const results = await Promise.allSettled(rejectPromises)
      const succeeded = results.filter(r => r.status === 'fulfilled')
      const failed = results.filter(r => r.status === 'rejected')
      
      if (failed.length > 0) {
        // Check for 409 conflicts (already actioned by another reviewer)
        const conflictErrors = failed.filter(f => {
          if (f.status === 'rejected' && f.reason instanceof Error) {
            try {
              const errorData = JSON.parse(f.reason.message)
              return errorData.error?.code === 'ALREADY_ACTIONED'
            } catch {
              return false
            }
          }
          return false
        })
        
        if (conflictErrors.length > 0) {
          setError(`${succeeded.length} rejected, ${conflictErrors.length} skipped — already handled by another reviewer`)
        } else {
          throw new Error(`${failed.length} rejection(s) failed`)
        }
      }

      setShowRejectModal(false)
      setSelectedObservations(new Set())
      setRejectionReason('')
      setBulkAction(null)
      await fetchAllObservations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject some observations')
    } finally {
      setRejecting(null)
    }
  }

  const getRagLabel = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'green': return 'Green'
      case 'amber': return 'Amber'
      case 'red': return 'Red'
      case 'not_submitted': return 'Not Submitted'
      default: return status
    }
  }

  const getStatusBadge = (status: string, observation?: Observation) => {
    if (observation?.reopen_requested_at && !observation.reopen_approved_at) {
      return <span className="status-badge status-badge--reopen">Reopen Requested</span>
    }

    const classMap: Record<string, string> = {
      'pending': 'status-badge--pending',
      'verified': 'status-badge--verified',
      'rejected': 'status-badge--rejected',
    }
    const cls = classMap[status.toLowerCase()] || ''
    return <span className={`status-badge ${cls}`}>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
  }

  const getUniqueDepartments = () => {
    const departments = [...new Set(allObservations.map(obs => obs.department_name))]
    return departments.sort()
  }

  const filteredObservations = allObservations.filter(obs => {
    if (selectedDate && obs.submission_date && !obs.submission_date.startsWith(selectedDate)) return false
    if (filterStatus !== 'all' && obs.status.toLowerCase() !== filterStatus) return false
    if (filterDepartment !== 'all' && obs.department_name !== filterDepartment) return false
    if (filterRag !== 'all' && obs.rag_status.toLowerCase() !== filterRag) return false
    if (filterStatus === 'reopen_requested' && !obs.reopen_requested_at) return false
    return true
  })

  const stats = {
    total: allObservations.length,
    pending: allObservations.filter(o => o.status.toLowerCase() === 'pending').length,
    verified: allObservations.filter(o => o.status.toLowerCase() === 'verified').length,
    late: allObservations.filter(o => o.is_late).length,
    reopenRequested: allObservations.filter(o => o.reopen_requested_at && !o.reopen_approved_at).length
  }

  if (loading) {
    return (
      <div className="checker-kpi-view page-shell">
        <div className="loading-state">
          <p>Loading KPI observations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="checker-kpi-view page-shell">
      <div className="page-head">
        <div>
          <div className="eyebrow">Verification</div>
          <h1>KPI Verification</h1>
        </div>
        <div className="header-actions">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="date-picker"
            max={new Date().toISOString().split('T')[0]}
          />
        </div>
      </div>

      {/* Stats Ribbon — flat --ink-900 */}
      <div className="ribbon" style={{ margin: 'var(--space-5) 0' }}>
        <div className="ribbon-item">
          <div className="ribbon-num">{stats.total}</div>
          <div className="ribbon-label">Total</div>
        </div>
        <div className="ribbon-item">
          <div className="ribbon-num">{stats.pending}</div>
          <div className="ribbon-label">Pending</div>
        </div>
        <div className="ribbon-item accent">
          <div className="ribbon-num">{stats.verified}</div>
          <div className="ribbon-label">Verified</div>
        </div>
        <div className="ribbon-item warn">
          <div className="ribbon-num">{stats.late}</div>
          <div className="ribbon-label">Late</div>
        </div>
        <div className="ribbon-item accent">
          <div className="ribbon-num">{stats.reopenRequested}</div>
          <div className="ribbon-label">Reopen</div>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <div className="filter-group">
          <label htmlFor="status-filter">Status:</label>
          <select
            id="status-filter"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="verified">Verified</option>
            <option value="rejected">Rejected</option>
            <option value="reopen_requested">Reopen Requests</option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="department-filter">Department:</label>
          <select
            id="department-filter"
            value={filterDepartment}
            onChange={(e) => setFilterDepartment(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Departments</option>
            {getUniqueDepartments().map(dept => (
              <option key={dept} value={dept}>{dept}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={selectedObservations.size > 0}
              onChange={handleSelectAll}
              disabled={filteredObservations.filter(obs => obs.status.toLowerCase() === 'pending').length === 0}
            />
            <span>Select All Pending</span>
          </label>
        </div>
      </div>

      {/* Bulk Action Bar */}
      {selectedObservations.size > 0 && (
        <div className="bulk-action-bar">
          <span className="bulk-action-count">
            {selectedObservations.size} observation{selectedObservations.size !== 1 ? 's' : ''} selected
          </span>
          <div className="bulk-action-buttons">
            <button
              onClick={handleBulkVerify}
              disabled={bulkAction !== null}
              className="btn btn-primary btn-sm"
            >
              {bulkAction === 'verify' ? 'Verifying...' : 'Verify All'}
            </button>
            <button
              onClick={handleBulkRejectClick}
              disabled={bulkAction !== null}
              className="btn btn-danger btn-sm"
            >
              {bulkAction === 'reject' ? 'Rejecting...' : 'Reject All'}
            </button>
            <button
              onClick={() => setSelectedObservations(new Set())}
              disabled={bulkAction !== null}
              className="btn btn-secondary btn-sm"
            >
              Clear Selection
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="alert-close">×</button>
        </div>
      )}

      {filteredObservations.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>No observations found</h3>
          <p>No KPI submissions match the current filters.</p>
        </div>
      ) : (
        <div className="observations-list">
          {filteredObservations.map(observation => {
            const isReopen = !!observation.reopen_requested_at && !observation.reopen_approved_at
            return (
            <div key={observation.id} className={`observation-card ${isReopen ? 'observation-card--reopen' : ''}`}>
              <div className="observation-card__header">
                <div className="observation-card__select">
                  {observation.status.toLowerCase() === 'pending' && (
                    <input
                      type="checkbox"
                      checked={selectedObservations.has(observation.id)}
                      onChange={() => handleSelectObservation(observation.id)}
                      disabled={bulkAction !== null}
                    />
                  )}
                </div>
                <div className="observation-card__kpi">
                  <h3>{observation.kpi_title}</h3>
                  <div className="observation-card__meta">
                    <span className="department-badge">{observation.department_name}</span>
                    <span className="checker-badge">Submitted by: {observation.checker_name}</span>
                    {observation.is_late && (
                      <span className="late-badge">Late Submission</span>
                    )}
                  </div>
                </div>
                <div className="observation-card__rag">
                  <div className="rag-indicator">
                    <span className={`rag-dot rag-dot--${observation.rag_status.toLowerCase()}`} />
                    <span className={`rag-text--${observation.rag_status.toLowerCase()}`}>{getRagLabel(observation.rag_status)}</span>
                  </div>
                </div>
              </div>

              <div className="observation-card__body">
                <div className="observation-card__values">
                  <div className="value-group">
                    <span className="value-label">Target:</span>
                    <span className="value-value">
                      {(() => {
                        const kpi = getKpiById(observation.kpi_id)
                        return kpi ? `${kpi.target_value} ${kpi.unit_of_measure}` : `${observation.kpi_target_value} ${observation.kpi_unit}`
                      })()}
                    </span>
                  </div>
                  <div className="value-group">
                    <span className="value-label">Actual:</span>
                    <span className="value-value">
                      {observation.value_numeric} {observation.kpi_unit}
                    </span>
                  </div>
                  <div className="value-group">
                    <span className="value-label">Result:</span>
                    <span className="value-value value-result">
                      {observation.auto_result}
                    </span>
                  </div>
                </div>

                {observation.value_text && (
                  <div className="observation-card__notes">
                    <strong>Notes:</strong> {observation.value_text}
                  </div>
                )}

                {observation.reopen_requested_at && !observation.reopen_approved_at && (
                  <div className="observation-card__reopen-info">
                    <div className="reopen-request-details">
                      <strong>Reopen Requested</strong>
                      <div className="reopen-reason">
                        <strong>Reason:</strong> {observation.reopen_reason}
                      </div>
                      <div className="reopen-meta">
                        Requested on {new Date(observation.reopen_requested_at).toLocaleString()}
                      </div>
                      {canApproveReopen(observation) && (
                        <div className="reopen-actions">
                          <button
                            onClick={() => handleApproveReopen(observation.id)}
                            disabled={approvingReopen === observation.id || denyingReopen === observation.id}
                            className="btn btn-primary btn-sm"
                          >
                            {approvingReopen === observation.id ? 'Approving...' : 'Approve'}
                          </button>
                          <button
                            onClick={() => handleDenyReopenClick(observation)}
                            disabled={approvingReopen === observation.id || denyingReopen === observation.id}
                            className="btn btn-danger btn-sm"
                          >
                            {denyingReopen === observation.id ? 'Denying...' : 'Deny'}
                          </button>
                        </div>
                      )}
                      {!canApproveReopen(observation) && (
                        <div className="reopen-notice">
                          <small>Cannot approve your own verification/rejection</small>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                <div className="observation-card__footer">
                  <div className="observation-card__date">
                    Submitted: {new Date(observation.submission_date).toLocaleString()}
                  </div>
                  <div className="observation-card__actions">
                    {getStatusBadge(observation.status, observation)}
                    {observation.status.toLowerCase() === 'pending' && (
                      <>
                        <button
                          onClick={() => handleVerify(observation.id)}
                          disabled={verifying === observation.id || rejecting === observation.id}
                          className="btn btn-primary"
                        >
                          {verifying === observation.id ? 'Verifying...' : 'Verify'}
                        </button>
                        <button
                          onClick={() => handleRejectClick(observation)}
                          disabled={verifying === observation.id || rejecting === observation.id}
                          className="btn btn-danger"
                        >
                          {rejecting === observation.id ? 'Rejecting...' : 'Reject'}
                        </button>
                      </>
                    )}
                    {(observation.status.toLowerCase() === 'verified' || observation.status.toLowerCase() === 'rejected') && 
                     !observation.reopen_requested_at && (
                      <button
                        onClick={() => handleReopenRequestClick(observation)}
                        disabled={requestingReopen === observation.id}
                        className="btn btn-secondary"
                      >
                        {requestingReopen === observation.id ? 'Requesting...' : 'Request Reopen'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )
          })}
        </div>
      )}

      {/* Rejection Reason Modal */}
      {showRejectModal && (
        <div className="modal-overlay" onClick={handleRejectCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {bulkAction === 'reject' 
                  ? `Reject ${selectedObservations.size} KPI Submission${selectedObservations.size !== 1 ? 's' : ''}`
                  : `Reject KPI Submission`}
              </h3>
              <button onClick={handleRejectCancel} className="modal-close">×</button>
            </div>
            <div className="modal-body">
              <p className="modal-description">
                {bulkAction === 'reject'
                  ? `Please provide a reason for rejecting ${selectedObservations.size} KPI submission${selectedObservations.size !== 1 ? 's' : ''}.`
                  : `Please provide a reason for rejecting this KPI submission from ${selectedObservation?.department_name}.`
                }
              </p>
              <div className="form-group">
                <label htmlFor="rejection-reason">Rejection Reason *</label>
                <textarea
                  id="rejection-reason"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="Explain why this submission is being rejected..."
                  rows={4}
                  className="input-field textarea"
                  disabled={rejecting !== null}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                onClick={handleRejectCancel}
                disabled={rejecting !== null}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={bulkAction === 'reject' ? handleBulkRejectSubmit : handleRejectSubmit}
                disabled={rejecting !== null || !rejectionReason.trim()}
                className="btn btn-danger"
              >
                {rejecting ? 'Rejecting...' : 'Reject Submission'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reopen Request Modal */}
      {showReopenModal && (
        <div className="modal-overlay" onClick={handleReopenRequestCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Request Reopen</h3>
              <button onClick={handleReopenRequestCancel} className="modal-close">×</button>
            </div>
            <div className="modal-body">
              <p className="modal-description">
                Please provide a reason for requesting to reopen this KPI submission from {selectedObservation?.department_name}.
                This will require Admin/SuperAdmin approval.
              </p>
              <div className="form-group">
                <label htmlFor="reopen-reason">Reopen Reason *</label>
                <textarea
                  id="reopen-reason"
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                  placeholder="Explain why this submission needs to be reopened..."
                  rows={4}
                  className="input-field textarea"
                  disabled={requestingReopen !== null}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                onClick={handleReopenRequestCancel}
                disabled={requestingReopen !== null}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleReopenRequestSubmit}
                disabled={requestingReopen !== null || !reopenReason.trim()}
                className="btn btn-primary"
              >
                {requestingReopen ? 'Requesting...' : 'Request Reopen'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deny Reopen Modal */}
      {showDenyReopenModal && (
        <div className="modal-overlay" onClick={handleDenyReopenCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Deny Reopen Request</h3>
              <button onClick={handleDenyReopenCancel} className="modal-close">×</button>
            </div>
            <div className="modal-body">
              <p className="modal-description">
                Please provide a reason for denying the reopen request from {selectedObservation?.department_name}.
              </p>
              <div className="form-group">
                <label htmlFor="deny-reopen-reason">Denial Reason *</label>
                <textarea
                  id="deny-reopen-reason"
                  value={denyReopenReason}
                  onChange={(e) => setDenyReopenReason(e.target.value)}
                  placeholder="Explain why this reopen request is being denied..."
                  rows={4}
                  className="input-field textarea"
                  disabled={denyingReopen !== null}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                onClick={handleDenyReopenCancel}
                disabled={denyingReopen !== null}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleDenyReopenSubmit}
                disabled={denyingReopen !== null || !denyReopenReason.trim()}
                className="btn btn-danger"
              >
                {denyingReopen ? 'Denying...' : 'Deny Request'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
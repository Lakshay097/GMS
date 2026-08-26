import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

interface ApprovalRequest {
  id: string
  user_id: string
  full_name: string
  email: string
  school_id: string
  school_name: string
  school_code: string
  requested_department_id: string
  requested_department_name: string
  requested_department_code: string
  requested_at: string
}

export default function ApprovalList() {
  const [requests, setRequests] = useState<ApprovalRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [rejectionDialog, setRejectionDialog] = useState<{ userId: string, departmentId: string } | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    loadRequests(controller.signal)
    return () => controller.abort()
  }, [])

  const loadRequests = async (signal?: AbortSignal) => {
    try {
      const response = await apiFetch('/api/v1/approvals/pending', { signal })
      if (response.ok) {
        const data = await response.json()
        setRequests(data.data || [])
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (userId: string, departmentId: string) => {
    try {
      const response = await apiFetch(`/api/v1/approvals/${userId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ department_id: departmentId })
      })
      if (response.ok) {
        loadRequests()
      }
    } catch (err) {
      console.error('Failed to approve request:', err)
    }
  }

  const handleReject = async () => {
    if (!rejectionDialog) return

    try {
      const response = await apiFetch(`/api/v1/approvals/${rejectionDialog.userId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          department_id: rejectionDialog.departmentId,
          rejection_reason: rejectionReason
        })
      })
      if (response.ok) {
        setRejectionDialog(null)
        setRejectionReason('')
        loadRequests()
      }
    } catch (err) {
      console.error('Failed to reject request:', err)
    }
  }

  if (loading) {
    return <div className="page-shell">Loading...</div>
  }

  if (requests.length === 0) {
    return (
      <div className="page-shell">
        <div className="header">
          <h1>Approvals</h1>
        </div>
        <div className="empty-state">
          <p>No pending requests</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell">
      <div className="header">
        <h1>Approvals</h1>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th></th>
              <th>Name</th>
              <th>Email</th>
              <th>School</th>
              <th>Requested Department</th>
              <th>Requested</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((request) => (
              <React.Fragment key={request.id}>
                <tr className={expandedRow === request.id ? 'expanded' : ''}>
                  <td>
                    <button
                      onClick={() => setExpandedRow(expandedRow === request.id ? null : request.id)}
                      className="expand-btn"
                      aria-label="Expand row"
                    >
                      {expandedRow === request.id ? '▼' : '▶'}
                    </button>
                  </td>
                  <td>
                    <Link to={`/users/${request.user_id}`} className="name-link">
                      {request.full_name}
                    </Link>
                  </td>
                  <td>{request.email}</td>
                  <td>
                    {request.school_name}
                    <span className="detail-sublabel">{request.school_code}</span>
                  </td>
                  <td>
                    {request.requested_department_name}
                    <span className="detail-sublabel">{request.requested_department_code}</span>
                  </td>
                  <td>{new Date(request.requested_at).toLocaleDateString()}</td>
                  <td>
                    <div className="action-buttons">
                      <button
                        onClick={() => handleApprove(request.user_id, request.requested_department_id)}
                        className="icon-btn icon-btn-primary"
                        title="Approve request"
                      >
                        ✓
                      </button>
                      <button
                        onClick={() => setRejectionDialog({ userId: request.user_id, departmentId: request.requested_department_id })}
                        className="icon-btn icon-btn-ghost"
                        title="Reject request"
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedRow === request.id && (
                  <tr className="expanded-row">
                    <td colSpan={7}>
                      <div className="expanded-content">
                        <div className="expanded-details">
                          <div className="detail-group">
                            <span className="detail-label">School Code:</span>
                            <span className="detail-value">{request.school_code}</span>
                          </div>
                          <div className="detail-group">
                            <span className="detail-label">Department Code:</span>
                            <span className="detail-value">{request.requested_department_code}</span>
                          </div>
                          <div className="detail-group">
                            <span className="detail-label">Requested On:</span>
                            <span className="detail-value">{new Date(request.requested_at).toLocaleString()}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Rejection Dialog */}
      {rejectionDialog && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h2>Reject Request</h2>
              <button
                onClick={() => {
                  setRejectionDialog(null)
                  setRejectionReason('')
                }}
                className="icon-btn"
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to reject this department request?</p>
              <div className="form-group">
                <label htmlFor="rejectionReason">Rejection Reason (Optional)</label>
                <textarea
                  id="rejectionReason"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="Explain why this request was rejected"
                  rows={3}
                  className="form-input"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                onClick={() => {
                  setRejectionDialog(null)
                  setRejectionReason('')
                }}
                className="btn btn-ghost"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                className="btn btn-danger"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

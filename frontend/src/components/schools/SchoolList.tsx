import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import RoleGuard from '../common/RoleGuard'
import { getPermissions } from '../../lib/permissions'
import { useUser } from '@clerk/clerk-react'


interface School {
  id: string
  name: string
  code: string
  status: string
  address?: string
  contact_email?: string
  contact_phone?: string
  created_at: string
  deactivated_at?: string
}

interface SchoolListResponse {
  data: School[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}

type SortField = 'name' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

export default function SchoolList() {
  const [allSchools, setAllSchools] = useState<School[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [expandedSchools, setExpandedSchools] = useState<Record<string, boolean>>({})
  const [sortField, setSortField] = useState<SortField>('name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [pendingDeactivateId, setPendingDeactivateId] = useState<string | null>(null)
  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  useEffect(() => {
    fetchAllSchools()
  }, [])

  useEffect(() => {
    if (!banner) return
    const timer = setTimeout(() => setBanner(null), 5000)
    return () => clearTimeout(timer)
  }, [banner])

  const fetchAllSchools = async () => {
    try {
      setLoading(true)
      const response = await apiFetch('/api/v1/schools?page=1&page_size=200')
      
      if (!response.ok) {
        const errBody = await response.json().catch(() => null)
        throw new Error(errBody?.error?.message || 'Failed to fetch schools')
      }
      
      const data: SchoolListResponse = await response.json()
      setAllSchools(data.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const handleDeactivate = async (schoolId: string) => {
    setPendingDeactivateId(null)
    setAllSchools(prev => prev.map(s => s.id === schoolId ? { ...s, status: 'inactive' } : s))
    try {
      const response = await apiFetch(`/api/v1/schools/${schoolId}/deactivate`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        const errData = await response.json().catch(() => null)
        throw new Error(errData?.error?.message || 'Failed to deactivate school')
      }
      
      setBanner({ type: 'success', message: 'School deactivated' })
    } catch (err) {
      setAllSchools(prev => prev.map(s => s.id === schoolId ? { ...s, status: 'active' } : s))
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to deactivate school' })
    }
  }

  const toggleSchoolExpand = (schoolId: string) => {
    setExpandedSchools(prev => ({ ...prev, [schoolId]: !prev[schoolId] }))
  }

  // Client-side sort + paginate
  const sortedSchools = [...allSchools].sort((a, b) => {
    const aVal = a[sortField] ?? ''
    const bVal = b[sortField] ?? ''
    const cmp = String(aVal).localeCompare(String(bVal))
    return sortDirection === 'asc' ? cmp : -cmp
  })

  const PAGE_SIZE = 20
  const total = sortedSchools.length
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const pagedSchools = sortedSchools.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (loading) return <div className="loading-state">Loading schools…</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="school-list page-shell">
      <div className="header">
        <h1>Schools</h1>
        <RoleGuard requires={{ canCreate: true }}>
          <Link to="/schools/new" className="btn btn-primary">
            + Create School
          </Link>
        </RoleGuard>
      </div>

      {banner && (
        <div className={`alert alert-${banner.type}`}>
          <span className="alert-icon">{banner.type === 'error' ? '⚠️' : '✓'}</span>
          <span>{banner.message}</span>
          <button onClick={() => setBanner(null)} className="alert-close">×</button>
        </div>
      )}
      
      {/* Desktop/Tablet Table */}
      <div className="table-wrap">
        <table className="data-table schools-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('name')}>
                School Name
                {sortField === 'name' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th>Code</th>
              <th className="sortable" onClick={() => handleSort('status')}>
                Status
                {sortField === 'status' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th className="expandable-column">Contact Email</th>
              <th className="expandable-column">Contact Phone</th>
              <th className="sortable expandable-column" onClick={() => handleSort('created_at')}>
                Created
                {sortField === 'created_at' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {pagedSchools.map((school) => {
              const isExpanded = expandedSchools[school.id]
              return (
                <React.Fragment key={school.id}>
                  <tr className="school-row">
                    <td>
                      <button 
                        className="expand-btn"
                        onClick={() => toggleSchoolExpand(school.id)}
                        aria-label="Expand row"
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                      <Link to={`/schools/${school.id}/edit`} className="school-name-link">
                        <span className="school-icon">🏫</span>
                        {school.name}
                      </Link>
                    </td>
                    <td>
                      <span className="code-badge">{school.code}</span>
                    </td>
                    <td>
                      <span className={`status status-${school.status}`}>
                        {school.status}
                      </span>
                    </td>
                    <td className="expandable-column">{school.contact_email || '—'}</td>
                    <td className="expandable-column">{school.contact_phone || '—'}</td>
                    <td className="expandable-column">
                      {new Date(school.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <RoleGuard requires={{ canEdit: true }} fallback={null}>
                        <div className="action-buttons">
                          <Link 
                            to={`/schools/${school.id}/edit`} 
                            className="icon-btn"
                            title="Edit school"
                          >
                            ✏️
                          </Link>
                          <RoleGuard requires={{ canDelete: true }}>
                            {school.status === 'active' && (
                              pendingDeactivateId === school.id ? (
                                <span className="inline-confirm">
                                  <span className="inline-confirm__text">Deactivate?</span>
                                  <button className="btn btn-sm btn-danger" onClick={() => handleDeactivate(school.id)}>Yes</button>
                                  <button className="btn btn-sm btn-ghost" onClick={() => setPendingDeactivateId(null)}>No</button>
                                </span>
                              ) : (
                                <button 
                                  onClick={() => setPendingDeactivateId(school.id)}
                                  className="icon-btn icon-btn-danger"
                                  title="Deactivate school"
                                >
                                  ⏻
                                </button>
                              )
                            )}
                          </RoleGuard>
                        </div>
                      </RoleGuard>
                    </td>
                  </tr>
                  
                  {isExpanded && (
                    <tr className="expanded-row">
                      <td colSpan={7}>
                        <div className="expanded-content">
                          <div className="expanded-details">
                            <div className="detail-group">
                              <span className="detail-label">Address:</span>
                              <span className="detail-value">{school.address || 'Not provided'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Contact Email:</span>
                              <span className="detail-value">{school.contact_email || 'Not provided'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Contact Phone:</span>
                              <span className="detail-value">{school.contact_phone || 'Not provided'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Created:</span>
                              <span className="detail-value">{new Date(school.created_at).toLocaleDateString()}</span>
                            </div>
                            {school.deactivated_at && (
                              <div className="detail-group">
                                <span className="detail-label">Deactivated:</span>
                                <span className="detail-value">{new Date(school.deactivated_at).toLocaleDateString()}</span>
                              </div>
                            )}
                          </div>
                          <div className="expanded-actions">
                            <Link to={`/schools/${school.id}/edit`} className="btn btn-sm btn-primary">
                              ✏️ Edit School
                            </Link>
                            {school.status === 'active' && (
                              pendingDeactivateId === school.id ? (
                                <span className="inline-confirm">
                                  <span className="inline-confirm__text">Deactivate this school?</span>
                                  <button className="btn btn-sm btn-danger" onClick={() => handleDeactivate(school.id)}>Yes, deactivate</button>
                                  <button className="btn btn-sm btn-ghost" onClick={() => setPendingDeactivateId(null)}>Cancel</button>
                                </span>
                              ) : (
                                <button 
                                  onClick={() => setPendingDeactivateId(school.id)}
                                  className="btn btn-sm btn-danger"
                                >
                                  ⏻ Deactivate
                                </button>
                              )
                            )}
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
      
      {/* Mobile Cards */}
      <div className="school-cards-mobile">
        {pagedSchools.map((school) => {
          const isExpanded = expandedSchools[school.id]
          return (
            <div 
              key={school.id} 
              className={`school-card ${isExpanded ? 'expanded' : ''}`}
              onClick={() => toggleSchoolExpand(school.id)}
            >
              <div className="school-card-header">
                <span className="school-card-icon">🏫</span>
                <div className="school-card-info">
                  <div className="school-card-name">{school.name}</div>
                  <div className="school-card-meta">
                    <span className="school-card-code">{school.code}</span>
                    <span className={`school-card-status status-${school.status}`}>
                      {school.status}
                    </span>
                  </div>
                </div>
                {isExpanded ? '▼' : '▶'}
              </div>
              
              {isExpanded && (
                <div className="school-card-body">
                  <div className="school-card-details">
                    <div className="school-card-detail">
                      <span className="school-card-detail-label">Contact Email</span>
                      <span className="school-card-detail-value">{school.contact_email || 'Not provided'}</span>
                    </div>
                    <div className="school-card-detail">
                      <span className="school-card-detail-label">Contact Phone</span>
                      <span className="school-card-detail-value">{school.contact_phone || 'Not provided'}</span>
                    </div>
                    <div className="school-card-detail">
                      <span className="school-card-detail-label">Address</span>
                      <span className="school-card-detail-value">{school.address || 'Not provided'}</span>
                    </div>
                    <div className="school-card-detail">
                      <span className="school-card-detail-label">Created</span>
                      <span className="school-card-detail-value">{new Date(school.created_at).toLocaleDateString()}</span>
                    </div>
                    {school.deactivated_at && (
                      <div className="school-card-detail">
                        <span className="school-card-detail-label">Deactivated</span>
                        <span className="school-card-detail-value">{new Date(school.deactivated_at).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                  <div className="school-card-actions">
                    <Link
                      to={`/schools/${school.id}/edit`}
                      className="btn btn-sm btn-primary"
                      onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                      ✏️ Edit School
                    </Link>
                    {school.status === 'active' && (
                      pendingDeactivateId === school.id ? (
                        <span className="inline-confirm">
                          <span className="inline-confirm__text">Deactivate?</span>
                          <button className="btn btn-sm btn-danger" onClick={(e) => { e.stopPropagation(); handleDeactivate(school.id) }}>Yes</button>
                          <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); setPendingDeactivateId(null) }}>No</button>
                        </span>
                      ) : (
                        <button 
                          onClick={(e) => {
                            e.stopPropagation()
                            setPendingDeactivateId(school.id)
                          }}
                          className="btn btn-sm btn-danger"
                        >
                          ⏻ Deactivate
                        </button>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
      
      <div className="pagination">
        <button 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className="btn btn-sm"
        >
          Previous
        </button>
        <span className="pagination-info">
          {total > 0 ? `${(page - 1) * 50 + 1}–${Math.min(page * 50, total)} of ${total}` : '0 of 0'}
        </span>
        <button 
          onClick={() => setPage(p => p + 1)}
          disabled={page >= totalPages}
          className="btn btn-sm"
        >
          Next
        </button>
      </div>
    </div>
  )
}
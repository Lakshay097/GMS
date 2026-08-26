import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import React from 'react'
import { apiFetch } from '../../lib/api'
import RoleGuard from '../common/RoleGuard'

interface Department {
  id: string
  school_id: string
  school_name?: string
  school_code?: string
  name: string
  code: string
  status: string
  description?: string
  head_user_id?: string
  created_at: string
  archived_at?: string
}

interface DepartmentListResponse {
  data: Department[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}

interface School {
  id: string
  name: string
  code: string
}

type SortField = 'name' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

export default function DepartmentList() {
  const [allDepartments, setAllDepartments] = useState<Department[]>([])
  const [schools, setSchools] = useState<School[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSchool, setSelectedSchool] = useState<string>('all')
  const [sortField, setSortField] = useState<SortField>('name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [expandedDepartments, setExpandedDepartments] = useState<Record<string, boolean>>({})
  const [showArchived, setShowArchived] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    const load = async () => {
      try {
        setLoading(true)
        const [schoolRes, deptRes] = await Promise.all([
          apiFetch('/api/v1/schools?page=1&page_size=200', { signal }),
          apiFetch('/api/v1/departments?page=1&page_size=200', { signal }),
        ])

        if (schoolRes.ok) {
          const schoolData = await schoolRes.json()
          setSchools(schoolData.data)
        }

        if (!deptRes.ok) {
          throw new Error('Failed to fetch departments')
        }
        const deptData: DepartmentListResponse = await deptRes.json()
        setAllDepartments(deptData.data)
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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const [pendingDeactivateId, setPendingDeactivateId] = useState<string | null>(null)
  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  useEffect(() => {
    if (!banner) return
    const timer = setTimeout(() => setBanner(null), 5000)
    return () => clearTimeout(timer)
  }, [banner])

  const handleDeactivate = async (departmentId: string) => {
    setPendingDeactivateId(null)
    setAllDepartments(prev => prev.map(d => d.id === departmentId ? { ...d, status: 'inactive' as any } : d))
    try {
      const response = await apiFetch(`/api/v1/departments/${departmentId}/deactivate`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to deactivate department')
      }
      
      setBanner({ type: 'success', message: 'Department deactivated' })
    } catch (err) {
      setAllDepartments(prev => prev.map(d => d.id === departmentId ? { ...d, status: 'active' as any } : d))
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to deactivate department' })
    }
  }

  const toggleDepartmentExpand = (departmentId: string) => {
    setExpandedDepartments(prev => ({ ...prev, [departmentId]: !prev[departmentId] }))
  }

  // Client-side filter: school, archived, then sort
  const departments = allDepartments.filter(d => {
    if (selectedSchool !== 'all' && d.school_id !== selectedSchool) return false
    if (!showArchived && d.archived_at) return false
    return true
  })

  const visibleDepartments = [...departments].sort((a, b) => {
    const aVal = a[sortField] ?? ''
    const bVal = b[sortField] ?? ''
    const cmp = String(aVal).localeCompare(String(bVal))
    return sortDirection === 'asc' ? cmp : -cmp
  })

  if (loading) return <div className="loading-state">Loading departments…</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="department-list page-shell">
      <div className="header">
        <h1>Departments</h1>
        <RoleGuard requires={{ canCreate: true }}>
          <Link to="/departments/new" className="btn btn-primary">
            + Create Department
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
      
      {/* Filter Control */}
      <div className="filter-row">
        <label htmlFor="school-filter">Filter by School:</label>
        <select
          id="school-filter"
          value={selectedSchool}
          onChange={(e) => setSelectedSchool(e.target.value)}
          className="form-input filter-select"
        >
          <option value="all">All Schools</option>
          {schools.map(school => (
            <option key={school.id} value={school.id}>
              {school.name} ({school.code})
            </option>
          ))}
        </select>
        <label className="toggle-label" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-small)', color: 'var(--ink-500)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
            style={{ accentColor: 'var(--gold-600)' }}
          />
          <span>Show deactivated</span>
        </label>
      </div>

      {/* Desktop/Tablet Table */}
      <div className="table-wrap">
        <table className="data-table departments-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('name')}>
                Name
                {sortField === 'name' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th>Code</th>
              <th>School</th>
              <th className="sortable" onClick={() => handleSort('status')}>
                Status
                {sortField === 'status' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th className="expandable-column">Description</th>
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
            {            visibleDepartments.map((dept) => {
              const isExpanded = expandedDepartments[dept.id]
              return (
                <React.Fragment key={dept.id}>
                  <tr className="department-row">
                    <td>
                      <button 
                        className="expand-btn"
                        onClick={() => toggleDepartmentExpand(dept.id)}
                        aria-label="Expand row"
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                      <Link to={`/departments/${dept.id}/edit`} className="department-name-link">
                        {dept.name}
                      </Link>
                    </td>
                    <td>
                      <span className="code-badge">{dept.code}</span>
                    </td>
                    <td>
                      <span className="school-name">{dept.school_name || dept.school_code || '—'}</span>
                    </td>
                    <td>
                      <span className={`status status-${dept.status}`}>
                        {dept.status}
                      </span>
                    </td>
                    <td className="expandable-column">
                      <span className="description-text">
                        {dept.description ? (dept.description.length > 50 ? dept.description.substring(0, 50) + '...' : dept.description) : '—'}
                      </span>
                    </td>
                    <td className="expandable-column">
                      {new Date(dept.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <RoleGuard requires={{ canEdit: true }} fallback={null}>
                        <div className="action-buttons">
                          <Link 
                            to={`/departments/${dept.id}/edit`} 
                            className="icon-btn"
                            title="Edit department"
                          >
                            ✏️
                          </Link>
                          <RoleGuard requires={{ canDelete: true }}>
                            {dept.status === 'active' && (
                              pendingDeactivateId === dept.id ? (
                                <span className="inline-confirm">
                                  <span className="inline-confirm__text">Deactivate?</span>
                                  <button className="btn btn-sm btn-danger" onClick={() => handleDeactivate(dept.id)}>Yes</button>
                                  <button className="btn btn-sm btn-ghost" onClick={() => setPendingDeactivateId(null)}>No</button>
                                </span>
                              ) : (
                                <button 
                                  onClick={() => setPendingDeactivateId(dept.id)}
                                  className="icon-btn icon-btn-danger"
                                  title="Deactivate department"
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
                              <span className="detail-label">Full Description:</span>
                              <span className="detail-value">{dept.description || 'Not provided'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">School:</span>
                              <span className="detail-value">{dept.school_name || dept.school_code || 'Not assigned'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Created:</span>
                              <span className="detail-value">{new Date(dept.created_at).toLocaleDateString()}</span>
                            </div>
                            {dept.archived_at && (
                              <div className="detail-group">
                                <span className="detail-label">Deactivated:</span>
                                <span className="detail-value">{new Date(dept.archived_at).toLocaleDateString()}</span>
                              </div>
                            )}
                          </div>
                          <div className="expanded-actions">
                            <Link to={`/departments/${dept.id}/edit`} className="btn btn-sm btn-primary">
                              ✏️ Edit Department
                            </Link>
                            {dept.status === 'active' && (
                              pendingDeactivateId === dept.id ? (
                                <span className="inline-confirm">
                                  <span className="inline-confirm__text">Deactivate this department?</span>
                                  <button className="btn btn-sm btn-danger" onClick={() => handleDeactivate(dept.id)}>Yes</button>
                                  <button className="btn btn-sm btn-ghost" onClick={() => setPendingDeactivateId(null)}>No</button>
                                </span>
                              ) : (
                                <button 
                                  onClick={() => setPendingDeactivateId(dept.id)}
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
      <div className="department-cards-mobile">
        {            visibleDepartments.map((dept) => {
          const isExpanded = expandedDepartments[dept.id]
          return (
            <div 
              key={dept.id} 
              className={`department-card ${isExpanded ? 'expanded' : ''}`}
              onClick={() => toggleDepartmentExpand(dept.id)}
            >
              <div className="department-card-header">
                <div className="department-card-info">
                  <div className="department-card-name">{dept.name}</div>
                  <div className="department-card-subtitle">{dept.school_name || dept.school_code || '—'}</div>
                  <div className="department-card-meta">
                    <span className="department-card-code">{dept.code}</span>
                    <span className={`department-card-status status-${dept.status}`}>
                      {dept.status}
                    </span>
                  </div>
                </div>
                {isExpanded ? '▼' : '▶'}
              </div>
              
              {isExpanded && (
                <div className="department-card-body">
                  <div className="department-card-details">
                    <div className="department-card-detail">
                      <span className="department-card-detail-label">Description</span>
                      <span className="department-card-detail-value">{dept.description || 'Not provided'}</span>
                    </div>
                    <div className="department-card-detail">
                      <span className="department-card-detail-label">School</span>
                      <span className="department-card-detail-value">{dept.school_name || dept.school_code || 'Not assigned'}</span>
                    </div>
                    <div className="department-card-detail">
                      <span className="department-card-detail-label">Created</span>
                      <span className="department-card-detail-value">{new Date(dept.created_at).toLocaleDateString()}</span>
                    </div>
                    {dept.archived_at && (
                      <div className="department-card-detail">
                        <span className="department-card-detail-label">Deactivated</span>
                        <span className="department-card-detail-value">{new Date(dept.archived_at).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                  <div className="department-card-actions">
                    <Link 
                      to={`/departments/${dept.id}/edit`} 
                      className="btn btn-sm btn-primary"
                      onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                      ✏️ Edit Department
                    </Link>
                    {dept.status === 'active' && (
                      pendingDeactivateId === dept.id ? (
                        <span className="inline-confirm">
                          <span className="inline-confirm__text">Deactivate?</span>
                          <button className="btn btn-sm btn-danger" onClick={(e) => { e.stopPropagation(); handleDeactivate(dept.id) }}>Yes</button>
                          <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); setPendingDeactivateId(null) }}>No</button>
                        </span>
                      ) : (
                        <button 
                          onClick={(e) => {
                            e.stopPropagation()
                            setPendingDeactivateId(dept.id)
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
        <span className="pagination-info">
          {visibleDepartments.length > 0 ? `${visibleDepartments.length} departments` : '0 departments'}
        </span>
      </div>
    </div>
  )
}
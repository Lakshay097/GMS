import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'

interface User {
  id: string
  clerk_user_id: string
  email: string
  full_name: string
  school_id?: string
  school_name?: string
  department_id?: string
  department_name?: string
  requested_department_id?: string
  requested_department_name?: string
  department_request_status?: 'none' | 'pending' | 'approved' | 'rejected'
  status: string
  roles: string[]
  mfa_enabled: boolean
  phone?: string
  employee_id?: string
  created_at: string
  archived_at?: string
}

interface School {
  id: string
  name: string
  code: string
}

interface Department {
  id: string
  name: string
  code: string
}

interface UserListResponse {
  data: User[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}

type SortField = 'full_name' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

export default function UserList() {
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const [expandedUsers, setExpandedUsers] = useState<Record<string, boolean>>({})
  const [sortField, setSortField] = useState<SortField>('full_name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [selectedSchool, setSelectedSchool] = useState<string>('')
  const [selectedDepartment, setSelectedDepartment] = useState<string>('')
  const [schools, setSchools] = useState<School[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [schoolsLoading, setSchoolsLoading] = useState(false)
  const [departmentsLoading, setDepartmentsLoading] = useState(false)
  const [pendingArchiveId, setPendingArchiveId] = useState<string | null>(null)
  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  useEffect(() => {
    fetchSchools()
    fetchDepartments()
    fetchAllUsers()
  }, [])

  const fetchSchools = async () => {
    try {
      setSchoolsLoading(true)
      const response = await apiFetch('/api/v1/schools?page=1&page_size=200')
      if (response.ok) {
        const data = await response.json()
        setSchools(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch schools:', err)
    } finally {
      setSchoolsLoading(false)
    }
  }

  const fetchDepartments = async () => {
    try {
      setDepartmentsLoading(true)
      const response = await apiFetch('/api/v1/departments?page=1&page_size=200')
      if (response.ok) {
        const data = await response.json()
        setDepartments(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch departments:', err)
    } finally {
      setDepartmentsLoading(false)
    }
  }

  // Auto-dismiss banner after 5s
  useEffect(() => {
    if (!banner) return
    const timer = setTimeout(() => setBanner(null), 5000)
    return () => clearTimeout(timer)
  }, [banner])

  const fetchAllUsers = async () => {
    try {
      setLoading(true)
      const response = await apiFetch('/api/v1/users?page=1&page_size=200')
      
      if (!response.ok) {
        const errBody = await response.json().catch(() => null)
        throw new Error(errBody?.error?.message || 'Failed to fetch users')
      }
      
      const data: UserListResponse = await response.json()
      setAllUsers(data.data)
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

  const handleArchive = async (userId: string) => {
    setPendingArchiveId(null)
    // Optimistic: immediately mark as archived in UI
    setAllUsers(prev => prev.map(u => u.id === userId ? { ...u, status: 'archived' } : u))
    try {
      const response = await apiFetch(`/api/v1/users/${userId}/archive`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to archive user')
      }
      
      setBanner({ type: 'success', message: 'User archived successfully' })
    } catch (err) {
      // Revert optimistic update on failure
      setAllUsers(prev => prev.map(u => u.id === userId ? { ...u, status: 'active' } : u))
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to archive user' })
    }
  }

  const toggleUserExpand = (userId: string) => {
    setExpandedUsers(prev => ({ ...prev, [userId]: !prev[userId] }))
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('')
  }

  const renderRoles = (roles: string[], maxVisible: number = 3) => {
    if (roles.length === 0) return <span className="text-ink-300">—</span>
    
    const visibleRoles = roles.slice(0, maxVisible)
    const remainingCount = roles.length - maxVisible
    
    return (
      <div className="role-badges">
        {visibleRoles.map((role, idx) => (
          <span key={idx} className="role-badge">{role}</span>
        ))}
        {remainingCount > 0 && (
          <span className="role-badge role-badge--more">+{remainingCount} more</span>
        )}
      </div>
    )
  }

  // Client-side filter + sort
  const users = allUsers.filter(u => {
    if (selectedSchool && u.school_id !== selectedSchool) return false
    if (selectedDepartment && u.department_id !== selectedDepartment) return false
    return true
  })

  const sortedUsers = [...users].sort((a, b) => {
    const aVal = a[sortField] ?? ''
    const bVal = b[sortField] ?? ''
    const cmp = String(aVal).localeCompare(String(bVal))
    return sortDirection === 'asc' ? cmp : -cmp
  })

  const total = sortedUsers.length
  const PAGE_SIZE = 20
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const pagedUsers = sortedUsers.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (loading) return <div className="loading-state">Loading users…</div>
  if (error) return <div className="error">Error: {error}</div>

  const schoolOptions = schools.map(school => ({
    value: school.id,
    label: school.name,
    sublabel: school.code
  }))

  const departmentOptions = departments.map(dept => ({
    value: dept.id,
    label: dept.name,
    sublabel: dept.code
  }))

  return (
    <div className="user-list page-shell">
      <div className="header">
        <h1>Users</h1>
        <Link to="/users/new" className="btn btn-primary">
          + Create User
        </Link>
      </div>

      {/* Banner (auto-dismiss after 5s) */}
      {banner && (
        <div className={`alert alert-${banner.type}`}>
          <span className="alert-icon">{banner.type === 'error' ? '⚠️' : '✓'}</span>
          <span>{banner.message}</span>
          <button onClick={() => setBanner(null)} className="alert-close">×</button>
        </div>
      )}
      
      {/* Filter Row */}
      <div className="filter-row">
        <div className="filter-group">
          <label htmlFor="school-filter">School</label>
          <SearchableSelect
            id="school-filter"
            name="school-filter"
            value={selectedSchool}
            onChange={setSelectedSchool}
            options={[{ value: '', label: 'All Schools', sublabel: '' }, ...schoolOptions]}
            placeholder="All Schools"
            loading={schoolsLoading}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="department-filter">Department</label>
          <SearchableSelect
            id="department-filter"
            name="department-filter"
            value={selectedDepartment}
            onChange={setSelectedDepartment}
            options={[{ value: '', label: 'All Departments', sublabel: '' }, ...departmentOptions]}
            placeholder="All Departments"
            loading={departmentsLoading}
          />
        </div>
      </div>
      
      {/* Desktop/Tablet Table */}
      <div className="table-wrap desktop-table">
        <table className="data-table users-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('full_name')}>
                Name
                {sortField === 'full_name' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th>Email</th>
              <th>Roles</th>
              <th className="sortable" onClick={() => handleSort('status')}>
                Status
                {sortField === 'status' && (
                  <span className="sort-indicator">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th className="expandable-column sortable" onClick={() => handleSort('created_at')}>
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
            {pagedUsers.map((user) => {
              const isExpanded = expandedUsers[user.id]
              return (
                <React.Fragment key={user.id}>
                  <tr className="user-row">
                    <td>
                      <button 
                        className="expand-btn"
                        onClick={() => toggleUserExpand(user.id)}
                        aria-label="Expand row"
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                      <Link to={`/users/${user.id}/edit`} className="user-name-link">
                        <div className="user-avatar">
                          {getInitials(user.full_name)}
                        </div>
                        <span className="user-name">{user.full_name}</span>
                      </Link>
                    </td>
                    <td className="expandable-column">{user.email}</td>
                    <td>{renderRoles(user.roles)}</td>
                    <td>
                      <span className={`status status-${user.department_request_status === 'pending' ? 'pending' : (user.status === 'archived' ? 'inactive' : user.status)}`}>
                        {user.department_request_status === 'pending' ? 'Pending' : (user.status === 'archived' ? 'Inactive' : user.status.charAt(0).toUpperCase() + user.status.slice(1))}
                      </span>
                    </td>
                    <td className="expandable-column">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <div className="action-buttons">
                        <Link 
                          to={`/users/${user.id}/edit`} 
                          className="icon-btn"
                          title="Edit user"
                        >
                          ✏️
                        </Link>
                        {user.status === 'active' && (
                          pendingArchiveId === user.id ? (
                            <span className="inline-confirm">
                              <span className="inline-confirm__text">Archive?</span>
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => handleArchive(user.id)}
                              >Yes</button>
                              <button
                                className="btn btn-sm btn-ghost"
                                onClick={() => setPendingArchiveId(null)}
                              >No</button>
                            </span>
                          ) : (
                            <button 
                              onClick={() => setPendingArchiveId(user.id)}
                              className="icon-btn icon-btn-danger"
                              title="Deactivate user"
                            >
                              ⏻
                            </button>
                          )
                        )}
                      </div>
                    </td>
                  </tr>
                  
                  {isExpanded && (
                    <tr className="expanded-row">
                      <td colSpan={6}>
                        <div className="expanded-content">
                          <div className="expanded-details">
                            <div className="detail-group">
                              <span className="detail-label">School:</span>
                              <span className="detail-value">{user.school_name || 'Not assigned'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Department:</span>
                              <span className="detail-value">{user.department_name || 'Not assigned'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Email:</span>
                              <span className="detail-value">{user.email}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Phone:</span>
                              <span className="detail-value">{user.phone || 'Not provided'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Employee ID:</span>
                              <span className="detail-value">{user.employee_id || 'Not provided'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">MFA Enabled:</span>
                              <span className="detail-value">{user.mfa_enabled ? 'Yes' : 'No'}</span>
                            </div>
                            <div className="detail-group">
                              <span className="detail-label">Roles:</span>
                              <span className="detail-value">
                                <div className="role-badges role-badges--expanded">
                                  {user.roles.map((role, idx) => (
                                    <span key={idx} className="role-badge">{role}</span>
                                  ))}
                                </div>
                              </span>
                            </div>
                            {user.department_request_status === 'pending' && user.requested_department_name && (
                              <div className="detail-group">
                                <span className="detail-label">Requested:</span>
                                <span className="detail-value">{user.requested_department_name}</span>
                              </div>
                            )}
                            <div className="detail-group">
                              <span className="detail-label">Created:</span>
                              <span className="detail-value">{new Date(user.created_at).toLocaleDateString()}</span>
                            </div>
                            {user.archived_at && (
                              <div className="detail-group">
                                <span className="detail-label">Archived:</span>
                                <span className="detail-value">{new Date(user.archived_at).toLocaleDateString()}</span>
                              </div>
                            )}
                          </div>
                          <div className="expanded-actions">
                            <Link to={`/users/${user.id}/edit`} className="btn btn-sm btn-primary">
                              ✏️ Edit User
                            </Link>
                            {user.status === 'active' && (
                              pendingArchiveId === user.id ? (
                                <span className="inline-confirm">
                                  <span className="inline-confirm__text">Archive this user?</span>
                                  <button
                                    className="btn btn-sm btn-danger"
                                    onClick={() => handleArchive(user.id)}
                                  >Yes, archive</button>
                                  <button
                                    className="btn btn-sm btn-ghost"
                                    onClick={() => setPendingArchiveId(null)}
                                  >Cancel</button>
                                </span>
                              ) : (
                                <button 
                                  onClick={() => setPendingArchiveId(user.id)}
                                  className="btn btn-sm btn-danger"
                                >
                                  📦 Archive
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
      
      {/* Mobile Accordion Cards */}
      <div className="user-list__mobile mobile-cards">
        {pagedUsers.map((user) => {
          const isExpanded = expandedUsers[user.id]
          return (
            <div key={user.id} className="user-card">
              <div 
                className="user-card__header"
                onClick={() => toggleUserExpand(user.id)}
              >
                <div className="user-card__main">
                  <div className="user-avatar">
                    {getInitials(user.full_name)}
                  </div>
                  <div className="user-card__info">
                    <div className="user-card__name">{user.full_name}</div>
                    <span className={`status status-${user.department_request_status === 'pending' ? 'pending' : (user.status === 'archived' ? 'inactive' : user.status)} user-card__status`}>
                      {user.department_request_status === 'pending' ? 'Pending' : (user.status === 'archived' ? 'Inactive' : user.status.charAt(0).toUpperCase() + user.status.slice(1))}
                    </span>
                  </div>
                </div>
                <span className={`user-card__expand ${isExpanded ? 'user-card__expand--open' : ''}`}>
                  ▶
                </span>
              </div>
              
              {isExpanded && (
                <div className="user-card__body">
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">Email:</span>
                    <span className="user-card__detail-value">{user.email}</span>
                  </div>
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">School:</span>
                    <span className="user-card__detail-value">{user.school_name || 'Not assigned'}</span>
                  </div>
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">Department:</span>
                    <span className="user-card__detail-value">{user.department_name || 'Not assigned'}</span>
                  </div>
                  {user.department_request_status === 'pending' && user.requested_department_name && (
                    <div className="user-card__detail">
                      <span className="user-card__detail-label">Requested:</span>
                      <span className="user-card__detail-value">{user.requested_department_name}</span>
                    </div>
                  )}
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">Phone:</span>
                    <span className="user-card__detail-value">{user.phone || 'Not provided'}</span>
                  </div>
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">Employee ID:</span>
                    <span className="user-card__detail-value">{user.employee_id || 'Not provided'}</span>
                  </div>
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">MFA Enabled:</span>
                    <span className="user-card__detail-value">{user.mfa_enabled ? 'Yes' : 'No'}</span>
                  </div>
                  <div className="user-card__detail">
                    <span className="user-card__detail-label">Created:</span>
                    <span className="user-card__detail-value">{new Date(user.created_at).toLocaleDateString()}</span>
                  </div>
                  {user.archived_at && (
                    <div className="user-card__detail">
                      <span className="user-card__detail-label">Archived:</span>
                      <span className="user-card__detail-value">{new Date(user.archived_at).toLocaleDateString()}</span>
                    </div>
                  )}
                  
                  <div className="user-card__roles">
                    <div className="user-card__detail-label">Roles:</div>
                    <div className="role-badges role-badges--expanded">
                      {user.roles.map((role, idx) => (
                        <span key={idx} className="role-badge">{role}</span>
                      ))}
                    </div>
                  </div>
                  
                  <div className="user-card__actions">
                    <Link to={`/users/${user.id}/edit`} className="btn btn-primary">
                      ✏️ Edit User
                    </Link>
                    {user.status === 'active' && (
                      pendingArchiveId === user.id ? (
                        <span className="inline-confirm">
                          <span className="inline-confirm__text">Archive?</span>
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => handleArchive(user.id)}
                          >Yes</button>
                          <button
                            className="btn btn-sm btn-ghost"
                            onClick={() => setPendingArchiveId(null)}
                          >No</button>
                        </span>
                      ) : (
                        <button 
                          onClick={() => setPendingArchiveId(user.id)}
                          className="btn btn-danger"
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
      
      {/* Pagination */}
      <div className="pagination">
        <button 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className="btn btn-sm"
        >
          Previous
        </button>
        <span>Page {page} of {totalPages || 1}</span>
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
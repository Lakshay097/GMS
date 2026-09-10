import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'
import RoleGuard from '../common/RoleGuard'
import SetPasswordModal from './SetPasswordModal'
import BulkImport from './BulkImport'
import InviteCodes from './InviteCodes'
import './UserList.css'

/* ─── Types ────────────────────────────────────────────────────────────────── */

interface User {
  id: string
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

interface School  { id: string; name: string; code: string }
interface Department { id: string; name: string; code: string }

interface UserListResponse {
  data: User[]
  pagination: { page: number; page_size: number; total_count: number; has_next: boolean }
}

type SortField = 'full_name' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

/* ─── Module-level cache ────────────────────────────────────────────────────
 * Stores the last successful fetch so navigating away and back is instant.
 * The cache is intentionally process-lifetime (until hard refresh) — user lists
 * don't change frequently enough to need TTL in this context.  A manual refresh
 * button (or the optimistic archive update) keeps the view accurate.
 * ─────────────────────────────────────────────────────────────────────────── */
let _cachedUsers:       User[]       | null = null
let _cachedSchools:     School[]     | null = null
let _cachedDepartments: Department[] | null = null

/* ─── Helpers ───────────────────────────────────────────────────────────────*/

function getInitials(name: string): string {
  return name.split(' ').map(n => n.charAt(0).toUpperCase()).slice(0, 2).join('')
}

function userStatusLabel(user: User): string {
  if (user.department_request_status === 'pending') return 'Pending'
  if (user.status === 'archived') return 'Inactive'
  return user.status.charAt(0).toUpperCase() + user.status.slice(1)
}

function userStatusClass(user: User): string {
  if (user.department_request_status === 'pending') return 'status status-pending'
  if (user.status === 'archived') return 'status status-inactive'
  return `status status-${user.status}`
}

const ROLE_COLOR: Record<string, string> = {
  superadmin:  'role-badge--superadmin',
  admin:       'role-badge--admin',
  dept_head:   'role-badge--dept-head',
  checker:     'role-badge--checker',
  auditor:     'role-badge--auditor',
  verifier:    'role-badge--verifier',
  viewer:      'role-badge--viewer',
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span className={`role-badge ${ROLE_COLOR[role] ?? ''}`}>
      {role.replace('_', ' ')}
    </span>
  )
}

function RoleBadges({ roles, expanded = false }: { roles: string[]; expanded?: boolean }) {
  const MAX = 3
  if (!roles.length) return <span className="ul-empty-cell">—</span>
  const visible = expanded ? roles : roles.slice(0, MAX)
  const extra   = !expanded && roles.length > MAX ? roles.length - MAX : 0
  return (
    <div className={`role-badges${expanded ? ' role-badges--expanded' : ''}`}>
      {visible.map((r, i) => <RoleBadge key={i} role={r} />)}
      {extra > 0 && <span className="role-badge role-badge--more">+{extra}</span>}
    </div>
  )
}

/* ─── Skeleton row ──────────────────────────────────────────────────────────*/

function SkeletonRows({ count = 8 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i} className="ul-skeleton-row">
          <td>
            <div className="ul-name-cell">
              <span className="ul-skeleton ul-skeleton--avatar" />
              <div className="ul-skeleton-name-wrap">
                <span className="ul-skeleton ul-skeleton--name" style={{ width: `${110 + (i % 4) * 30}px` }} />
                <span className="ul-skeleton ul-skeleton--sub" style={{ width: `${80 + (i % 3) * 20}px` }} />
              </div>
            </div>
          </td>
          <td className="ul-col-email"><span className="ul-skeleton ul-skeleton--text" style={{ width: '140px' }} /></td>
          <td><span className="ul-skeleton ul-skeleton--badge" /></td>
          <td><span className="ul-skeleton ul-skeleton--pill" /></td>
          <td className="ul-col-created"><span className="ul-skeleton ul-skeleton--text" style={{ width: '80px' }} /></td>
          <td><span className="ul-skeleton ul-skeleton--actions" /></td>
        </tr>
      ))}
    </>
  )
}

/* ─── Sort icon ─────────────────────────────────────────────────────────────*/

function SortIcon({ field, active, dir }: { field: string; active: boolean; dir: SortDirection }) {
  return (
    <span className={`ul-sort-icon ${active ? 'ul-sort-icon--active' : ''}`} aria-hidden>
      {active ? (dir === 'asc' ? '↑' : '↓') : '↕'}
    </span>
  )
}

/* ─── Main component ─────────────────────────────────────────────────────── */

export default function UserList() {
  // Seed from cache so returning to the page renders instantly.
  const [allUsers,     setAllUsers]     = useState<User[]>(_cachedUsers ?? [])
  const [schools,      setSchools]      = useState<School[]>(_cachedSchools ?? [])
  const [departments,  setDepartments]  = useState<Department[]>(_cachedDepartments ?? [])

  // loading=true only when we have NO cached data (first visit).
  // Subsequent visits show stale data immediately and refresh silently.
  const [loading,      setLoading]      = useState(_cachedUsers === null)
  const [refreshing,   setRefreshing]   = useState(false)  // background refresh indicator
  const [error,        setError]        = useState<string | null>(null)

  const [page,              setPage]              = useState(1)
  const [expandedUsers,     setExpandedUsers]     = useState<Record<string, boolean>>({})
  const [sortField,         setSortField]         = useState<SortField>('full_name')
  const [sortDirection,     setSortDirection]     = useState<SortDirection>('asc')
  const [selectedSchool,    setSelectedSchool]    = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState('')
  const [pendingArchiveId,  setPendingArchiveId]  = useState<string | null>(null)
  const [passwordModalUser, setPasswordModalUser] = useState<User | null>(null)
  const [showBulkImport,    setShowBulkImport]    = useState(false)
  const [showInvites,       setShowInvites]       = useState(false)
  const [banner,            setBanner]            = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  const isMounted = useRef(true)
  useEffect(() => { isMounted.current = true; return () => { isMounted.current = false } }, [])

  /* ── Data fetch ─────────────────────────────────────────────────────────── */

  const fetchData = useCallback(async (signal: AbortSignal) => {
    try {
      const [schoolRes, deptRes, userRes] = await Promise.all([
        apiFetch('/api/v1/schools?page=1&page_size=200', { signal }),
        apiFetch('/api/v1/departments?page=1&page_size=200', { signal }),
        apiFetch('/api/v1/users?page=1&page_size=200', { signal }),
      ])

      if (!isMounted.current) return

      if (schoolRes.ok) {
        const d = await schoolRes.json()
        const list = d.data ?? []
        _cachedSchools = list
        setSchools(list)
      }
      if (deptRes.ok) {
        const d = await deptRes.json()
        const list = d.data ?? []
        _cachedDepartments = list
        setDepartments(list)
      }
      if (!userRes.ok) {
        const body = await userRes.json().catch(() => null)
        throw new Error(body?.error?.message ?? 'Failed to fetch users')
      }
      const userData: UserListResponse = await userRes.json()
      _cachedUsers = userData.data
      setAllUsers(userData.data)
      setError(null)
    } catch (err) {
      if ((err as DOMException).name === 'AbortError') return
      if (isMounted.current) setError(err instanceof Error ? err.message : 'An error occurred')
    }
  }, [])

  // Initial load (and background refresh when cache already exists)
  useEffect(() => {
    const controller = new AbortController()
    const hasCached = _cachedUsers !== null

    if (hasCached) {
      // Show stale data immediately; refresh silently in background
      setRefreshing(true)
      fetchData(controller.signal).finally(() => {
        if (isMounted.current) setRefreshing(false)
      })
    } else {
      setLoading(true)
      fetchData(controller.signal).finally(() => {
        if (isMounted.current) setLoading(false)
      })
    }

    return () => controller.abort()
  }, [fetchData])

  // Manual refresh callable from the UI
  const handleRefresh = useCallback(async () => {
    const controller = new AbortController()
    setRefreshing(true)
    await fetchData(controller.signal)
    if (isMounted.current) setRefreshing(false)
  }, [fetchData])

  /* ── Banner auto-dismiss ────────────────────────────────────────────────── */

  useEffect(() => {
    if (!banner) return
    const t = setTimeout(() => setBanner(null), 5000)
    return () => clearTimeout(t)
  }, [banner])

  /* ── Filter / sort / page ──────────────────────────────────────────────── */

  // Reset to page 1 whenever filters change
  useEffect(() => { setPage(1) }, [selectedSchool, selectedDepartment])

  const handleSort = (field: SortField) => {
    setSortField(f => {
      if (f === field) { setSortDirection(d => d === 'asc' ? 'desc' : 'asc'); return f }
      setSortDirection('asc')
      return field
    })
    setPage(1)
  }

  const toggleUserExpand = (userId: string) =>
    setExpandedUsers(prev => ({ ...prev, [userId]: !prev[userId] }))

  /* ── Archive ────────────────────────────────────────────────────────────── */

  const handleArchive = async (userId: string) => {
    setPendingArchiveId(null)
    // Optimistic update — keep the row visible as 'archived'
    const patch = (list: User[]) => list.map(u => u.id === userId ? { ...u, status: 'archived' } : u)
    setAllUsers(patch)
    _cachedUsers = _cachedUsers ? patch(_cachedUsers) : null

    try {
      const res = await apiFetch(`/api/v1/users/${userId}/archive`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message ?? 'Failed to archive user')
      }
      setBanner({ type: 'success', message: 'User archived successfully' })
    } catch (err) {
      // Revert
      const revert = (list: User[]) => list.map(u => u.id === userId ? { ...u, status: 'active' } : u)
      setAllUsers(revert)
      _cachedUsers = _cachedUsers ? revert(_cachedUsers) : null
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to archive user' })
    }
  }

  /* ── Derived display data ───────────────────────────────────────────────── */

  const filteredUsers = allUsers.filter(u => {
    if (selectedSchool     && u.school_id     !== selectedSchool)     return false
    if (selectedDepartment && u.department_id !== selectedDepartment) return false
    return true
  })

  const sortedUsers = [...filteredUsers].sort((a, b) => {
    const av = (a[sortField] ?? '') as string
    const bv = (b[sortField] ?? '') as string
    const cmp = av.localeCompare(bv)
    return sortDirection === 'asc' ? cmp : -cmp
  })

  const PAGE_SIZE   = 20
  const total       = sortedUsers.length
  const totalPages  = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const safePage    = Math.min(page, totalPages)
  const pagedUsers  = sortedUsers.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const schoolOptions     = schools.map(s => ({ value: s.id, label: s.name, sublabel: s.code }))
  const departmentOptions = departments.map(d => ({ value: d.id, label: d.name, sublabel: d.code }))

  const isInitialLoad = loading && allUsers.length === 0

  /* ── Render ─────────────────────────────────────────────────────────────── */

  if (error && allUsers.length === 0) {
    return (
      <div className="user-list page-shell">
        <div className="ul-page-header">
          <div className="ul-page-title">
            <span className="eyebrow"><span className="eyebrow__dot" />Users</span>
            <h1>Users</h1>
          </div>
        </div>
        <div className="ul-error-state">
          <span className="ul-error-icon">⚠</span>
          <p>{error}</p>
          <button className="btn btn-ghost btn-sm" onClick={handleRefresh}>Retry</button>
        </div>
      </div>
    )
  }

  return (
    <div className="user-list page-shell">

      {/* ── Page header ───────────────────────────────────────────────────── */}
      <div className="ul-page-header">
        <div className="ul-page-title">
          <span className="eyebrow"><span className="eyebrow__dot" />Administration</span>
          <h1>
            Users
            {refreshing && <span className="ul-refresh-dot" aria-label="Refreshing…" title="Refreshing…" />}
          </h1>
        </div>

        <div className="ul-header-actions">
          <RoleGuard requires={{ canCreate: true }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowInvites(true)}>
              Invite Codes
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowBulkImport(true)}>
              Bulk Import
            </button>
            <Link to="/users/new" className="btn btn-primary">
              + Create User
            </Link>
          </RoleGuard>
        </div>
      </div>

      {/* ── Alert banner ─────────────────────────────────────────────────── */}
      {banner && (
        <div className={`alert alert-${banner.type}`} role="alert">
          <span className="alert-icon">{banner.type === 'error' ? '!' : '✓'}</span>
          <span>{banner.message}</span>
          <button onClick={() => setBanner(null)} className="alert-close" aria-label="Dismiss">×</button>
        </div>
      )}

      {/* ── Filters ──────────────────────────────────────────────────────── */}
      <div className="ul-filter-row">
        <div className="ul-filter-group">
          <label htmlFor="school-filter" className="ul-filter-label">School</label>
          <SearchableSelect
            id="school-filter"
            name="school-filter"
            value={selectedSchool}
            onChange={v => { setSelectedSchool(v); setPage(1) }}
            options={[{ value: '', label: 'All Schools', sublabel: '' }, ...schoolOptions]}
            placeholder="All Schools"
          />
        </div>
        <div className="ul-filter-group">
          <label htmlFor="department-filter" className="ul-filter-label">Department</label>
          <SearchableSelect
            id="department-filter"
            name="department-filter"
            value={selectedDepartment}
            onChange={v => { setSelectedDepartment(v); setPage(1) }}
            options={[{ value: '', label: 'All Departments', sublabel: '' }, ...departmentOptions]}
            placeholder="All Departments"
          />
        </div>
        {!isInitialLoad && (
          <span className="ul-count-badge">
            {total} {total === 1 ? 'user' : 'users'}
          </span>
        )}
      </div>

      {/* ── Desktop / tablet table ────────────────────────────────────────── */}
      <div className="table-wrap ul-table-wrap desktop-table">
        <table className="data-table users-table ul-table">
          <colgroup>
            <col className="ul-col-name" />
            <col className="ul-col-email" />
            <col className="ul-col-roles" />
            <col className="ul-col-status" />
            <col className="ul-col-created expandable-column" />
            <col className="ul-col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th
                className="sortable"
                onClick={() => handleSort('full_name')}
                aria-sort={sortField === 'full_name' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                Name <SortIcon field="full_name" active={sortField === 'full_name'} dir={sortDirection} />
              </th>
              <th className="ul-col-email">Email</th>
              <th>Roles</th>
              <th
                className="sortable"
                onClick={() => handleSort('status')}
                aria-sort={sortField === 'status' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                Status <SortIcon field="status" active={sortField === 'status'} dir={sortDirection} />
              </th>
              <th
                className="expandable-column sortable"
                onClick={() => handleSort('created_at')}
                aria-sort={sortField === 'created_at' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                Created <SortIcon field="created_at" active={sortField === 'created_at'} dir={sortDirection} />
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isInitialLoad ? (
              <SkeletonRows count={8} />
            ) : pagedUsers.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <div className="ul-empty-state">
                    <span className="ul-empty-icon">👥</span>
                    <p className="ul-empty-title">
                      {selectedSchool || selectedDepartment
                        ? 'No users match the selected filters.'
                        : 'No users found.'}
                    </p>
                    {(selectedSchool || selectedDepartment) && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => { setSelectedSchool(''); setSelectedDepartment(''); setPage(1) }}
                      >
                        Clear filters
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              pagedUsers.map(user => {
                const isExpanded = expandedUsers[user.id]
                return (
                  <React.Fragment key={user.id}>
                    <tr className={`ul-user-row${isExpanded ? ' ul-user-row--expanded' : ''}`}>

                      {/* Name */}
                      <td>
                        <div className="ul-name-cell">
                          <button
                            className="expand-btn"
                            onClick={() => toggleUserExpand(user.id)}
                            aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                            aria-expanded={isExpanded}
                          >
                            <span className={`ul-chevron${isExpanded ? ' ul-chevron--open' : ''}`} aria-hidden>▶</span>
                          </button>
                          <Link to={`/users/${user.id}/edit`} className="ul-name-link">
                            <div className="ul-avatar" aria-hidden>
                              {getInitials(user.full_name)}
                            </div>
                            <div className="ul-name-text">
                              <span className="ul-name-primary">{user.full_name}</span>
                              {user.school_name && (
                                <span className="ul-name-secondary">{user.school_name}</span>
                              )}
                            </div>
                          </Link>
                        </div>
                      </td>

                      {/* Email */}
                      <td className="ul-col-email ul-cell-email">{user.email}</td>

                      {/* Roles */}
                      <td><RoleBadges roles={user.roles} /></td>

                      {/* Status */}
                      <td>
                        <span className={userStatusClass(user)}>
                          {userStatusLabel(user)}
                        </span>
                      </td>

                      {/* Created */}
                      <td className="expandable-column ul-cell-date">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>

                      {/* Actions */}
                      <td>
                        <RoleGuard requires={{ canEdit: true }} fallback={null}>
                          <div className="action-buttons ul-actions">
                            <Link to={`/users/${user.id}/edit`} className="icon-btn" title="Edit user">
                              Edit
                            </Link>
                            {user.status === 'active' && (
                              <button className="icon-btn" title="Set password" onClick={() => setPasswordModalUser(user)}>
                                Password
                              </button>
                            )}
                            <RoleGuard requires={{ canDelete: true }}>
                              {user.status === 'active' && (
                                pendingArchiveId === user.id ? (
                                  <span className="inline-confirm">
                                    <span className="inline-confirm__text">Archive?</span>
                                    <button className="btn btn-sm btn-danger" onClick={() => handleArchive(user.id)}>Yes</button>
                                    <button className="btn btn-sm btn-ghost" onClick={() => setPendingArchiveId(null)}>No</button>
                                  </span>
                                ) : (
                                  <button
                                    onClick={() => setPendingArchiveId(user.id)}
                                    className="icon-btn icon-btn-danger"
                                    title="Archive user"
                                  >⏻</button>
                                )
                              )}
                            </RoleGuard>
                          </div>
                        </RoleGuard>
                      </td>
                    </tr>

                    {/* Expanded detail row */}
                    {isExpanded && (
                      <tr className="expanded-row ul-expanded-row">
                        <td colSpan={6}>
                          <div className="expanded-content ul-expanded-content">
                            <div className="expanded-details ul-expanded-grid">
                              <div className="detail-group">
                                <span className="detail-label">School</span>
                                <span className="detail-value">{user.school_name || <em className="ul-na">Not assigned</em>}</span>
                              </div>
                              <div className="detail-group">
                                <span className="detail-label">Department</span>
                                <span className="detail-value">{user.department_name || <em className="ul-na">Not assigned</em>}</span>
                              </div>
                              <div className="detail-group">
                                <span className="detail-label">Email</span>
                                <span className="detail-value">{user.email}</span>
                              </div>
                              <div className="detail-group">
                                <span className="detail-label">Phone</span>
                                <span className="detail-value">{user.phone || <em className="ul-na">Not provided</em>}</span>
                              </div>
                              <div className="detail-group">
                                <span className="detail-label">Employee ID</span>
                                <span className="detail-value">{user.employee_id || <em className="ul-na">Not provided</em>}</span>
                              </div>
                              <div className="detail-group">
                                <span className="detail-label">MFA</span>
                                <span className="detail-value">{user.mfa_enabled ? 'Enabled' : 'Disabled'}</span>
                              </div>
                              <div className="detail-group">
                                <span className="detail-label">Created</span>
                                <span className="detail-value">{new Date(user.created_at).toLocaleDateString()}</span>
                              </div>
                              {user.archived_at && (
                                <div className="detail-group">
                                  <span className="detail-label">Archived</span>
                                  <span className="detail-value">{new Date(user.archived_at).toLocaleDateString()}</span>
                                </div>
                              )}
                              <div className="detail-group ul-detail-roles">
                                <span className="detail-label">All Roles</span>
                                <RoleBadges roles={user.roles} expanded />
                              </div>
                              {user.department_request_status === 'pending' && user.requested_department_name && (
                                <div className="detail-group">
                                  <span className="detail-label">Requested Dept</span>
                                  <span className="detail-value">{user.requested_department_name}</span>
                                </div>
                              )}
                            </div>

                            <div className="expanded-actions ul-expanded-actions">
                              <Link to={`/users/${user.id}/edit`} className="btn btn-sm btn-primary">Edit User</Link>
                              {user.status === 'active' && (
                                <button className="btn btn-sm" onClick={() => setPasswordModalUser(user)}>
                                  Set Password
                                </button>
                              )}
                              {user.status === 'active' && (
                                pendingArchiveId === user.id ? (
                                  <span className="inline-confirm">
                                    <span className="inline-confirm__text">Archive this user?</span>
                                    <button className="btn btn-sm btn-danger" onClick={() => handleArchive(user.id)}>Yes, archive</button>
                                    <button className="btn btn-sm btn-ghost" onClick={() => setPendingArchiveId(null)}>Cancel</button>
                                  </span>
                                ) : (
                                  <button className="btn btn-sm btn-danger" onClick={() => setPendingArchiveId(user.id)}>
                                    Archive
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
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Mobile accordion cards ───────────────────────────────────────── */}
      <div className="user-list__mobile mobile-cards">
        {isInitialLoad ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="user-card ul-card-skeleton">
              <div className="ul-card-skeleton__header">
                <span className="ul-skeleton ul-skeleton--avatar" />
                <div className="ul-card-skeleton__lines">
                  <span className="ul-skeleton ul-skeleton--name" style={{ width: `${120 + i * 15}px` }} />
                  <span className="ul-skeleton ul-skeleton--sub" style={{ width: '70px' }} />
                </div>
              </div>
            </div>
          ))
        ) : pagedUsers.length === 0 ? (
          <div className="ul-empty-state">
            <span className="ul-empty-icon">👥</span>
            <p className="ul-empty-title">
              {selectedSchool || selectedDepartment ? 'No users match the selected filters.' : 'No users found.'}
            </p>
          </div>
        ) : (
          pagedUsers.map(user => {
            const isExpanded = expandedUsers[user.id]
            return (
              <div key={user.id} className="user-card">
                <div className="user-card__header" onClick={() => toggleUserExpand(user.id)} role="button" tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && toggleUserExpand(user.id)}>
                  <div className="user-card__main">
                    <div className="user-avatar ul-avatar">{getInitials(user.full_name)}</div>
                    <div className="user-card__info">
                      <div className="user-card__name">{user.full_name}</div>
                      <span className={`${userStatusClass(user)} user-card__status`}>
                        {userStatusLabel(user)}
                      </span>
                    </div>
                  </div>
                  <span className={`user-card__expand${isExpanded ? ' user-card__expand--open' : ''}`} aria-hidden>▶</span>
                </div>

                {isExpanded && (
                  <div className="user-card__body">
                    {[
                      ['Email',        user.email],
                      ['School',       user.school_name     || '—'],
                      ['Department',   user.department_name  || '—'],
                      ['Phone',        user.phone           || '—'],
                      ['Employee ID',  user.employee_id     || '—'],
                      ['MFA',          user.mfa_enabled ? 'Enabled' : 'Disabled'],
                      ['Created',      new Date(user.created_at).toLocaleDateString()],
                    ].map(([label, value]) => (
                      <div key={label} className="user-card__detail">
                        <span className="user-card__detail-label">{label}</span>
                        <span className="user-card__detail-value">{value}</span>
                      </div>
                    ))}
                    {user.archived_at && (
                      <div className="user-card__detail">
                        <span className="user-card__detail-label">Archived</span>
                        <span className="user-card__detail-value">{new Date(user.archived_at).toLocaleDateString()}</span>
                      </div>
                    )}
                    <div className="user-card__roles">
                      <div className="user-card__detail-label">Roles</div>
                      <RoleBadges roles={user.roles} expanded />
                    </div>
                    <div className="user-card__actions">
                      <Link to={`/users/${user.id}/edit`} className="btn btn-primary">Edit User</Link>
                      {user.status === 'active' && (
                        <button className="btn" onClick={() => setPasswordModalUser(user)}>Set Password</button>
                      )}
                      {user.status === 'active' && (
                        pendingArchiveId === user.id ? (
                          <span className="inline-confirm">
                            <span className="inline-confirm__text">Archive?</span>
                            <button className="btn btn-sm btn-danger" onClick={() => handleArchive(user.id)}>Yes</button>
                            <button className="btn btn-sm btn-ghost" onClick={() => setPendingArchiveId(null)}>No</button>
                          </span>
                        ) : (
                          <button className="btn btn-danger" onClick={() => setPendingArchiveId(user.id)}>⏻ Deactivate</button>
                        )
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* ── Pagination ───────────────────────────────────────────────────── */}
      {!isInitialLoad && totalPages > 1 && (
        <div className="ul-pagination">
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={safePage === 1}
          >← Prev</button>
          <span className="ul-pagination__info">
            Page {safePage} of {totalPages}
            <span className="ul-pagination__total"> · {total} users</span>
          </span>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={safePage >= totalPages}
          >Next →</button>
        </div>
      )}

      {/* ── Modals ───────────────────────────────────────────────────────── */}
      {passwordModalUser && (
        <SetPasswordModal
          userId={passwordModalUser.id}
          userName={passwordModalUser.full_name}
          onClose={() => setPasswordModalUser(null)}
        />
      )}
      {showBulkImport && (
        <BulkImport
          onClose={() => setShowBulkImport(false)}
          onDone={() => { setBanner({ type: 'success', message: 'Bulk import complete' }); handleRefresh() }}
        />
      )}
      {showInvites && <InviteCodes onClose={() => setShowInvites(false)} />}
    </div>
  )
}

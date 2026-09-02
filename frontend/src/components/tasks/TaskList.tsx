import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useUser } from '@clerk/clerk-react'
import { apiFetch } from '../../lib/api'
import { formatDate, formatDateTime, isDueSoon, isOverdue } from '../../lib/utils'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Task {
  id: string
  title: string
  description?: string
  school_id: string
  school_name?: string
  department_id?: string
  department_name?: string
  created_by: string
  completion_rule: string
  eta: string
  eta_extension_count: number
  status: string
  priority?: 'high' | 'medium' | 'low'
  entity_type?: string
  entity_id?: string
  created_at: string
  updated_at: string
  completed_at?: string
  cancelled_at?: string
}

type SortKey = 'title' | 'priority' | 'eta' | 'status'
type SortDir = 'asc' | 'desc'

const PRIORITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }
const STATUS_ORDER: Record<string, number> = { open: 0, in_progress: 1, completed: 2, cancelled: 3, escalated: 0 }

function sortTasks(items: Task[], key: SortKey, dir: SortDir): Task[] {
  return [...items].sort((a, b) => {
    let cmp = 0
    switch (key) {
      case 'title':
        cmp = a.title.localeCompare(b.title)
        break
      case 'priority':
        cmp = (PRIORITY_ORDER[a.priority ?? 'medium'] ?? 1) - (PRIORITY_ORDER[b.priority ?? 'medium'] ?? 1)
        break
      case 'eta':
        cmp = new Date(a.eta).getTime() - new Date(b.eta).getTime()
        break
      case 'status':
        cmp = (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99)
        break
    }
    return dir === 'asc' ? cmp : -cmp
  })
}

/** Can this task be completed? (mirrors TaskDetail's canComplete logic) */
function canComplete(task: Task): boolean {
  return task.status === 'open' || task.status === 'in_progress'
}

/** Status label for display */
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

/** Priority label */
function priorityLabel(priority?: string): string {
  if (!priority) return 'Medium'
  return priority.charAt(0).toUpperCase() + priority.slice(1)
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function TaskList() {
  const { user } = useUser()

  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('eta')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({})
  const [completingId, setCompletingId] = useState<string | null>(null)

  const fetchTasks = async (signal?: AbortSignal) => {
    try {
      setLoading(true)
      const response = await apiFetch('/api/v1/tasks', { signal })
      if (!response.ok) throw new Error('Failed to fetch tasks')
      setTasks(await response.json())
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchTasks(controller.signal)
    return () => controller.abort()
  }, [])

  // ── Derived data ──────────────────────────────────────────────────────────

  const filteredTasks = tasks.filter(task => {
    const matchesFilter = filter === 'all' || task.status === filter
    const matchesSearch =
      searchTerm === '' ||
      task.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (task.description && task.description.toLowerCase().includes(searchTerm.toLowerCase()))
    return matchesFilter && matchesSearch
  })

  const sortedTasks = sortTasks(filteredTasks, sortKey, sortDir)

  const stats = {
    total: tasks.length,
    pending: tasks.filter(t => t.status === 'open').length,
    inProgress: tasks.filter(t => t.status === 'in_progress').length,
    completed: tasks.filter(t => t.status === 'completed').length,
  }

  // ── Sort helpers ──────────────────────────────────────────────────────────

  const cycleSort = (key: SortKey) => {
    setSortKey(prev => {
      if (prev === key) {
        setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
        return key
      }
      setSortDir(key === 'eta' ? 'asc' : 'asc')
      return key
    })
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return <span className="sort-indicator">↕</span>
    return <span className="sort-indicator">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  // ── Expand ────────────────────────────────────────────────────────────────

  const toggleExpand = (taskId: string) => {
    setExpandedTasks(prev => ({ ...prev, [taskId]: !prev[taskId] }))
  }

  // ── Mark Complete ─────────────────────────────────────────────────────────

  const handleMarkComplete = useCallback(async (taskId: string) => {
    const userId = user?.id
    if (!userId) {
      setError('Cannot determine current user')
      return
    }
    try {
      setCompletingId(taskId)
      const response = await apiFetch(`/api/v1/tasks/${taskId}/complete`, {
        method: 'POST',
        body: JSON.stringify({ completed_by: userId, notes: '' }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || body?.error?.message || 'Failed to complete task')
      }
      // Refresh list to reflect updated status
      await fetchTasks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete task')
    } finally {
      setCompletingId(null)
    }
  }, [user, fetchTasks])

  // ── Loading / error ──────────────────────────────────────────────────────

  if (loading) return <div className="loading-state">Loading tasks…</div>
  if (error) return <div className="error">{error}</div>

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="task-list page-shell">

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">Task Management</div>
          <h1>Tasks</h1>
        </div>
        <Link to="/tasks/new" className="btn btn-primary">＋ Create Task</Link>
      </div>

      {/* ── Stats Ribbon ────────────────────────────────────────────────── */}
      <div className="ribbon">
        <div className="ribbon-item">
          <div className="ribbon-num">{stats.total}</div>
          <div className="ribbon-label">Total</div>
        </div>
        <div className="ribbon-item warn">
          <div className="ribbon-num">{stats.pending}</div>
          <div className="ribbon-label">Pending</div>
        </div>
        <div className="ribbon-item">
          <div className="ribbon-num">{stats.inProgress}</div>
          <div className="ribbon-label">In Progress</div>
        </div>
        <div className="ribbon-item accent">
          <div className="ribbon-num">{stats.completed}</div>
          <div className="ribbon-label">Completed</div>
        </div>
      </div>

      {/* ── Controls ────────────────────────────────────────────────────── */}
      <div className="controls">
        <div className="tabs">
          <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>
            All Tasks <span className="count">{stats.total}</span>
          </button>
          <button className={filter === 'open' ? 'active' : ''} onClick={() => setFilter('open')}>
            Pending <span className="count">{stats.pending}</span>
          </button>
          <button className={filter === 'in_progress' ? 'active' : ''} onClick={() => setFilter('in_progress')}>
            In Progress <span className="count">{stats.inProgress}</span>
          </button>
          <button className={filter === 'completed' ? 'active' : ''} onClick={() => setFilter('completed')}>
            Completed <span className="count">{stats.completed}</span>
          </button>
        </div>
        <div className="search-mini">
          <span>🔍</span>
          <input
            type="text"
            placeholder="Search tasks…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* ── Table ────────────────────────────────────────────────────────── */}
      {sortedTasks.length === 0 ? (
        <div className="empty">
          <div className="glyph">🗂️</div>
          <h3>No tasks found</h3>
          <p>Nothing matches this filter yet — try another view or create a new task.</p>
        </div>
      ) : (
        <>
          {/* Desktop / tablet table */}
          <div className="table-wrap task-table-wrap">
            <table className="data-table tasks-table">
              <thead>
                <tr>
                  <th
                    className="sortable"
                    onClick={() => cycleSort('title')}
                    aria-sort={sortKey === 'title' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Title {sortIndicator('title')}
                  </th>
                  <th className="col-dept-school">Department · School</th>
                  <th
                    className="sortable col-priority"
                    onClick={() => cycleSort('priority')}
                    aria-sort={sortKey === 'priority' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Priority {sortIndicator('priority')}
                  </th>
                  <th
                    className="sortable col-due"
                    onClick={() => cycleSort('eta')}
                    aria-sort={sortKey === 'eta' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Due {sortIndicator('eta')}
                  </th>
                  <th
                    className="sortable col-status"
                    onClick={() => cycleSort('status')}
                    aria-sort={sortKey === 'status' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Status {sortIndicator('status')}
                  </th>
                  <th className="col-expand" />
                </tr>
              </thead>
              <tbody>
                {sortedTasks.map((task) => {
                  const isExpanded = !!expandedTasks[task.id]
                  const dueSoon = isDueSoon(task.eta)
                  const overdue = isOverdue(task.eta) && canComplete(task)

                  return (
                    <React.Fragment key={task.id}>
                      <tr className={isExpanded ? 'row-expanded' : ''}>
                        <td className="task-title-cell">
                          <Link to={`/tasks/${task.id}`} className="task-title-link">
                            {task.title}
                          </Link>
                          {/* Priority shown on mobile at top level */}
                          <span className="task-title-mobile-priority">
                            <span className={`dot ${task.priority === 'high' ? 'high' : task.priority === 'low' ? 'low' : 'med'}`} />
                            <span>{priorityLabel(task.priority)}</span>
                          </span>
                        </td>
                        <td className="task-dept-school expandable-column">
                          <span className="task-dept-name">{task.department_name || '—'}</span>
                          <span className="task-school-name">{task.school_name || task.school_id}</span>
                        </td>
                        <td className="task-priority-cell col-priority expandable-column">
                          <span className="priority-inline">
                            <span className={`dot ${task.priority === 'high' ? 'high' : task.priority === 'low' ? 'low' : 'med'}`} />
                            <span>{priorityLabel(task.priority)}</span>
                          </span>
                        </td>
                        <td className="task-due-cell col-due expandable-column">
                          <span className={`task-due ${dueSoon ? 'soon' : ''} ${overdue ? 'overdue' : ''}`}>
                            {formatDate(task.eta)}
                          </span>
                        </td>
                        <td className="task-status-cell col-status expandable-column">
                          <span className={`status-pill status-pill--${task.status === 'open' ? 'pending' : task.status === 'in_progress' ? 'progress' : task.status === 'completed' ? 'completed' : 'pending'}`}>
                            {statusLabel(task.status)}
                          </span>
                        </td>
                        <td className="task-expand-cell col-expand">
                          <button
                            className="expand-toggle-btn"
                            onClick={() => toggleExpand(task.id)}
                            aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                            aria-expanded={isExpanded}
                          >
                            {isExpanded ? '▼' : '▶'}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded row details */}
                      {isExpanded && (
                        <tr className="expanded-row">
                          <td colSpan={6}>
                            <div className="expanded-content">
                              <div className="expanded-details">
                                {task.description && (
                                  <div className="detail-group detail-group--full">
                                    <span className="detail-label">Description</span>
                                    <span className="detail-value">{task.description}</span>
                                  </div>
                                )}
                                <div className="detail-group">
                                  <span className="detail-label">School ID</span>
                                  <span className="detail-value">{task.school_id}</span>
                                </div>
                                <div className="detail-group">
                                  <span className="detail-label">Created</span>
                                  <span className="detail-value">{formatDateTime(task.created_at)}</span>
                                </div>
                                <div className="detail-group">
                                  <span className="detail-label">Updated</span>
                                  <span className="detail-value">{formatDateTime(task.updated_at)}</span>
                                </div>
                                {task.completed_at && (
                                  <div className="detail-group">
                                    <span className="detail-label">Completed</span>
                                    <span className="detail-value">{formatDateTime(task.completed_at)}</span>
                                  </div>
                                )}
                              </div>
                              <div className="expanded-actions">
                                <Link to={`/tasks/${task.id}`} className="btn btn-sm">View Details</Link>
                                <Link to={`/tasks/${task.id}/edit`} className="btn btn-sm">Edit</Link>
                                {canComplete(task) && (
                                  <button
                                    className="btn btn-sm btn-primary"
                                    onClick={() => handleMarkComplete(task.id)}
                                    disabled={completingId === task.id}
                                  >
                                    {completingId === task.id ? 'Completing…' : 'Mark Complete'}
                                  </button>
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

          {/* Mobile stacked cards */}
          <div className="task-mobile-cards">
            {sortedTasks.map((task) => {
              const isExpanded = !!expandedTasks[task.id]
              const dueSoon = isDueSoon(task.eta)
              const overdue = isOverdue(task.eta) && canComplete(task)

              return (
                <div key={task.id} className="task-mobile-card">
                  <div
                    className="task-mobile-card__header"
                    onClick={() => toggleExpand(task.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter') toggleExpand(task.id) }}
                  >
                    <div className="task-mobile-card__top">
                      <div className="task-mobile-card__title-row">
                        <span className={`task-mobile-card__title ${task.status === 'completed' ? 'done' : ''}`}>
                          {task.title}
                        </span>
                        <span className={`status-pill status-pill--${task.status === 'open' ? 'pending' : task.status === 'in_progress' ? 'progress' : task.status === 'completed' ? 'completed' : 'pending'}`}>
                          {statusLabel(task.status)}
                        </span>
                      </div>
                      <div className="task-mobile-card__priority-row">
                        <span className={`dot ${task.priority === 'high' ? 'high' : task.priority === 'low' ? 'low' : 'med'}`} />
                        <span className="task-mobile-card__priority-label">{priorityLabel(task.priority)}</span>
                        <span className={`task-mobile-card__due ${dueSoon ? 'soon' : ''} ${overdue ? 'overdue' : ''}`}>
                          Due {formatDate(task.eta)}
                        </span>
                      </div>
                    </div>
                    <span className={`task-mobile-card__expand ${isExpanded ? 'open' : ''}`}>▶</span>
                  </div>

                  {isExpanded && (
                    <div className="task-mobile-card__body">
                      {task.description && (
                        <div className="task-mobile-card__detail">
                          <span className="detail-label">Description</span>
                          <span className="detail-value">{task.description}</span>
                        </div>
                      )}
                      <div className="task-mobile-card__detail">
                        <span className="detail-label">Department</span>
                        <span className="detail-value">{task.department_name || '—'}</span>
                      </div>
                      <div className="task-mobile-card__detail">
                        <span className="detail-label">School</span>
                        <span className="detail-value">{task.school_name || task.school_id}</span>
                      </div>
                      <div className="task-mobile-card__detail">
                        <span className="detail-label">Due Date</span>
                        <span className="detail-value">{formatDateTime(task.eta)}</span>
                      </div>
                      <div className="task-mobile-card__actions">
                        <Link to={`/tasks/${task.id}`} className="btn btn-sm">View Details</Link>
                        <Link to={`/tasks/${task.id}/edit`} className="btn btn-sm">Edit</Link>
                        {canComplete(task) && (
                          <button
                            className="btn btn-sm btn-primary btn-full"
                            onClick={(e) => { e.stopPropagation(); handleMarkComplete(task.id) }}
                            disabled={completingId === task.id}
                          >
                            {completingId === task.id ? 'Completing…' : 'Mark Complete'}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}


import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'
import './TaskForm.css'

interface TaskFormData {
  title: string
  description?: string
  owner_ids: string[]
  completion_rule: string
  eta: string
  school_id: string
  department_id?: string
  entity_type?: string
  entity_id?: string
}

interface School { id: string; name: string; school_code?: string }
interface Department { id: string; name: string }
interface User { id: string; full_name: string; email: string; status?: string }

// Entity types — confirmed from search_indexer.py and API routes
const ENTITY_TYPES = [
  { value: 'observation', label: 'Observation' },
  { value: 'task', label: 'Task' },
  { value: 'discrepancy', label: 'Discrepancy' },
  { value: 'kpi', label: 'KPI' },
]

// Endpoint mapping — not all entity types follow the /${type}s pattern
const ENTITY_ENDPOINTS: Record<string, string> = {
  observation: '/api/v1/observations',
  task: '/api/v1/tasks',
  discrepancy: '/api/v1/audit-discrepancy/discrepancies',
  kpi: '/api/v1/kra-kpi-library/kpis',
}

export default function TaskForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEditing = !!id

  const [formData, setFormData] = useState<TaskFormData>({
    title: '', description: '', owner_ids: [], completion_rule: 'any_owner',
    eta: '', school_id: '', department_id: '', entity_type: '', entity_id: '',
  })

  const [schools, setSchools] = useState<School[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Owner search state
  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerDropdownOpen, setOwnerDropdownOpen] = useState(false)
  const ownerDropdownRef = useRef<HTMLDivElement>(null)

  // Entity search state
  const [entitySearch, setEntitySearch] = useState('')
  const [entityOptions, setEntityOptions] = useState<{ value: string; label: string }[]>([])
  const [entityLoading, setEntityLoading] = useState(false)

  useEffect(() => {
    fetchSchools()
    fetchUsers()
    if (isEditing) fetchTask()
  }, [id])

  useEffect(() => {
    if (formData.school_id) {
      fetchDepartments(formData.school_id)
      // Clear department when school changes
      if (formData.department_id) {
        setFormData(prev => ({ ...prev, department_id: '' }))
      }
    } else {
      setDepartments([])
    }
  }, [formData.school_id])

  // Fetch entities when entity_type changes
  useEffect(() => {
    if (formData.entity_type) {
      fetchEntities(formData.entity_type)
      setFormData(prev => ({ ...prev, entity_id: '' }))
    } else {
      setEntityOptions([])
    }
  }, [formData.entity_type])

  // Close owner dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ownerDropdownRef.current && !ownerDropdownRef.current.contains(e.target as Node)) {
        setOwnerDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const fetchSchools = async () => {
    try {
      const res = await apiFetch('/api/v1/schools?page_size=100')
      if (res.ok) {
        const data = await res.json()
        setSchools(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch schools:', err)
    }
  }

  const fetchDepartments = async (schoolId: string) => {
    try {
      const res = await apiFetch(`/api/v1/departments?school_id=${schoolId}&page_size=100`)
      if (res.ok) {
        const data = await res.json()
        setDepartments(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch departments:', err)
    }
  }

  const fetchUsers = async () => {
    try {
      const res = await apiFetch('/api/v1/users?page_size=100')
      if (res.ok) {
        const data = await res.json()
        setUsers(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch users:', err)
    }
  }

  const fetchTask = async () => {
    try {
      setLoading(true)
      const res = await apiFetch(`/api/v1/tasks/${id}`)
      if (res.ok) {
        const task = await res.json()
        setFormData({
          title: task.title,
          description: task.description || '',
          owner_ids: task.owners?.map((o: any) => o.user_id || o.id) || task.owner_ids || [],
          completion_rule: task.completion_rule,
          eta: task.eta ? task.eta.slice(0, 16) : '',
          school_id: task.school_id || '',
          department_id: task.department_id || '',
          entity_type: task.entity_type || '',
          entity_id: task.entity_id || '',
        })
      } else {
        throw new Error('Failed to fetch task')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const fetchEntities = async (type: string) => {
    setEntityLoading(true)
    try {
      const endpoint = ENTITY_ENDPOINTS[type] || `/api/v1/${type}s`
      const res = await apiFetch(`${endpoint}?page_size=50`)
      if (res.ok) {
        const data = await res.json()
        const items = data.data || data.reports || data || []
        setEntityOptions(items.map((item: any) => ({
          value: item.id,
          label: item.title || item.name || item.id,
        })))
      }
    } catch {
      setEntityOptions([])
    } finally {
      setEntityLoading(false)
    }
  }

  // ── Owner multi-select logic ───────────────────────────────────────────
  const selectedOwners = useMemo(() =>
    users.filter(u => formData.owner_ids.includes(u.id)),
    [users, formData.owner_ids]
  )

  const filteredAvailableOwners = useMemo(() => {
    const term = ownerSearch.toLowerCase()
    return users.filter(u =>
      !formData.owner_ids.includes(u.id) &&
      (u.full_name?.toLowerCase().includes(term) || u.email?.toLowerCase().includes(term))
    )
  }, [users, formData.owner_ids, ownerSearch])

  const addOwner = (userId: string) => {
    setFormData(prev => ({
      ...prev,
      owner_ids: [...prev.owner_ids, userId],
    }))
    setOwnerSearch('')
    setOwnerDropdownOpen(false)
  }

  const removeOwner = (userId: string) => {
    setFormData(prev => ({
      ...prev,
      owner_ids: prev.owner_ids.filter(id => id !== userId),
    }))
  }

  // ── Title character counter ─────────────────────────────────────────────
  const titleLength = formData.title.length
  const showCounter = titleLength > 200
  const counterClass = titleLength > 240 ? 'char-counter--danger' : titleLength > 200 ? 'char-counter--warn' : ''

  // ── Submit ──────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (formData.owner_ids.length === 0) {
      setError('At least one owner is required')
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      const payload: any = {
        ...formData,
        eta: new Date(formData.eta).toISOString(),
      }

      const url = isEditing ? `/api/v1/tasks/${id}` : '/api/v1/tasks'
      const method = isEditing ? 'PATCH' : 'POST'

      // Exclude immutable fields on edit
      if (isEditing) {
        delete payload.completion_rule
        delete payload.created_by
      }

      const res = await apiFetch(url, { method, body: JSON.stringify(payload) })
      if (!res.ok) {
        const errBody = await res.json().catch(() => null)
        throw new Error(errBody?.error?.message || 'Failed to save task')
      }

      navigate('/tasks')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="loading-state">Loading…</div>

  return (
    <div className="task-form page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <button onClick={() => navigate('/tasks')} className="btn btn-ghost btn-sm" style={{ marginBottom: 'var(--space-2)' }}>
            ← Tasks
          </button>
          <h1>{isEditing ? 'Edit Task' : 'Create Task'}</h1>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: '0 var(--space-10) var(--space-5)' }}>
          <span className="alert-icon">⚠️</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="alert-close">×</button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="task-form__card">

        {/* ── Title ────────────────────────────────────────────────────── */}
        <div className="form-group">
          <label htmlFor="title">Title *</label>
          <input
            id="title"
            type="text"
            value={formData.title}
            onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
            required
            maxLength={255}
            className="form-group__input"
            placeholder="Enter task title"
          />
          {showCounter && (
            <span className={`char-counter ${counterClass}`}>
              {titleLength}/255
            </span>
          )}
        </div>

        {/* ── Description ──────────────────────────────────────────────── */}
        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={formData.description || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
            rows={3}
            className="form-group__input form-group__textarea"
            placeholder="Optional description"
          />
        </div>

        {/* ── School (searchable) ──────────────────────────────────────── */}
        <div className="form-group">
          <label htmlFor="school">School *</label>
          <SearchableSelect
            id="school"
            name="school_id"
            value={formData.school_id}
            onChange={(val) => setFormData(prev => ({ ...prev, school_id: val, department_id: '' }))}
            options={schools.map(s => ({ value: s.id, label: s.name, sublabel: s.school_code }))}
            placeholder="Select school…"
            required
            unsetLabel="Clear"
          />
        </div>

        {/* ── Department (searchable, dependent) ───────────────────────── */}
        <div className="form-group">
          <label htmlFor="department">Department</label>
          <SearchableSelect
            id="department"
            name="department_id"
            value={formData.department_id || ''}
            onChange={(val) => setFormData(prev => ({ ...prev, department_id: val }))}
            options={departments.map(d => ({ value: d.id, label: d.name }))}
            placeholder={formData.school_id ? 'Select department…' : 'Select school first'}
            disabled={!formData.school_id}
            unsetLabel="Clear"
          />
        </div>

        {/* ── Completion Rule (immutable on edit) ──────────────────────── */}
        <div className="form-group">
          <label htmlFor="completion_rule">
            Completion Rule *
            {isEditing && (
              <span className="field-note" title="Cannot be changed after creation">
                🔒 Immutable
              </span>
            )}
          </label>
          <select
            id="completion_rule"
            value={formData.completion_rule}
            onChange={(e) => setFormData(prev => ({ ...prev, completion_rule: e.target.value }))}
            required
            disabled={isEditing}
            className="form-group__input"
            title={isEditing ? 'Cannot be changed after creation' : undefined}
          >
            <option value="any_owner">Any Owner</option>
            <option value="all_owners">All Owners</option>
            <option value="majority">Majority of Owners</option>
          </select>
        </div>

        {/* ── ETA ──────────────────────────────────────────────────────── */}
        <div className="form-group">
          <label htmlFor="eta">ETA *</label>
          <input
            id="eta"
            type="datetime-local"
            value={formData.eta}
            onChange={(e) => setFormData(prev => ({ ...prev, eta: e.target.value }))}
            required
            className="form-group__input"
          />
        </div>

        {/* ── Task Owners (searchable multi-select with chips) ─────────── */}
        <div className="form-group">
          <label htmlFor="owners">Task Owners *</label>

          {/* Selected owner chips */}
          {selectedOwners.length > 0 && (
            <div className="owner-chips">
              {selectedOwners.map(owner => (
                <span key={owner.id} className="owner-chip">
                  <span className="owner-chip__name">{owner.full_name || owner.email}</span>
                  <button
                    type="button"
                    className="owner-chip__remove"
                    onClick={() => removeOwner(owner.id)}
                    aria-label={`Remove ${owner.full_name}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Searchable dropdown */}
          <div className="owner-search" ref={ownerDropdownRef}>
            <input
              id="owners"
              type="text"
              value={ownerSearch}
              onChange={(e) => { setOwnerSearch(e.target.value); setOwnerDropdownOpen(true) }}
              onFocus={() => setOwnerDropdownOpen(true)}
              placeholder={selectedOwners.length > 0 ? 'Add another owner…' : 'Search users…'}
              className="form-group__input"
            />
            {ownerDropdownOpen && filteredAvailableOwners.length > 0 && (
              <div className="owner-dropdown">
                {filteredAvailableOwners.slice(0, 10).map(user => (
                  <button
                    key={user.id}
                    type="button"
                    className="owner-dropdown__item"
                    onClick={() => addOwner(user.id)}
                  >
                    <span className="owner-dropdown__name">{user.full_name || user.email}</span>
                    <span className="owner-dropdown__email">{user.email}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {formData.owner_ids.length === 0 && (
            <span className="form-group__hint form-group__hint--error">
              At least one owner is required
            </span>
          )}
        </div>

        {/* ── Entity Type + Entity ID (dependent pair, side-by-side) ───── */}
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="entity_type">Entity Type</label>
            <select
              id="entity_type"
              value={formData.entity_type || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, entity_type: e.target.value, entity_id: '' }))}
              className="form-group__input"
            >
              <option value="">None</option>
              {ENTITY_TYPES.map(et => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="entity_id">Entity ID</label>
            <SearchableSelect
              id="entity_id"
              name="entity_id"
              value={formData.entity_id || ''}
              onChange={(val) => setFormData(prev => ({ ...prev, entity_id: val }))}
              options={entityOptions}
              placeholder={formData.entity_type ? 'Search entities…' : 'Select entity type first'}
              disabled={!formData.entity_type}
              loading={entityLoading}
              unsetLabel="Clear"
            />
          </div>
        </div>

        {/* ── Footer ───────────────────────────────────────────────────── */}
        <div className="form-actions">
          <button type="button" className="btn btn-ghost" onClick={() => navigate('/tasks')}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save Task'}
          </button>
        </div>
      </form>
    </div>
  )
}

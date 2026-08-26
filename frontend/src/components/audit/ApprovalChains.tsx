import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'
import './ApprovalChains.css'

/* ── Types ─────────────────────────────────────────────────────────────── */

interface ApprovalLevel {
  level: number
  role_id?: string
  user_id?: string
  assignee_type: 'role' | 'user'
  auto_escalation_sla_hours?: number
}

interface ApprovalChain {
  chain_version_id: string
  name: string
  description?: string
  levels: ApprovalLevel[]
  is_active: boolean
  priority: number
  school_id?: string
  school_name?: string
  department_id?: string
  department_name?: string
  category_id?: string
  category_name?: string
  created_at: string
  created_by?: string
}

interface Role {
  id: string
  name: string
  description?: string
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
  school_id: string
}

interface Category {
  id: string
  name: string
  status: string
}

interface User {
  id: string
  email: string
  full_name: string
  school_id?: string
  school_name?: string
  roles: string[]
}

/* ── Helpers ───────────────────────────────────────────────────────────── */

function resolveAssigneeName(
  level: ApprovalLevel,
  roleLookup: Map<string, string>,
  userLookup: Map<string, string>,
): string {
  if (level.assignee_type === 'user' && level.user_id) {
    return userLookup.get(level.user_id) || level.user_id.slice(0, 8) + '...'
  }
  if (level.role_id) {
    return roleLookup.get(level.role_id) || level.role_id.charAt(0).toUpperCase() + level.role_id.slice(1)
  }
  return '—'
}

function scopeSummary(chain: ApprovalChain): string {
  const parts: string[] = []
  if (chain.school_name) parts.push(chain.school_name)
  if (chain.department_name) parts.push(chain.department_name)
  if (chain.category_name) parts.push(chain.category_name)
  return parts.length > 0 ? parts.join(' / ') : 'All schools, all departments'
}

/* ── Main component ────────────────────────────────────────────────────── */

export default function ApprovalChains() {
  const [chains, setChains] = useState<ApprovalChain[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [schools, setSchools] = useState<School[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingChain, setEditingChain] = useState<ApprovalChain | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    priority: 0,
    school_id: '',
    department_id: '',
    category_id: '',
    levels: [{ level: 1, assignee_type: 'role' as 'role' | 'user', role_id: '', user_id: '', auto_escalation_sla_hours: 24 }],
  })

  const [submitting, setSubmitting] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ApprovalChain | null>(null)

  /* ── Data fetching ──────────────────────────────────────────────────── */

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    const load = async () => {
      setLoading(true)
      await Promise.all([
        fetchChains(signal),
        fetchRoles(signal),
        fetchSchools(signal),
        fetchCategories(signal),
        fetchUsers(signal),
      ])
      setLoading(false)
    }
    load()
    return () => controller.abort()
  }, [])

  const fetchChains = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch('/api/v1/audit-discrepancy/approval-chains', { signal })
      if (res.ok) setChains(await res.json())
      else setChains([])
    } catch { setChains([]) }
  }

  const fetchRoles = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch('/api/v1/users/roles', { signal })
      if (res.ok) {
        const data = await res.json()
        setRoles(data.roles || data || [])
      }
    } catch { /* ignore */ }
  }

  const fetchSchools = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch('/api/v1/schools?page=1&page_size=200', { signal })
      if (res.ok) {
        const data = await res.json()
        setSchools(data.data || [])
      }
    } catch { /* ignore */ }
  }

  const fetchCategories = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch('/api/v1/settings/master-data/discrepancy-categories', { signal })
      if (res.ok) {
        const data = await res.json()
        setCategories(data || [])
      }
    } catch { /* ignore */ }
  }

  const fetchUsers = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch('/api/v1/users?page=1&page_size=200', { signal })
      if (res.ok) {
        const data = await res.json()
        setUsers(data.data || [])
      }
    } catch { /* ignore */ }
  }

  const fetchDepartments = async (schoolId: string) => {
    if (!schoolId) { setDepartments([]); return }
    try {
      const res = await apiFetch(`/api/v1/departments?school_id=${schoolId}`)
      if (res.ok) {
        const data = await res.json()
        setDepartments(data.data || [])
      }
    } catch { setDepartments([]) }
  }

  /* ── Lookups ─────────────────────────────────────────────────────────── */

  const roleLookup = new Map(roles.map(r => [r.id, r.name.charAt(0).toUpperCase() + r.name.slice(1)]))

  const roleOptions = roles.map(r => ({
    value: r.id,
    label: r.name.charAt(0).toUpperCase() + r.name.slice(1),
    sublabel: r.description || '',
  }))

  const userLookup = new Map(users.map(u => [u.id, `${u.full_name} (${u.email})`]))

  const userOptions = users.map(u => ({
    value: u.id,
    label: u.full_name,
    sublabel: `${u.email}${u.school_name ? ' - ' + u.school_name : ''}`,
  }))

  const schoolOptions = [
    { value: '', label: 'All Schools', sublabel: 'Matches any school' },
    ...schools.map(s => ({ value: s.id, label: s.name, sublabel: s.code })),
  ]

  const departmentOptions = [
    { value: '', label: 'All Departments', sublabel: 'Matches any department' },
    ...departments.map(d => ({ value: d.id, label: d.name, sublabel: d.code })),
  ]

  const categoryOptions = [
    { value: '', label: 'All Categories', sublabel: 'Matches any discrepancy category' },
    ...categories.map(c => ({ value: c.id, label: c.name, sublabel: c.status })),
  ]

  /* ── Form: dynamic levels ───────────────────────────────────────────── */

  const handleAddLevel = () => {
    const newLevel = formData.levels.length + 1
    setFormData(prev => ({
      ...prev,
      levels: [
        ...prev.levels,
        { level: newLevel, assignee_type: 'role', role_id: '', user_id: '', auto_escalation_sla_hours: 24 },
      ],
    }))
  }

  const handleRemoveLevel = (index: number) => {
    setFormData(prev => ({
      ...prev,
      levels: prev.levels
        .filter((_, i) => i !== index)
        .map((l, i) => ({ ...l, level: i + 1 })),
    }))
  }

  const handleLevelChange = (index: number, field: string, value: string | number) => {
    setFormData(prev => ({
      ...prev,
      levels: prev.levels.map((l, i) =>
        i === index ? { ...l, [field]: value } : l
      ),
    }))
  }

  /* ── Submit ──────────────────────────────────────────────────────────── */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const payload = {
        name: formData.name,
        description: formData.description || null,
        priority: formData.priority,
        school_id: formData.school_id || null,
        department_id: formData.department_id || null,
        category_id: formData.category_id || null,
        levels: formData.levels.map(l => ({
          level: l.level,
          role_id: l.assignee_type === 'role' ? l.role_id : undefined,
          user_id: l.assignee_type === 'user' ? l.user_id : undefined,
          auto_escalation_sla_hours: l.auto_escalation_sla_hours,
        })),
      }

      const url = editingChain
        ? `/api/v1/audit-discrepancy/approval-chains/${editingChain.chain_version_id}`
        : '/api/v1/audit-discrepancy/approval-chains'
      const method = editingChain ? 'PATCH' : 'POST'

      const res = await apiFetch(url, {
        method,
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errBody = await res.json().catch(() => null)
        throw new Error(errBody?.detail || errBody?.error?.message || 'Failed to save chain')
      }

      await fetchChains()
      setShowForm(false)
      setEditingChain(null)
      resetForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      priority: 0,
      school_id: '',
      department_id: '',
      category_id: '',
      levels: [{ level: 1, assignee_type: 'role', role_id: '', user_id: '', auto_escalation_sla_hours: 24 }],
    })
  }

  const handleEdit = (chain: ApprovalChain) => {
    setEditingChain(chain)
    setFormData({
      name: chain.name,
      description: chain.description || '',
      priority: chain.priority,
      school_id: chain.school_id || '',
      department_id: chain.department_id || '',
      category_id: chain.category_id || '',
      levels: chain.levels.map((l, i) => ({
        level: i + 1,
        assignee_type: l.assignee_type || 'role',
        role_id: l.role_id || '',
        user_id: l.user_id || '',
        auto_escalation_sla_hours: l.auto_escalation_sla_hours || 24,
      })),
    })
    if (chain.school_id) fetchDepartments(chain.school_id)
    setShowForm(true)
  }

  /* ── Activate / Deactivate / Delete ──────────────────────────────────── */

  const handleToggleActive = async (chain: ApprovalChain) => {
    const action = chain.is_active ? 'deactivate' : 'activate'
    try {
      const res = await apiFetch(
        `/api/v1/audit-discrepancy/approval-chains/${chain.chain_version_id}/${action}`,
        { method: 'PATCH' },
      )
      if (res.ok) await fetchChains()
    } catch { /* ignore */ }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      const res = await apiFetch(
        `/api/v1/audit-discrepancy/approval-chains/${deleteTarget.chain_version_id}`,
        { method: 'DELETE' },
      )
      if (res.ok) {
        await fetchChains()
        setDeleteTarget(null)
      } else {
        const errBody = await res.json().catch(() => null)
        setError(errBody?.detail || 'Failed to delete chain')
      }
    } catch { /* ignore */ }
  }

  /* ── Loading ─────────────────────────────────────────────────────────── */

  if (loading) return <div className="loading-state">Loading approval chains...</div>

  /* ── Render ──────────────────────────────────────────────────────────── */

  return (
    <div className="approval-chains page-shell">

      {/* Page Header */}
      <div className="page-head ac-page-head">
        <div>
          <div className="eyebrow">Policy Configuration</div>
          <h1>Approval Chains</h1>
        </div>
        <button
          className={`btn ${showForm ? 'btn-ghost' : 'btn-primary'}`}
          onClick={() => { setShowForm(!showForm); setEditingChain(null); resetForm() }}
        >
          {showForm ? 'Cancel' : '+ Create New Chain'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="ac-alert ac-alert-error" style={{ margin: 'var(--space-5) 40px 0' }}>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ac-alert__close">x</button>
        </div>
      )}

      <div style={{ padding: 'var(--space-5) 40px 0' }}>

        {/* ── Active Chains ──────────────────────────────────────────── */}
        <div className="ac-section-head">
          <h3>Active Chains</h3>
          <span style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)' }}>
            {chains.filter(c => c.is_active).length} active
          </span>
        </div>

        {chains.filter(c => c.is_active).length === 0 ? (
          <div className="ac-empty">
            <h3>No active approval chains</h3>
            <p>Create a chain and activate it to configure discrepancy approval flow.</p>
          </div>
        ) : (
          <div className="ac-chain-stack">
            {chains.filter(c => c.is_active).map(chain => (
              <ChainCard
                key={chain.chain_version_id}
                chain={chain}
                roleLookup={roleLookup}
                userLookup={userLookup}
                onEdit={handleEdit}
                onToggle={handleToggleActive}
                onDelete={setDeleteTarget}
              />
            ))}
          </div>
        )}

        {/* ── Inactive Chains ───────────────────────────────────────── */}
        {chains.filter(c => !c.is_active).length > 0 && (
          <>
            <div className="ac-section-head" style={{ marginTop: 'var(--space-6)' }}>
              <h3>Inactive Chains</h3>
            </div>
            <div className="ac-chain-stack">
              {chains.filter(c => !c.is_active).map(chain => (
                <ChainCard
                  key={chain.chain_version_id}
                  chain={chain}
                  roleLookup={roleLookup}
                  userLookup={userLookup}
                  onEdit={handleEdit}
                  onToggle={handleToggleActive}
                  onDelete={setDeleteTarget}
                />
              ))}
            </div>
          </>
        )}

        {/* ── Create / Edit Form ────────────────────────────────────── */}
        {showForm && (
          <form onSubmit={handleSubmit} className="ac-form" style={{ marginTop: 'var(--space-6)' }}>
            <h3 className="ac-form__title">{editingChain ? 'Edit Chain' : 'Create New Chain'}</h3>

            {/* Name + Priority */}
            <div className="ac-form__row">
              <div className="form-group" style={{ flex: 2 }}>
                <label htmlFor="chain-name">Chain Name *</label>
                <input
                  id="chain-name"
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Financial Audit Chain"
                  className="form-input"
                  required
                />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="chain-priority">Priority (higher = checked first)</label>
                <input
                  id="chain-priority"
                  type="number"
                  value={formData.priority}
                  onChange={e => setFormData(prev => ({ ...prev, priority: parseInt(e.target.value) || 0 }))}
                  className="form-input"
                />
              </div>
            </div>

            {/* Description */}
            <div className="form-group">
              <label htmlFor="chain-desc">Description (optional)</label>
              <input
                id="chain-desc"
                type="text"
                value={formData.description}
                onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="When should this chain be used?"
                className="form-input"
              />
            </div>

            {/* Scope Filters */}
            <div className="ac-form__section-header">
              <span className="ac-form__section-label">Scope Filters (optional)</span>
            </div>
            <p style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)', margin: '0 0 var(--space-3)' }}>
              Leave blank to match all. Specific scopes take priority when combined with higher priority numbers.
            </p>

            <div className="ac-form__row">
              <div className="form-group">
                <label>School</label>
                <SearchableSelect
                  id="chain-school"
                  name="school_id"
                  value={formData.school_id}
                  onChange={val => {
                    setFormData(prev => ({ ...prev, school_id: val, department_id: '' }))
                    fetchDepartments(val)
                  }}
                  options={schoolOptions}
                  placeholder="All Schools"
                />
              </div>
              <div className="form-group">
                <label>Department</label>
                <SearchableSelect
                  id="chain-dept"
                  name="department_id"
                  value={formData.department_id}
                  onChange={val => setFormData(prev => ({ ...prev, department_id: val }))}
                  options={departmentOptions}
                  placeholder="All Departments"
                  disabled={!formData.school_id}
                />
              </div>
              <div className="form-group">
                <label>Category</label>
                <SearchableSelect
                  id="chain-category"
                  name="category_id"
                  value={formData.category_id}
                  onChange={val => setFormData(prev => ({ ...prev, category_id: val }))}
                  options={categoryOptions}
                  placeholder="All Categories"
                />
              </div>
            </div>

            {/* Approval Levels */}
            <div className="ac-form__section-header">
              <span className="ac-form__section-label">Approval Levels</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={handleAddLevel}>
                Add Level
              </button>
            </div>

            {formData.levels.map((level, index) => (
              <div key={`level-${index}`} className="ac-level-card">
                <div className="ac-level-card__head">
                  <span className="ac-level-card__number">Level {level.level}</span>
                  {formData.levels.length > 1 && (
                    <button type="button" className="btn btn-ghost btn-sm" style={{ color: 'var(--rose-600)' }}
                      onClick={() => handleRemoveLevel(index)}>
                      Remove
                    </button>
                  )}
                </div>

                <div className="ac-level-card__fields">
                  {/* Assignee type toggle */}
                  <div className="form-group" style={{ flex: 0.5 }}>
                    <label>Assignee Type</label>
                    <select
                      value={level.assignee_type}
                      onChange={e => handleLevelChange(index, 'assignee_type', e.target.value)}
                      className="form-input"
                    >
                      <option value="role">Role</option>
                      <option value="user">Specific Person</option>
                    </select>
                  </div>

                  {/* Role selector */}
                  {level.assignee_type === 'role' && (
                    <div className="form-group" style={{ flex: 1.5 }}>
                      <label>Role *</label>
                      <SearchableSelect
                        id={`role-${index}`}
                        name={`role_id_${index}`}
                        value={level.role_id}
                        onChange={val => handleLevelChange(index, 'role_id', val)}
                        options={roleOptions}
                        placeholder="Select role..."
                        required
                      />
                    </div>
                  )}

                  {/* User selector */}
                  {level.assignee_type === 'user' && (
                    <div className="form-group" style={{ flex: 1.5 }}>
                      <label>Assign to *</label>
                      <SearchableSelect
                        id={`user-${index}`}
                        name={`user_id_${index}`}
                        value={level.user_id}
                        onChange={val => handleLevelChange(index, 'user_id', val)}
                        options={userOptions}
                        placeholder="Search by name or email..."
                        required
                      />
                    </div>
                  )}

                  {/* SLA */}
                  <div className="form-group" style={{ flex: 0.5 }}>
                    <label>SLA (hours)</label>
                    <input
                      type="number"
                      min="1"
                      value={level.auto_escalation_sla_hours}
                      onChange={e => handleLevelChange(index, 'auto_escalation_sla_hours', parseInt(e.target.value) || 1)}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>
            ))}

            <div className="ac-form__actions">
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? 'Saving...' : editingChain ? 'Update Chain' : 'Save Chain'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => { setShowForm(false); setEditingChain(null); resetForm() }}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Delete Confirm Dialog */}
      {deleteTarget && (
        <div className="ac-confirm-overlay" onClick={e => { if (e.target === e.currentTarget) setDeleteTarget(null) }}>
          <div className="ac-confirm-dialog">
            <h3 className="ac-confirm-dialog__title">Delete chain "{deleteTarget.name}"?</h3>
            <div className="ac-confirm-dialog__body">
              This cannot be undone. The chain will be deleted unless it is bound to in-flight discrepancies.
            </div>
            <div className="ac-confirm-dialog__actions">
              <button className="btn btn-ghost" onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Chain Card sub-component ─────────────────────────────────────────── */

function ChainCard({
  chain,
  roleLookup,
  userLookup,
  onEdit,
  onToggle,
  onDelete,
}: {
  chain: ApprovalChain
  roleLookup: Map<string, string>
  userLookup: Map<string, string>
  onEdit: (c: ApprovalChain) => void
  onToggle: (c: ApprovalChain) => void
  onDelete: (c: ApprovalChain) => void
}) {
  return (
    <div className={`ac-chain-card ${chain.is_active ? 'ac-chain-card--active' : 'ac-chain-card--inactive'}`}>
      <div className="ac-chain-card__head">
        <div className="ac-chain-card__title-row">
          <h3 className="ac-chain-card__name">{chain.name}</h3>
          <span className={`status ${chain.is_active ? 'status-active' : 'status-inactive'}`}>
            {chain.is_active ? 'Active' : 'Inactive'}
          </span>
          {chain.priority > 0 && (
            <span className="ac-chain-card__priority">P{chain.priority}</span>
          )}
        </div>
        {chain.description && (
          <div className="ac-chain-card__desc">{chain.description}</div>
        )}
        <div className="ac-chain-card__scope">{scopeSummary(chain)}</div>
      </div>

      <div className="ac-levels-table-wrap">
        <table className="ac-levels-table">
          <thead>
            <tr>
              <th>Level</th>
              <th>Approver</th>
              <th>SLA</th>
            </tr>
          </thead>
          <tbody>
            {chain.levels.map((lvl, i) => (
              <tr key={`lvl-${i}`}>
                <td className="cell-level">{lvl.level}</td>
                <td className="cell-role">
                  {lvl.assignee_type === 'user' ? '' : ''}
                  {resolveAssigneeName(lvl, roleLookup, userLookup)}
                </td>
                <td className="cell-sla">
                  {lvl.auto_escalation_sla_hours ? `${lvl.auto_escalation_sla_hours}h` : 'N/A'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="ac-chain-card__footer">
        <span style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)' }}>
          Created: {new Date(chain.created_at).toLocaleDateString()}
        </span>
        <div className="ac-chain-card__actions">
          <button className="btn btn-sm btn-ghost" onClick={() => onEdit(chain)}>Edit</button>
          <button className="btn btn-sm btn-primary" onClick={() => onToggle(chain)}>
            {chain.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button className="btn btn-sm btn-ghost" style={{ color: 'var(--rose-600)' }} onClick={() => onDelete(chain)}>
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

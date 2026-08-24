import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'
import './EscalationRules.css'

interface EscalationRule {
  id: string
  escalation_level: number
  sla_hours: number
  school_id?: string
  school_name?: string
  department_id?: string
  department_name?: string
  escalate_to_role_id?: string
  escalate_to_role_name?: string
  created_at: string
  updated_at: string
}

interface School { id: string; name: string }
interface Department { id: string; name: string }
interface Role { id: string; name: string }

export default function EscalationRules() {
  const [rules, setRules] = useState<EscalationRule[]>([])
  const [schools, setSchools] = useState<School[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const [formData, setFormData] = useState({
    escalation_level: 1,
    sla_hours: 24,
    school_id: '',
    department_id: '',
    escalate_to_role_id: '',
  })

  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchRules()
    fetchSchools()
    fetchRoles()
  }, [])

  useEffect(() => {
    if (formData.school_id) {
      fetchDepartments(formData.school_id)
    } else {
      setDepartments([])
    }
  }, [formData.school_id])

  const fetchRules = async () => {
    try {
      setLoading(true)
      const res = await apiFetch('/api/v1/escalation-rules')
      if (res.ok) {
        setRules(await res.json())
      } else {
        setRules([])
      }
    } catch {
      setRules([])
    } finally {
      setLoading(false)
    }
  }

  const fetchSchools = async () => {
    try {
      const res = await apiFetch('/api/v1/schools?page_size=100')
      if (res.ok) {
        const data = await res.json()
        setSchools(data.data || [])
      }
    } catch { /* ignore */ }
  }

  const fetchDepartments = async (schoolId: string) => {
    try {
      const res = await apiFetch(`/api/v1/departments?school_id=${schoolId}&page_size=100`)
      if (res.ok) {
        const data = await res.json()
        setDepartments(data.data || [])
      }
    } catch { /* ignore */ }
  }

  const fetchRoles = async () => {
    try {
      // Roles endpoint — may need adjustment based on actual API
      const res = await apiFetch('/api/v1/users/roles')
      if (res.ok) {
        const data = await res.json()
        setRoles(data.roles || data || [])
      }
    } catch { /* ignore */ }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const res = await apiFetch('/api/v1/escalation-rules', {
        method: 'POST',
        body: JSON.stringify({
          escalation_level: formData.escalation_level,
          sla_hours: formData.sla_hours,
          school_id: formData.school_id || null,
          department_id: formData.department_id || null,
          escalate_to_role_id: formData.escalate_to_role_id || null,
        }),
      })
      if (!res.ok) {
        const errBody = await res.json().catch(() => null)
        throw new Error(errBody?.error?.message || 'Failed to save rule')
      }
      await fetchRules()
      setShowForm(false)
      setFormData({ escalation_level: 1, sla_hours: 24, school_id: '', department_id: '', escalate_to_role_id: '' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  /** Resolve a rule's display values */
  const resolveRule = (rule: EscalationRule) => ({
    ...rule,
    schoolDisplay: rule.school_name || 'All Schools',
    departmentDisplay: rule.department_name || 'All Departments',
    roleDisplay: rule.escalate_to_role_name || 'Default',
    isFallback: !rule.school_id && !rule.department_id,
  })

  const resolvedRules = rules.map(resolveRule)

  if (loading) return <div className="loading-state">Loading escalation rules…</div>

  return (
    <div className="escalation-rules page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">Policy Configuration</div>
          <h1>Escalation Rules</h1>
        </div>
        <button
          className={`btn ${showForm ? 'btn-ghost' : 'btn-primary'}`}
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? 'Cancel' : '＋ Add Rule'}
        </button>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: '0 0 var(--space-5)' }}>
          <span className="alert-icon">⚠️</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="alert-close">×</button>
        </div>
      )}

      {/* ── Info Banner ──────────────────────────────────────────────── */}
      <div className="escalation-banner">
        <div className="escalation-banner__content">
          <strong>How Escalation Works:</strong> Tasks that exceed their ETA are automatically
          escalated based on these rules. After 4 extension requests (policy R-33/BR-10),
          a task escalates regardless of extension status. Rules are applied most-specific-first:
          a rule scoped to a specific school and department takes precedence over a rule
          scoped to "All Schools."
        </div>
      </div>

      {/* ── Create Rule Form ─────────────────────────────────────────── */}
      {showForm && (
        <form onSubmit={handleSubmit} className="escalation-form">
          <h3 className="escalation-form__title">Create Escalation Rule</h3>

          <div className="escalation-form__grid">
            <div className="form-group">
              <label htmlFor="escalation_level">Escalation Level *</label>
              <input
                id="escalation_level"
                type="number"
                min="1"
                value={formData.escalation_level}
                onChange={(e) => setFormData(prev => ({ ...prev, escalation_level: parseInt(e.target.value) || 1 }))}
                required
                className="escalation-form__input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="sla_hours">SLA Hours *</label>
              <input
                id="sla_hours"
                type="number"
                min="1"
                value={formData.sla_hours}
                onChange={(e) => setFormData(prev => ({ ...prev, sla_hours: parseInt(e.target.value) || 1 }))}
                required
                className="escalation-form__input"
              />
            </div>
          </div>

          <div className="escalation-form__grid">
            <div className="form-group">
              <label htmlFor="school">School</label>
              <SearchableSelect
                id="school"
                name="school_id"
                value={formData.school_id}
                onChange={(val) => setFormData(prev => ({ ...prev, school_id: val, department_id: '' }))}
                options={schools.map(s => ({ value: s.id, label: s.name }))}
                placeholder="All Schools"
                unsetLabel="All Schools"
              />
            </div>

            <div className="form-group">
              <label htmlFor="department">Department</label>
              <SearchableSelect
                id="department"
                name="department_id"
                value={formData.department_id}
                onChange={(val) => setFormData(prev => ({ ...prev, department_id: val }))}
                options={departments.map(d => ({ value: d.id, label: d.name }))}
                placeholder={formData.school_id ? 'All Departments' : 'Select school first'}
                disabled={!formData.school_id}
                unsetLabel="All Departments"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="escalate_to_role">Escalate To Role</label>
            <SearchableSelect
              id="escalate_to_role"
              name="escalate_to_role_id"
              value={formData.escalate_to_role_id}
              onChange={(val) => setFormData(prev => ({ ...prev, escalate_to_role_id: val }))}
              options={roles.map(r => ({ value: r.id, label: r.name.charAt(0).toUpperCase() + r.name.slice(1) }))}
              placeholder="Default"
              unsetLabel="Default"
            />
          </div>

          <div className="escalation-form__actions">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving…' : 'Save Rule'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* ── Rules Table ──────────────────────────────────────────────── */}
      {resolvedRules.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">⚙️</div>
          <h3>No escalation rules configured</h3>
          <p>Add a rule to define how tasks escalate when they exceed their ETA.</p>
        </div>
      ) : (
        <>
          <div className="escalation-order-note">
            Rules shown in creation order — evaluation order not yet confirmed.
          </div>

          <div className="table-wrap escalation-table-wrap">
            <table className="data-table escalation-table">
              <thead>
                <tr>
                  <th>Level</th>
                  <th>SLA</th>
                  <th className="col-scope">Scope</th>
                  <th className="col-role">Escalate To</th>
                  <th className="col-created">Created</th>
                </tr>
              </thead>
              <tbody>
                {resolvedRules.map((rule, i) => (
                  <tr key={`${rule.id}-${i}`} className={rule.isFallback ? 'row--fallback' : ''}>
                    <td className="cell-level">{rule.escalation_level}</td>
                    <td>{rule.sla_hours}h</td>
                    <td className="col-scope">
                      <span className="scope-display">
                        {!rule.school_id && <span className="badge-neutral">All Schools</span>}
                        {rule.school_id && <span>{rule.schoolDisplay}</span>}
                        {rule.school_id && !rule.department_id && <span className="badge-neutral">All Depts</span>}
                        {rule.department_id && <span>{rule.departmentDisplay}</span>}
                      </span>
                    </td>
                    <td className="col-role">
                      {rule.escalate_to_role_id ? (
                        <span>{rule.roleDisplay}</span>
                      ) : (
                        <span className="badge-neutral">Default</span>
                      )}
                    </td>
                    <td className="col-created">
                      {new Date(rule.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked cards */}
          <div className="escalation-mobile-cards">
            {resolvedRules.map((rule, i) => (
              <div key={`${rule.id}-mob-${i}`} className={`escalation-mobile-card ${rule.isFallback ? 'escalation-mobile-card--fallback' : ''}`}>
                <div className="escalation-mobile-card__header">
                  <span className="escalation-mobile-card__level">Level {rule.escalation_level}</span>
                  <span className="escalation-mobile-card__sla">{rule.sla_hours}h SLA</span>
                </div>
                <div className="escalation-mobile-card__body">
                  <div className="escalation-mobile-card__row">
                    <span className="escalation-mobile-card__label">Scope</span>
                    <span className="escalation-mobile-card__value">
                      {!rule.school_id && <span className="badge-neutral">All Schools</span>}
                      {rule.school_id && <span>{rule.schoolDisplay}</span>}
                      {rule.school_id && !rule.department_id && <span className="badge-neutral">All Depts</span>}
                      {rule.department_id && <span>{rule.departmentDisplay}</span>}
                    </span>
                  </div>
                  <div className="escalation-mobile-card__row">
                    <span className="escalation-mobile-card__label">Escalate To</span>
                    <span className="escalation-mobile-card__value">
                      {rule.escalate_to_role_id ? rule.roleDisplay : <span className="badge-neutral">Default</span>}
                    </span>
                  </div>
                  <div className="escalation-mobile-card__row">
                    <span className="escalation-mobile-card__label">Created</span>
                    <span className="escalation-mobile-card__value">
                      {new Date(rule.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

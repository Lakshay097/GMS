import { useState } from 'react'
import { apiFetch } from '../../lib/api'
import { useSchools } from './useOrgData'

interface Props {
  preselectedSchoolId?: string
  onCreated?: (dept: any) => void
  onCancel?: () => void
}

export default function DepartmentForm({ preselectedSchoolId, onCreated, onCancel }: Props) {
  const { schools } = useSchools()
  const [form, setForm] = useState({
    name: '',
    code: '',
    school_id: preselectedSchoolId || '',
    description: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState('')

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!form.name.trim()) errs.name = 'Name is required'
    if (!form.code.trim()) errs.code = 'Code is required'
    if (!form.school_id) errs.school_id = 'School is required'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setServerError('')
    try {
      const res = await apiFetch('/api/v1/departments', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        setServerError(data.detail?.message || 'Failed to create department')
        return
      }
      onCreated?.(data)
    } catch {
      setServerError('Network error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="org-form" style={{ maxWidth: 500 }}>
      <h3>Create Department</h3>
      {serverError && <div className="error-banner">{serverError}</div>}

      <label>
        School *
        <select
          value={form.school_id}
          onChange={e => setForm({ ...form, school_id: e.target.value })}
          className={errors.school_id ? 'field-error' : ''}
          disabled={!!preselectedSchoolId}
        >
          <option value="">Select a school...</option>
          {schools.map(s => (
            <option key={s.id} value={s.id}>{s.name} ({s.code})</option>
          ))}
        </select>
        {errors.school_id && <span className="field-error-text">{errors.school_id}</span>}
      </label>

      <label>
        Name *
        <input
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          className={errors.name ? 'field-error' : ''}
        />
        {errors.name && <span className="field-error-text">{errors.name}</span>}
      </label>

      <label>
        Code *
        <input
          value={form.code}
          onChange={e => setForm({ ...form, code: e.target.value })}
          className={errors.code ? 'field-error' : ''}
        />
        {errors.code && <span className="field-error-text">{errors.code}</span>}
      </label>

      <label>
        Description
        <textarea
          value={form.description}
          onChange={e => setForm({ ...form, description: e.target.value })}
          rows={3}
        />
      </label>

      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create Department'}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="btn-secondary">
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}

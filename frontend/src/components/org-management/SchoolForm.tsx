import { useState } from 'react'
import { apiFetch } from '../../lib/api'

interface Props {
  onCreated?: (school: any) => void
  onCancel?: () => void
}

export default function SchoolForm({ onCreated, onCancel }: Props) {
  const [form, setForm] = useState({
    name: '',
    code: '',
    address: '',
    contact_email: '',
    contact_phone: '',
    timezone: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState('')

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!form.name.trim()) errs.name = 'Name is required'
    if (!form.code.trim()) errs.code = 'Code is required'
    if (form.contact_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.contact_email)) {
      errs.contact_email = 'Invalid email'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setServerError('')
    try {
      const res = await apiFetch('/api/v1/schools', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        setServerError(data.detail?.message || 'Failed to create school')
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
      <h3>Create School</h3>
      {serverError && <div className="error-banner">{serverError}</div>}

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
        Address
        <input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} />
      </label>

      <label>
        Contact Email
        <input
          type="email"
          value={form.contact_email}
          onChange={e => setForm({ ...form, contact_email: e.target.value })}
          className={errors.contact_email ? 'field-error' : ''}
        />
        {errors.contact_email && <span className="field-error-text">{errors.contact_email}</span>}
      </label>

      <label>
        Contact Phone
        <input value={form.contact_phone} onChange={e => setForm({ ...form, contact_phone: e.target.value })} />
      </label>

      <label>
        Timezone
        <input
          value={form.timezone}
          onChange={e => setForm({ ...form, timezone: e.target.value })}
          placeholder="e.g. Asia/Kolkata"
        />
      </label>

      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create School'}
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

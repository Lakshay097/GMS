import { useState } from 'react'
import { apiFetch } from '../../lib/api'

interface Props {
  onCreated?: (kra: any) => void
  onCancel?: () => void
}

export default function KraForm({ onCreated, onCancel }: Props) {
  const [form, setForm] = useState({ name: '', description: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState('')

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!form.name.trim()) errs.name = 'Name is required'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setServerError('')
    try {
      const res = await apiFetch('/api/v1/kras', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        setServerError(data.detail?.message || 'Failed to create KRA')
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
      <h3>Create KRA</h3>
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
        Description
        <textarea
          value={form.description}
          onChange={e => setForm({ ...form, description: e.target.value })}
          rows={3}
        />
      </label>

      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create KRA'}
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

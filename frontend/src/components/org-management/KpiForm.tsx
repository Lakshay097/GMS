import { useState } from 'react'
import { apiFetch } from '../../lib/api'
import { useKras } from './useOrgData'

interface Props {
  preselectedKraId?: string
  onCreated?: (kpi: any) => void
  onCancel?: () => void
}

export default function KpiForm({ preselectedKraId, onCreated, onCancel }: Props) {
  const { kras } = useKras()
  const [form, setForm] = useState({
    kra_id: preselectedKraId || '',
    title: '',
    description: '',
    target_value: '100',
    comparator: '>=',
    unit_of_measure: 'percent',
    frequency_code: 'daily',
    capture_type: 'value_reading',
    is_sensitive: false,
    evidence_required: false,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState('')

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!form.kra_id) errs.kra_id = 'KRA is required'
    if (!form.title.trim()) errs.title = 'Title is required'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setServerError('')
    try {
      const res = await apiFetch('/api/v1/kpis', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          target_value: parseFloat(form.target_value) || 100,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setServerError(data.detail?.message || 'Failed to create KPI')
        return
      }
      onCreated?.(data)
    } catch {
      setServerError('Network error')
    } finally {
      setSubmitting(false)
    }
  }

  const update = (field: string, value: any) => setForm({ ...form, [field]: value })

  return (
    <form onSubmit={handleSubmit} className="org-form" style={{ maxWidth: 600 }}>
      <h3>Create KPI</h3>
      {serverError && <div className="error-banner">{serverError}</div>}

      <label>
        KRA *
        <select
          value={form.kra_id}
          onChange={e => update('kra_id', e.target.value)}
          className={errors.kra_id ? 'field-error' : ''}
          disabled={!!preselectedKraId}
        >
          <option value="">Select a KRA...</option>
          {kras.map(k => (
            <option key={k.id} value={k.id}>{k.name}</option>
          ))}
        </select>
        {errors.kra_id && <span className="field-error-text">{errors.kra_id}</span>}
      </label>

      <label>
        Title *
        <input
          value={form.title}
          onChange={e => update('title', e.target.value)}
          className={errors.title ? 'field-error' : ''}
        />
        {errors.title && <span className="field-error-text">{errors.title}</span>}
      </label>

      <label>
        Description
        <textarea value={form.description} onChange={e => update('description', e.target.value)} rows={2} />
      </label>

      <div className="form-row">
        <label>
          Target Value
          <input
            type="number"
            value={form.target_value}
            onChange={e => update('target_value', e.target.value)}
          />
        </label>

        <label>
          Comparator
          <select value={form.comparator} onChange={e => update('comparator', e.target.value)}>
            <option value=">=">&gt;=</option>
            <option value="<=">&lt;=</option>
            <option value="=">=</option>
            <option value=">">&gt;</option>
            <option value="<">&lt;</option>
          </select>
        </label>

        <label>
          Unit
          <input
            value={form.unit_of_measure}
            onChange={e => update('unit_of_measure', e.target.value)}
            placeholder="percent, count, etc."
          />
        </label>
      </div>

      <div className="form-row">
        <label>
          Frequency
          <select value={form.frequency_code} onChange={e => update('frequency_code', e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>

        <label>
          Capture Type
          <select value={form.capture_type} onChange={e => update('capture_type', e.target.value)}>
            <option value="value_reading">Value Reading</option>
            <option value="check">Check (Done / Not Done)</option>
            <option value="event_time">Event Time</option>
            <option value="value_and_event_time">Value + Event Time</option>
          </select>
        </label>
      </div>

      <div className="form-checkboxes">
        <label>
          <input
            type="checkbox"
            checked={form.is_sensitive}
            onChange={e => update('is_sensitive', e.target.checked)}
          />
          Sensitive (requires approval)
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.evidence_required}
            onChange={e => update('evidence_required', e.target.checked)}
          />
          Evidence Required
        </label>
      </div>

      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create KPI'}
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

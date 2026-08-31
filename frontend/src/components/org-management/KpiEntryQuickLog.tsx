import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'
import { useSchools, useDepartments, useKras, useKpis } from './useOrgData'

interface Props {
  onCreated?: (entry: any) => void
  preselectedKpiId?: string
}

/**
 * Quick-log form for KPI entries.
 * Mobile-friendly: minimal required fields, auto-fills context.
 * Cascading dropdowns: school → department, KRA → KPI.
 */
export default function KpiEntryQuickLog({ onCreated, preselectedKpiId }: Props) {
  const { schools } = useSchools()
  const [selectedSchoolId, setSelectedSchoolId] = useState<string>('')
  const { departments } = useDepartments(selectedSchoolId || null)
  const { kras } = useKras()
  const [selectedKraId, setSelectedKraId] = useState<string>('')
  const { kpis } = useKpis(selectedKraId || null)

  const [form, setForm] = useState({
    kpi_id: preselectedKpiId || '',
    check_name: '',
    check_type: 'daily_inspection',
    value: '',
    value_text: '',
    asset_id: '',
    department_id: '',
    school_id: '',
    notes: '',
  })

  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState('')
  const [success, setSuccess] = useState(false)

  // Auto-fill school/department from selected KPI context
  useEffect(() => {
    if (form.school_id) setSelectedSchoolId(form.school_id)
  }, [form.school_id])

  // Auto-set department_id when school changes
  useEffect(() => {
    if (selectedSchoolId && !form.department_id) {
      setForm(f => ({ ...f, school_id: selectedSchoolId }))
    }
  }, [selectedSchoolId])

  // Find the selected KPI to show its target
  const selectedKpi = kpis.find(k => k.kpi_id === form.kpi_id)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.kpi_id) {
      setServerError('Please select a KPI')
      return
    }
    setSubmitting(true)
    setServerError('')
    setSuccess(false)
    try {
      const body: any = {
        kpi_id: form.kpi_id,
        check_name: form.check_name || undefined,
        check_type: form.check_type || undefined,
        value: form.value ? parseFloat(form.value) : undefined,
        value_text: form.value_text || undefined,
        notes: form.notes || undefined,
        department_id: form.department_id || undefined,
        school_id: form.school_id || undefined,
        asset_id: form.asset_id || undefined,
      }
      const res = await apiFetch('/api/v1/kpi-entries', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        setServerError(data.detail?.message || 'Failed to log entry')
        return
      }
      setSuccess(true)
      // Reset form
      setForm(f => ({
        ...f,
        check_name: '',
        value: '',
        value_text: '',
        notes: '',
      }))
      onCreated?.(data)
    } catch {
      setServerError('Network error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="org-form kpi-quick-log" style={{ maxWidth: 500 }}>
      <h3>Log a Check</h3>
      {serverError && <div className="error-banner">{serverError}</div>}
      {success && <div className="success-banner">Entry logged successfully!</div>}

      {/* Cascading: School → Department */}
      <div className="form-row">
        <label>
          School
          <select value={form.school_id} onChange={e => {
            setForm(f => ({ ...f, school_id: e.target.value, department_id: '' }))
            setSelectedSchoolId(e.target.value)
          }}>
            <option value="">All schools</option>
            {schools.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>

        <label>
          Department
          <select
            value={form.department_id}
            onChange={e => setForm(f => ({ ...f, department_id: e.target.value }))}
            disabled={!selectedSchoolId}
          >
            <option value="">All departments</option>
            {departments.map(d => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Cascading: KRA → KPI */}
      <label>
        KRA
        <select value={selectedKraId} onChange={e => {
          setSelectedKraId(e.target.value)
          setForm(f => ({ ...f, kpi_id: '' }))
        }}>
          <option value="">All KRAs</option>
          {kras.map(k => (
            <option key={k.id} value={k.id}>{k.name}</option>
          ))}
        </select>
      </label>

      <label>
        KPI *
        <select
          value={form.kpi_id}
          onChange={e => setForm(f => ({ ...f, kpi_id: e.target.value }))}
          className={!form.kpi_id ? 'field-error' : ''}
        >
          <option value="">Select a KPI...</option>
          {kpis.map(k => (
            <option key={k.kpi_id} value={k.kpi_id}>
              {k.title} ({k.comparator} {k.target_value} {k.unit_of_measure})
            </option>
          ))}
        </select>
      </label>

      {selectedKpi && (
        <div className="kpi-target-info">
          Target: {selectedKpi.comparator} {selectedKpi.target_value} {selectedKpi.unit_of_measure}
          {selectedKpi.is_sensitive && <span className="badge badge-amber">Sensitive</span>}
          {selectedKpi.evidence_required && <span className="badge badge-blue">Evidence Required</span>}
        </div>
      )}

      <label>
        Check Name
        <input
          value={form.check_name}
          onChange={e => setForm(f => ({ ...f, check_name: e.target.value }))}
          placeholder="e.g. Morning Inspection — Block A"
        />
      </label>

      <label>
        Check Type
        <select value={form.check_type} onChange={e => setForm(f => ({ ...f, check_type: e.target.value }))}>
          <option value="daily_inspection">Daily Inspection</option>
          <option value="weekly_audit">Weekly Audit</option>
          <option value="monthly_review">Monthly Review</option>
          <option value="spot_check">Spot Check</option>
          <option value="scheduled_maintenance">Scheduled Maintenance</option>
        </select>
      </label>

      <div className="form-row">
        <label>
          Value (numeric)
          <input
            type="number"
            step="0.01"
            value={form.value}
            onChange={e => setForm(f => ({ ...f, value: e.target.value }))}
            placeholder="e.g. 97.5"
          />
        </label>

        <label>
          Or Text Value
          <input
            value={form.value_text}
            onChange={e => setForm(f => ({ ...f, value_text: e.target.value }))}
            placeholder="Free text if applicable"
          />
        </label>
      </div>

      <label>
        Notes
        <textarea
          value={form.notes}
          onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
          rows={2}
          placeholder="Optional observations..."
        />
      </label>

      <div className="form-actions">
        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? 'Logging...' : 'Log Check'}
        </button>
      </div>
    </form>
  )
}

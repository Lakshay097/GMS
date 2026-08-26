import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useUser } from '@clerk/clerk-react'
import { apiFetch } from '../../lib/api'
import { useSchoolContext } from '../../contexts/SchoolContext'
import SearchableSelect from '../common/SearchableSelect'
import './ObservationForm.css'

/* ── Types ─────────────────────────────────────────────────────────────── */

interface ObservationFormData {
  school_id: string
  department_id: string
  observation_date: string
  title: string
  description: string
  category_id: string
  status: string
}


interface Department {
  id: string
  name: string
}

/* ── Component ─────────────────────────────────────────────────────────── */

export default function ObservationForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useUser()
  const isEditing = !!id

  const [formData, setFormData] = useState<ObservationFormData>({
    school_id: '',
    department_id: '',
    observation_date: new Date().toISOString().slice(0, 10),
    title: '',
    description: '',
    category_id: '',
    status: 'draft',
  })

  // ── Active school from global context ──────────────────────────────────
  const { activeSchoolId, activeSchool } = useSchoolContext()

  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Auto-sync school from global context (updates if SuperAdmin switches school)
  useEffect(() => {
    if (activeSchoolId && activeSchoolId !== formData.school_id) {
      setFormData(prev => ({ ...prev, school_id: activeSchoolId, department_id: '' }))
    }
  }, [activeSchoolId])

  /* ── Data fetching ──────────────────────────────────────────────────── */

  useEffect(() => {
    if (isEditing) fetchObservation()
  }, [id])

  useEffect(() => {
    if (formData.school_id) {
      fetchDepartments(formData.school_id)
    } else {
      setDepartments([])
    }
  }, [formData.school_id])

  const fetchDepartments = async (schoolId: string) => {
    try {
      const res = await apiFetch(
        `/api/v1/departments?school_id=${schoolId}&page_size=100`,
      )
      if (res.ok) {
        const data = await res.json()
        setDepartments(data.data || [])
      }
    } catch {
      /* ignore */
    }
  }

  const fetchObservation = async () => {
    try {
      setLoading(true)
      const res = await apiFetch(`/api/v1/observations/${id}`)
      if (!res.ok) throw new Error('Failed to fetch observation')
      const obs = await res.json()

      setFormData({
        school_id: obs.school_id || '',
        department_id: obs.department_id || '',
        observation_date: obs.observation_date
          ? obs.observation_date.slice(0, 10)
          : obs.submitted_at
            ? obs.submitted_at.slice(0, 10)
            : new Date().toISOString().slice(0, 10),
        title: obs.title || '',
        description: obs.description || obs.value_text || '',
        category_id: obs.category_id || '',
        status: obs.status || 'draft',
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  /* ── Submit ─────────────────────────────────────────────────────────── */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const payload: Record<string, unknown> = {
        school_id: formData.school_id,
        department_id: formData.department_id || null,
        observation_date: new Date(formData.observation_date).toISOString(),
        title: formData.title || null,
        description: formData.description,
        category_id: formData.category_id || null,
        status: formData.status,
      }

      // On create, include the checker (current user) as observed_by
      if (!isEditing && user?.id) {
        payload.observed_by_user_id = user.id
      }

      const url = isEditing
        ? `/api/v1/observations/${id}`
        : '/api/v1/observations'
      const method = isEditing ? 'PATCH' : 'POST'

      const res = await apiFetch(url, {
        method,
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errBody = await res.json().catch(() => null)
        throw new Error(
          errBody?.error?.message || errBody?.detail || 'Failed to save observation',
        )
      }

      navigate('/observations')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  /* ── Helpers ────────────────────────────────────────────────────────── */

  const departmentOptions = departments.map((d) => ({
    value: d.id,
    label: d.name,
  }))

  if (loading) return <div className="loading-state">Loading…</div>

  /* ── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="observation-form page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <button
            onClick={() => navigate('/observations')}
            className="btn btn-ghost btn-sm"
            style={{ marginBottom: 'var(--space-2)' }}
          >
            ← Observations
          </button>
          <h1>{isEditing ? 'Edit Observation' : 'Create Observation'}</h1>
        </div>
      </div>

      {/* ── Error alert ──────────────────────────────────────────────── */}
      {error && (
        <div
          className="obs-form-alert obs-form-alert--error"
          style={{ margin: '0 var(--space-10) var(--space-5)' }}
        >
          <span className="obs-form-alert__icon">⚠️</span>
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="obs-form-alert__close"
          >
            ×
          </button>
        </div>
      )}

      {/* ── Form Card ────────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} className="obs-form-card">

        {/* ── Info Banner ──────────────────────────────────────────── */}
        <div className="obs-info-banner">
          <strong>Important:</strong> Once submitted, observations can only be
          verified or rejected by authorized users. Auditors can raise
          discrepancies against submitted observations.
        </div>

        {/* ── School (auto-set from global context, no manual picker) ──── */}
        {formData.school_id && (
          <div className="form-group">
            <label>School</label>
            <input type="hidden" name="school_id" value={formData.school_id} />
            <div style={{
              padding: '8px 12px', background: 'var(--ink-800)', borderRadius: 8,
              color: 'var(--ink-200)', fontSize: 'var(--text-sm)', fontWeight: 500,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ opacity: 0.5 }}>🏫</span>
              {activeSchool?.name || 'Loading…'}
            </div>
          </div>
        )}

        {/* ── Department (searchable, dependent on School) ──────────── */}
        <div className="form-group">
          <label htmlFor="department">Department</label>
          <SearchableSelect
            id="department"
            name="department_id"
            value={formData.department_id}
            onChange={(val) =>
              setFormData((prev) => ({ ...prev, department_id: val }))
            }
            options={departmentOptions}
            placeholder={
              formData.school_id ? 'Select department…' : 'Select school first'
            }
            disabled={!formData.school_id}
            unsetLabel="Clear"
          />
        </div>

        {/* ── Observation Date (required) ──────────────────────────── */}
        <div className="form-group">
          <label htmlFor="observation_date">Observation Date *</label>
          <input
            id="observation_date"
            type="date"
            value={formData.observation_date}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                observation_date: e.target.value,
              }))
            }
            required
            className="form-group__input"
          />
        </div>

        {/* ── Title (optional) ─────────────────────────────────────── */}
        <div className="form-group">
          <label htmlFor="title">Title</label>
          <input
            id="title"
            type="text"
            value={formData.title}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, title: e.target.value }))
            }
            placeholder="Brief observation title"
            maxLength={255}
            className="form-group__input"
          />
        </div>

        {/* ── Description (required, textarea 4 rows) ──────────────── */}
        <div className="form-group">
          <label htmlFor="description">Description *</label>
          <textarea
            id="description"
            value={formData.description}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                description: e.target.value,
              }))
            }
            rows={4}
            required
            placeholder="Detailed description of the observation…"
            className="form-group__input form-group__textarea"
          />
        </div>

        {/* ── Category (disabled — pending #13 lookup resolution) ─── */}
        <div className="form-group">
          <label htmlFor="category_id">
            Category
            <span
              className="field-note"
              title="Category selection unavailable — pending configuration"
            >
              🔒 Unavailable
            </span>
          </label>
          <SearchableSelect
            id="category_id"
            name="category_id"
            value={formData.category_id}
            onChange={() => {}}
            options={[]}
            placeholder="Category selection unavailable"
            disabled
            unsetLabel=""
          />
          <span className="form-group__hint">
            Category selection unavailable — pending configuration
          </span>
        </div>

        {/* ── Status ────────────────────────────────────────────────── */}
        <div className="form-group">
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={formData.status}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, status: e.target.value }))
            }
            className="form-group__input"
          >
            <option value="draft">Draft</option>
            <option value="pending">Submitted</option>
            <option value="verified">Verified</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        {/* ── Footer ────────────────────────────────────────────────── */}
        <div className="obs-form-actions">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => navigate('/observations')}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
          >
            {submitting ? 'Saving…' : 'Save Observation'}
          </button>
        </div>
      </form>
    </div>
  )
}

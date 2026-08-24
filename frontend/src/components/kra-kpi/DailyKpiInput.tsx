import { useState, useEffect, useRef, useMemo } from 'react'
import { useUser } from '@clerk/clerk-react'
import { useKpiContext } from '../../contexts/KpiContext'
import { apiFetch } from '../../lib/api'
import './DailyKpiInput.css'

interface KpiAssignment {
  id: string
  kpi_id: string
  kpi_title: string
  kpi_target_value: string
  kpi_unit: string
  kpi_comparator: string
  department_id: string
  department_name: string
  frequency_code: string
  capture_type: string
  last_submission_date?: string
  data_type?: 'numeric' | 'boolean' | 'text'
  version?: number
}

interface KpiInput {
  kpi_id: string
  value: string
  value_numeric?: number
  value_boolean?: boolean
  notes: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function determineDataType(unit: string): 'numeric' | 'boolean' | 'text' {
  const unitLower = unit.toLowerCase()
  if (unitLower === 'yes/no' || unitLower === 'yes-no' || unitLower === 'boolean') return 'boolean'
  if (unitLower === 'text' || unitLower === 'description' || unitLower === 'notes') return 'text'
  return 'numeric'
}

function isInputValid(input: KpiInput | undefined, dataType?: string): boolean {
  if (!input) return false
  if (dataType === 'boolean') return input.value_boolean !== undefined
  if (dataType === 'text') return input.value.trim().length > 0
  return input.value.trim().length > 0
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DailyKpiInput() {
  const { user } = useUser()
  const { kpis, loading: kpisLoading } = useKpiContext()
  const [assignments, setAssignments] = useState<KpiAssignment[]>([])
  const [inputs, setInputs] = useState<Record<string, KpiInput>>({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])
  const [notesOpen, setNotesOpen] = useState<Record<string, boolean>>({})
  const [submittedKpis, setSubmittedKpis] = useState<Set<string>>(new Set())
  const [clearDraftConfirm, setClearDraftConfirm] = useState(false)
  const [userDepartmentId, setUserDepartmentId] = useState<string | null>(null)
  const [userDepartmentName, setUserDepartmentName] = useState<string | null>(null)
  const [userSchoolId, setUserSchoolId] = useState<string | null>(null)

  const DRAFT_KEY = `kpi-draft-${selectedDate}`
  const hasLoadedDraft = useRef(false)

  // ── Date change handler ───────────────────────────────────────────────────
  const handleDateChange = (newDate: string) => {
    localStorage.removeItem(DRAFT_KEY)
    setSelectedDate(newDate)
    const clearedInputs: Record<string, KpiInput> = {}
    Object.keys(inputs).forEach(id => {
      clearedInputs[id] = { kpi_id: id, value: '', value_boolean: undefined, notes: '' }
    })
    setInputs(clearedInputs)
    hasLoadedDraft.current = false
  }

  // ── Draft persistence ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!loading && !kpisLoading && assignments.length > 0 && !hasLoadedDraft.current) {
      const savedDraft = localStorage.getItem(DRAFT_KEY)
      if (savedDraft) {
        try {
          const draft = JSON.parse(savedDraft)
          if (draft.inputs) {
            const restoredInputs: Record<string, KpiInput> = {}
            assignments.forEach(assignment => {
              restoredInputs[assignment.kpi_id] = draft.inputs[assignment.kpi_id] || {
                kpi_id: assignment.kpi_id, value: '', value_boolean: undefined, notes: '',
              }
            })
            setInputs(restoredInputs)
          }
        } catch (err) {
          console.error('Failed to load draft:', err)
        }
      }
      hasLoadedDraft.current = true
    }
  }, [loading, kpisLoading, assignments.length, DRAFT_KEY])

  useEffect(() => {
    if (Object.keys(inputs).length > 0) {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ inputs }))
    }
  }, [inputs, DRAFT_KEY])

  const clearDraft = () => {
    localStorage.removeItem(DRAFT_KEY)
    const clearedInputs: Record<string, KpiInput> = {}
    assignments.forEach(assignment => {
      clearedInputs[assignment.kpi_id] = {
        kpi_id: assignment.kpi_id, value: '', value_boolean: undefined, notes: '',
      }
    })
    setInputs(clearedInputs)
    setSubmittedKpis(new Set())
    setNotesOpen({})
    hasLoadedDraft.current = false
    setClearDraftConfirm(false)
  }

  // ── Auto-dismiss alerts after 5s ─────────────────────────────────────────
  useEffect(() => {
    if (!error) return
    const timer = setTimeout(() => setError(null), 5000)
    return () => clearTimeout(timer)
  }, [error])

  useEffect(() => {
    if (!success) return
    const timer = setTimeout(() => setSuccess(null), 5000)
    return () => clearTimeout(timer)
  }, [success])

  // ── Fetch user department ─────────────────────────────────────────────────
  useEffect(() => {
    const fetchUserDepartment = async () => {
      try {
        const res = await apiFetch('/auth/get-session')
        if (!res.ok) return
        const data = await res.json()
        if (data.user) {
          if (data.user.department_id) setUserDepartmentId(data.user.department_id)
          if (data.user.department_name) setUserDepartmentName(data.user.department_name)
          if (data.user.school_id) setUserSchoolId(data.user.school_id)
        }
      } catch (err) {
        console.error('Failed to fetch user department:', err)
      }
    }
    fetchUserDepartment()
  }, [])

  // ── Process KPIs into assignments ─────────────────────────────────────────
  useEffect(() => {
    if (!kpisLoading && kpis.length > 0) {
      const newAssignments: KpiAssignment[] = kpis.map((kpi: any) => ({
        id: kpi.kpi_id,
        kpi_id: kpi.kpi_id,
        kpi_title: kpi.title,
        kpi_target_value: kpi.target_value,
        kpi_unit: kpi.unit_of_measure,
        kpi_comparator: kpi.comparator,
        department_id: userDepartmentId || kpi.suggested_department || 'general',
        department_name: userDepartmentName || kpi.suggested_department || 'General',
        frequency_code: kpi.frequency_code,
        capture_type: kpi.capture_type,
        data_type: determineDataType(kpi.unit_of_measure),
        version: kpi.version || 1,
        last_submission_date: undefined,
      }))
      setAssignments(newAssignments)

      const initialInputs: Record<string, KpiInput> = {}
      newAssignments.forEach(a => {
        initialInputs[a.kpi_id] = { kpi_id: a.kpi_id, value: '', value_boolean: undefined, notes: '' }
      })
      setInputs(initialInputs)
      setLoading(false)
    }
  }, [kpisLoading, kpis, userDepartmentId, userDepartmentName])

  // ── Progress calculation ──────────────────────────────────────────────────
  const progress = useMemo(() => {
    const total = assignments.length
    const submitted = assignments.filter(a => submittedKpis.has(a.kpi_id)).length
    const ready = assignments.filter(a => isInputValid(inputs[a.kpi_id], a.data_type) && !submittedKpis.has(a.kpi_id)).length
    return { total, submitted, ready }
  }, [assignments, inputs, submittedKpis])

  // ── Input handlers ────────────────────────────────────────────────────────
  const handleInputChange = (kpiId: string, field: 'value' | 'notes' | 'value_boolean', value: string | boolean) => {
    setInputs(prev => ({
      ...prev,
      [kpiId]: { ...prev[kpiId], [field]: value },
    }))
  }

  const toggleNotes = (kpiId: string) => {
    setNotesOpen(prev => ({ ...prev, [kpiId]: !prev[kpiId] }))
  }

  // ── Per-card submit ───────────────────────────────────────────────────────
  const handleSubmit = async (kpiId: string) => {
    const input = inputs[kpiId]
    const assignment = assignments.find(a => a.kpi_id === kpiId)
    if (!input || !assignment) return

    if (!isInputValid(input, assignment.data_type)) {
      setError('Please fill in a valid value before submitting')
      return
    }

    setSubmitting(true)
    setError(null)
    setSuccess(null)

    try {
      const payload: any = buildPayload(assignment, input, kpiId)
      const idempotencyKey = `${kpiId}-${selectedDate}-${user?.id || 'anon'}-${Date.now()}`

      const res = await apiFetch('/api/v1/observations', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Failed to submit observation')
      }

      setSuccess('KPI value submitted successfully')
      setSubmittedKpis(prev => new Set([...prev, kpiId]))
      setNotesOpen(prev => ({ ...prev, [kpiId]: false }))
      localStorage.removeItem(DRAFT_KEY)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit KPI value')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Bulk submit (valid-only) ──────────────────────────────────────────────
  const handleSubmitAll = async () => {
    const validInputs = Object.entries(inputs).filter(([kpiId, input]) => {
      const assignment = assignments.find(a => a.kpi_id === kpiId)
      return isInputValid(input, assignment?.data_type)
    })

    if (validInputs.length === 0) {
      setError('No valid entries to submit. Fill in at least one KPI value.')
      return
    }

    setSubmitting(true)
    setError(null)
    setSuccess(null)

    try {
      const submissions = validInputs.map(([kpiId, input]) => {
        const assignment = assignments.find(a => a.kpi_id === kpiId)!
        const payload = buildPayload(assignment, input, kpiId)
        const idempotencyKey = `${kpiId}-${selectedDate}-${user?.id || 'anon'}-${Date.now()}`

        return apiFetch('/api/v1/observations', {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        })
      })

      const results = await Promise.allSettled(submissions)
      const failed = results.filter(r => r.status === 'rejected')

      if (failed.length > 0 && failed.length < validInputs.length) {
        setSuccess(`${validInputs.length - failed.length} submitted, ${failed.length} failed`)
      } else if (failed.length > 0) {
        throw new Error(`${failed.length} submission(s) failed`)
      } else {
        setSuccess(`${validInputs.length} KPI values submitted successfully`)
      }

      // Mark submitted KPIs as done, keep unsubmitted ones intact
      const submittedIds = new Set(validInputs.map(([kpiId]) => kpiId))
      setSubmittedKpis(prev => new Set([...prev, ...submittedIds]))
      localStorage.removeItem(DRAFT_KEY)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit some KPI values')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Build observation payload ─────────────────────────────────────────────
  function buildPayload(assignment: KpiAssignment, input: KpiInput, kpiId: string) {
    const payload: any = {
      kpi_id: kpiId,
      kpi_version: assignment.version || 1,
      checker_id: user?.id,
      department_id: userDepartmentId || assignment.department_id,
      school_id: userSchoolId || null,
      value_text: input.notes,
      submission_date: selectedDate,
    }

    if (assignment.data_type === 'boolean') {
      payload.value_numeric = input.value_boolean ? 1 : 0
      payload.value_text = input.value_boolean ? 'Yes' : 'No'
    } else if (assignment.data_type === 'text') {
      payload.value_text = input.value
    } else {
      payload.value_numeric = parseFloat(input.value)
    }

    return payload
  }

  // ── Loading / empty states ───────────────────────────────────────────────
  if (loading) {
    return (
      <div className="daily-kpi-input page-shell">
        <div className="loading-state">
          <p>Loading your KPI assignments…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="daily-kpi-input page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">KPI Entry</div>
          <h1>Daily KPI Entry</h1>
        </div>
        <div className="header-actions">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => handleDateChange(e.target.value)}
            className="date-picker"
            max={new Date().toISOString().split('T')[0]}
          />
          {clearDraftConfirm ? (
            <span className="inline-confirm">
              <span className="inline-confirm__text">Clear all unsaved entries?</span>
              <button onClick={clearDraft} disabled={submitting} className="btn btn-sm btn-danger">
                Yes, clear
              </button>
              <button onClick={() => setClearDraftConfirm(false)} disabled={submitting} className="btn btn-sm btn-ghost">
                Cancel
              </button>
            </span>
          ) : (
            <button onClick={() => setClearDraftConfirm(true)} disabled={submitting} className="btn btn-ghost btn-sm">
              Clear Draft
            </button>
          )}
        </div>
      </div>

      {/* ── Alerts ────────────────────────────────────────────────────── */}
      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="alert-close">×</button>
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <span className="alert-icon">✓</span>
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="alert-close">×</button>
        </div>
      )}

      {assignments.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>No KPIs Assigned</h3>
          <p>You don't have any KPIs assigned to your department yet.</p>
          <p className="empty-hint">Contact your administrator to get KPI assignments.</p>
        </div>
      ) : (
        <>
          {/* ── Progress Indicator ──────────────────────────────────────── */}
          <div className="progress-indicator">
            <span className="progress-text">
              <span className="progress-count">{progress.submitted}</span> of {progress.total} submitted today
            </span>
            <div className="progress-bar-track">
              <div
                className="progress-bar-fill"
                style={{ width: `${progress.total > 0 ? (progress.submitted / progress.total) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* ── KPI Input Cards ─────────────────────────────────────────── */}
          <div className="kpi-input-grid">
            {assignments.map(assignment => {
              const input = inputs[assignment.kpi_id] || { value: '', value_boolean: undefined, notes: '' }
              const valid = isInputValid(input, assignment.data_type)
              const submitted = submittedKpis.has(assignment.kpi_id)
              const showNotes = !!notesOpen[assignment.kpi_id]

              return (
                <div key={assignment.id} className={`kpi-input-card ${submitted ? 'kpi-input-card--submitted' : ''}`}>

                  {/* Status badge */}
                  <span className={`kpi-input-card__status ${submitted ? 'kpi-input-card__status--submitted' : valid ? 'kpi-input-card__status--ready' : 'kpi-input-card__status--not-submitted'}`}>
                    {submitted ? 'Submitted' : valid ? 'Ready' : 'Not submitted'}
                  </span>

                  {/* Card header */}
                  <div className="kpi-input-card__header">
                    <div className="kpi-input-card__title">
                      <h3>{assignment.kpi_title}</h3>
                      <div className="kpi-input-card__meta">
                        <span>{assignment.department_name}</span>
                        <span className="freq-badge">{assignment.frequency_code}</span>
                      </div>
                    </div>
                    <div className="kpi-input-card__target">
                      <span className="target-label">Target:</span>
                      <span className="target-value">
                        {assignment.kpi_comparator} {assignment.kpi_target_value} {assignment.kpi_unit}
                      </span>
                    </div>
                  </div>

                  {/* Card body */}
                  <div className="kpi-input-card__body">
                    {assignment.data_type === 'boolean' ? (
                      <div className="input-group">
                        <label>Value ({assignment.kpi_unit})</label>
                        <div className="boolean-segmented">
                          <button
                            type="button"
                            className={`boolean-segmented-btn ${input.value_boolean === true ? 'active' : ''}`}
                            onClick={() => handleInputChange(assignment.kpi_id, 'value_boolean', true)}
                            disabled={submitting}
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            className={`boolean-segmented-btn ${input.value_boolean === false ? 'active' : ''}`}
                            onClick={() => handleInputChange(assignment.kpi_id, 'value_boolean', false)}
                            disabled={submitting}
                          >
                            No
                          </button>
                        </div>
                      </div>
                    ) : assignment.data_type === 'text' ? (
                      <div className="input-group">
                        <label htmlFor={`value-${assignment.kpi_id}`}>
                          Value ({assignment.kpi_unit})
                        </label>
                        <textarea
                          id={`value-${assignment.kpi_id}`}
                          value={input.value}
                          onChange={(e) => handleInputChange(assignment.kpi_id, 'value', e.target.value)}
                          placeholder={`Enter ${assignment.kpi_unit}…`}
                          rows={3}
                          className="input-field textarea"
                          disabled={submitting}
                        />
                      </div>
                    ) : (
                      <div className="input-group">
                        <label htmlFor={`value-${assignment.kpi_id}`}>
                          Value ({assignment.kpi_unit})
                        </label>
                        <input
                          id={`value-${assignment.kpi_id}`}
                          type="number"
                          step="0.01"
                          value={input.value}
                          onChange={(e) => handleInputChange(assignment.kpi_id, 'value', e.target.value)}
                          placeholder={`Enter value in ${assignment.kpi_unit}`}
                          className="input-field"
                          disabled={submitting}
                        />
                      </div>
                    )}

                    {/* Notes — collapsed by default */}
                    {!showNotes ? (
                      <button
                        type="button"
                        className="notes-toggle"
                        onClick={() => toggleNotes(assignment.kpi_id)}
                      >
                        ＋ Add note
                      </button>
                    ) : (
                      <div className="notes-collapse-enter">
                        <div className="input-group">
                          <label htmlFor={`notes-${assignment.kpi_id}`}>Notes (optional)</label>
                          <textarea
                            id={`notes-${assignment.kpi_id}`}
                            value={input.notes}
                            onChange={(e) => handleInputChange(assignment.kpi_id, 'notes', e.target.value)}
                            placeholder="Add any notes or context…"
                            rows={2}
                            className="input-field textarea"
                            disabled={submitting}
                          />
                        </div>
                      </div>
                    )}

                    {/* Per-card submit */}
                    <div className="kpi-input-card__actions">
                      {submitted ? (
                        <span className="kpi-input-card__submitted-label">✓ Submitted</span>
                      ) : (
                        <button
                          onClick={() => handleSubmit(assignment.kpi_id)}
                          disabled={!valid || submitting}
                          className="btn btn-primary btn-sm"
                        >
                          {submitting ? 'Submitting…' : 'Submit'}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Footer — last submission */}
                  {assignment.last_submission_date && (
                    <div className="kpi-input-card__footer">
                      <span className="last-submission">
                        Last submitted: {new Date(assignment.last_submission_date).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* ── Sticky Bulk Action Bar ──────────────────────────────────── */}
          <div className="bulk-actions">
            <span className="bulk-actions__info">
              <span className="bulk-actions__ready">{progress.ready}</span> of {progress.total} ready to submit
            </span>
            <button
              onClick={handleSubmitAll}
              disabled={submitting || progress.ready === 0}
              className="btn btn-primary"
            >
              {submitting ? 'Submitting…' : `Submit All Ready (${progress.ready})`}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

import { useState, useEffect, useRef, useMemo } from 'react'
import { useKpiContext } from '../../contexts/KpiContext'
import { useAuthContext } from '../../contexts/AuthContext'
import { apiFetch } from '../../lib/api'
import './DailyKpiInput.css'

interface EventTimePointData {
  id: string
  name: string
  capture_mode_allowed: string
  target_time?: string | null
}

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
  event_time_points?: EventTimePointData[]
}

interface EventTimeInput {
  point_id: string
  point_name: string
  capture_mode: 'auto' | 'manual'
  capture_mode_allowed?: string
  reason?: string
}

interface KpiInput {
  kpi_id: string
  value: string
  value_numeric?: number
  value_boolean?: boolean
  notes: string
  event_times?: EventTimeInput[]
}

interface SubmittedEntry {
  observation_id: string
  kpi_id: string
  captured_at: string | null
  submitted_at: string | null
  check_result: string | null
  value_numeric: string | null
  value_text: string | null
  status: string
  edit_count: number
  check_result_val?: string
  reason?: string
  edit_window_remaining?: number | null  // seconds remaining in edit window
}

interface AuditRecord {
  id: string
  observation_id: string
  actor_id: string
  actor_email: string | null
  actor_role: string
  field_name: string
  old_value: string | null
  new_value: string | null
  change_type: string
  reason: string | null
  is_within_edit_window: boolean
  created_at: string | null
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function determineDataType(unit: string, captureType?: string): 'numeric' | 'boolean' | 'text' {
  if (captureType === 'check') return 'boolean'
  const unitLower = unit.toLowerCase()
  if (unitLower === 'yes/no' || unitLower === 'yes-no' || unitLower === 'boolean') return 'boolean'
  if (unitLower === 'text' || unitLower === 'description' || unitLower === 'notes') return 'text'
  return 'numeric'
}

function isInputValid(input: KpiInput | undefined, assignment?: KpiAssignment): boolean {
  if (!input || !assignment) return false

  const captureType = assignment.capture_type

  if (captureType === 'event_time') {
    if (!input.value.trim()) return false
    const hasAnyTime = (input.event_times || []).length > 0
    return hasAnyTime
  }
  if (captureType === 'value_and_event_time') {
    if (!input.value.trim()) return false
    const hasAnyTime = (input.event_times || []).length > 0
    return hasAnyTime
  }

  if (captureType === 'check') {
    if (input.value_boolean === undefined) return false
    if (input.value_boolean === false) {
      return input.notes.trim().length > 0
    }
    return true
  }

  const dataType = assignment.data_type
  if (dataType === 'boolean') return input.value_boolean !== undefined
  if (dataType === 'text') return input.value.trim().length > 0
  return input.value.trim().length > 0
}

// ─── Frequency-period helpers ─────────────────────────────────────────────

/** Return the start-of-period Date for a given frequency and reference date. */
function getPeriodStart(freq: string, refDate: Date): Date {
  const d = new Date(refDate)
  switch (freq) {
    case 'daily':
      d.setHours(0, 0, 0, 0)
      return d
    case 'weekly': {
      // ISO week: Monday = 1 … Sunday = 7
      const day = d.getDay() || 7 // convert Sun=0 → 7
      d.setDate(d.getDate() - day + 1) // back to Monday
      d.setHours(0, 0, 0, 0)
      return d
    }
    case 'monthly':
      return new Date(d.getFullYear(), d.getMonth(), 1)
    case 'quarterly': {
      const q = Math.floor(d.getMonth() / 3) * 3
      return new Date(d.getFullYear(), q, 1)
    }
    case 'annual':
      return new Date(d.getFullYear(), 0, 1)
    default:
      // Unknown frequency → treat as daily
      d.setHours(0, 0, 0, 0)
      return d
  }
}

/** Check if a submission falls within the same period as refDate for the given frequency. */
function isInSamePeriod(freq: string, submittedAt: string | null, refDate: Date): boolean {
  if (!submittedAt) return false
  const sub = new Date(submittedAt)
  const periodStart = getPeriodStart(freq, refDate)
  return sub >= periodStart
}

function formatRemaining(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return 'Edit window expired'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  if (m > 0) return `${m}m ${s}s remaining`
  return `${s}s remaining`
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DailyKpiInput() {
  const { kpis, loading: kpisLoading } = useKpiContext()
  const { user: dbUser, departmentId, schoolId } = useAuthContext()
  const [assignments, setAssignments] = useState<KpiAssignment[]>([])
  const [inputs, setInputs] = useState<Record<string, KpiInput>>({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])
  const [notesOpen, setNotesOpen] = useState<Record<string, boolean>>({})
  const [submittedKpis, setSubmittedKpis] = useState<Record<string, SubmittedEntry>>({})
  const [clearDraftConfirm, setClearDraftConfirm] = useState(false)

  // Edit state
  const [editingKpiId, setEditingKpiId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<Record<string, { value_numeric?: number; value_text?: string; check_result?: string; reason?: string }>>({})
  const [editSaving, setEditSaving] = useState(false)

  // Audit history state
  const [auditHistoryKpiId, setAuditHistoryKpiId] = useState<string | null>(null)
  const [auditHistory, setAuditHistory] = useState<AuditRecord[]>([])
  const [auditLoading, setAuditLoading] = useState(false)

  const userDepartmentId = departmentId
  const userDepartmentName = dbUser?.full_name || null
  const userSchoolId = schoolId

  const DRAFT_KEY = `kpi-draft-${selectedDate}`
  const hasLoadedDraft = useRef(false)

  // ── Edit window countdown timer ────────────────────────────────────────────
  const [, setTick] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 30000) // refresh every 30s
    return () => clearInterval(interval)
  }, [])

  // ── Date change handler ───────────────────────────────────────────────────
  const handleDateChange = (newDate: string) => {
    localStorage.removeItem(DRAFT_KEY)
    setSelectedDate(newDate)
    setEditingKpiId(null)
    setAuditHistoryKpiId(null)
    const clearedInputs: Record<string, KpiInput> = {}
    Object.keys(inputs).forEach(id => {
      const assignment = assignments.find(a => a.kpi_id === id)
      const eventTimes: EventTimeInput[] = (assignment?.event_time_points || []).map(p => ({
        point_id: p.id,
        point_name: p.name,
        capture_mode: 'manual' as const,
        reason: '',
      }))
      clearedInputs[id] = {
        kpi_id: id, value: '', value_boolean: undefined, notes: '',
        event_times: eventTimes.length > 0 ? eventTimes : undefined,
      }
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
              const draftInput = draft.inputs[assignment.kpi_id]
              if (draftInput) {
                restoredInputs[assignment.kpi_id] = draftInput
              } else {
                const eventTimes: EventTimeInput[] = (assignment.event_time_points || []).map(p => ({
                  point_id: p.id,
                  point_name: p.name,
                  capture_mode: 'manual' as const,
                  reason: '',
                }))
                restoredInputs[assignment.kpi_id] = {
                  kpi_id: assignment.kpi_id, value: '', value_boolean: undefined, notes: '',
                  event_times: eventTimes.length > 0 ? eventTimes : undefined,
                }
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
      const eventTimes: EventTimeInput[] = (assignment.event_time_points || []).map(p => ({
        point_id: p.id,
        point_name: p.name,
        capture_mode: 'manual' as const,
        reason: '',
      }))
      clearedInputs[assignment.kpi_id] = {
        kpi_id: assignment.kpi_id, value: '', value_boolean: undefined, notes: '',
        event_times: eventTimes.length > 0 ? eventTimes : undefined,
      }
    })
    setInputs(clearedInputs)
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
        department_id: userDepartmentId || 'general',
        department_name: userDepartmentName || 'General',
        frequency_code: kpi.frequency_code,
        capture_type: kpi.capture_type,
        data_type: determineDataType(kpi.unit_of_measure, kpi.capture_type),
        version: kpi.version || 1,
        last_submission_date: undefined,
        event_time_points: kpi.event_time_points || [],
      }))
      setAssignments(newAssignments)

      const initialInputs: Record<string, KpiInput> = {}
      newAssignments.forEach(a => {
        const eventTimes: EventTimeInput[] = (a.event_time_points || []).map(p => ({
          point_id: p.id,
          point_name: p.name,
          capture_mode: 'manual' as const,
          reason: '',
        }))
        initialInputs[a.kpi_id] = {
          kpi_id: a.kpi_id, value: '', value_boolean: undefined, notes: '',
          event_times: eventTimes.length > 0 ? eventTimes : undefined,
        }
      })
      setInputs(initialInputs)
      setLoading(false)
    }
  }, [kpisLoading, kpis, userDepartmentId, userDepartmentName])

  // ── Load submitted state from API on mount and date change ─────────────
  useEffect(() => {
    if (loading || assignments.length === 0) return

    const loadSubmissions = async () => {
      try {
        const res = await apiFetch(`/api/v1/observations/submissions-by-date?date=${selectedDate}`)
        if (res.ok) {
          const submissions: SubmittedEntry[] = await res.json()
          const refDate = new Date(selectedDate + 'T00:00:00')
          const submittedMap: Record<string, SubmittedEntry> = {}
          // For each KPI, find the most recent submission that falls within
          // the current period based on its frequency_code.
          submissions.forEach(s => {
            const assignment = assignments.find(a => a.kpi_id === s.kpi_id)
            const freq = assignment?.frequency_code || 'daily'
            if (isInSamePeriod(freq, s.submitted_at, refDate)) {
              // Keep the most recent submission per KPI (submissions are ordered desc)
              if (!submittedMap[s.kpi_id]) {
                submittedMap[s.kpi_id] = s
              }
            }
          })
          setSubmittedKpis(submittedMap)
        }
      } catch {
        // Silently handle — component will show fresh state
      }
    }
    loadSubmissions()
  }, [loading, assignments.length, selectedDate])

  // ── Progress calculation ──────────────────────────────────────────────────
  const progress = useMemo(() => {
    const total = assignments.length
    const submitted = assignments.filter(a => submittedKpis[a.kpi_id]).length
    const ready = assignments.filter(a => isInputValid(inputs[a.kpi_id], a) && !submittedKpis[a.kpi_id]).length
    return { total, submitted, ready }
  }, [assignments, inputs, submittedKpis])

  // ── Input handlers ────────────────────────────────────────────────────────
  const handleInputChange = (kpiId: string, field: 'value' | 'notes' | 'value_boolean', value: string | boolean) => {
    setInputs(prev => ({
      ...prev,
      [kpiId]: { ...prev[kpiId], [field]: value },
    }))
  }

  const handleEventTimeChange = (kpiId: string, pointIndex: number, field: keyof EventTimeInput, value: string) => {
    setInputs(prev => {
      const current = prev[kpiId]
      const eventTimes = [...(current.event_times || [])]
      eventTimes[pointIndex] = { ...eventTimes[pointIndex], [field]: value }
      return { ...prev, [kpiId]: { ...current, event_times: eventTimes } }
    })
  }

  const toggleNotes = (kpiId: string) => {
    setNotesOpen(prev => ({ ...prev, [kpiId]: !prev[kpiId] }))
  }

  // ── Build observation payload (no checker_id — backend derives from auth) ──
  function buildPayload(assignment: KpiAssignment, input: KpiInput, kpiId: string) {
    const payload: any = {
      kpi_id: kpiId,
      kpi_version: assignment.version || 1,
      department_id: userDepartmentId || null,
      school_id: userSchoolId || null,
      value_text: input.notes,
      submission_date: selectedDate,
    }

    const captureType = assignment.capture_type
    payload.capture_type = captureType

    if (captureType === 'check') {
      payload.check_result = input.value_boolean ? 'Yes' : 'No'
      if (input.value_boolean === false) {
        payload.reason = input.notes || ''
      }
    }

    if (captureType === 'event_time') {
      payload.value_text = input.value || input.notes
      // Event times — timestamps are auto-generated by the server
      payload.event_times = (input.event_times || []).map(et => ({
        event_time_point_id: et.point_id,
        captured_at: new Date().toISOString(), // placeholder — server overrides
        capture_mode: et.capture_mode,
        reason: et.capture_mode === 'manual' ? (et.reason || 'Manual entry') : undefined,
      }))
    } else if (captureType === 'value_and_event_time') {
      payload.value_numeric = parseFloat(input.value)
      payload.event_times = (input.event_times || []).map(et => ({
        event_time_point_id: et.point_id,
        captured_at: new Date().toISOString(), // placeholder — server overrides
        capture_mode: et.capture_mode,
        reason: et.capture_mode === 'manual' ? (et.reason || 'Manual entry') : undefined,
      }))
    } else if (assignment.data_type === 'boolean') {
      payload.value_numeric = input.value_boolean ? 1 : 0
      payload.value_text = input.value_boolean ? 'Yes' : 'No'
    } else if (assignment.data_type === 'text') {
      payload.value_text = input.value
    } else {
      payload.value_numeric = parseFloat(input.value)
    }

    return payload
  }

  // ── Per-card submit ───────────────────────────────────────────────────────
  const handleSubmit = async (kpiId: string) => {
    const input = inputs[kpiId]
    const assignment = assignments.find(a => a.kpi_id === kpiId)
    if (!input || !assignment) return

    if (!isInputValid(input, assignment)) {
      setError('Please fill in a valid value before submitting')
      return
    }

    setSubmitting(true)
    setError(null)
    setSuccess(null)

    try {
      const payload = buildPayload(assignment, input, kpiId)
      const idempotencyKey = `${kpiId}-${selectedDate}-${dbUser?.id || 'anon'}-${Date.now()}`

      const res = await apiFetch('/api/v1/observations', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => null)
        const msg = body?.detail || body?.error?.message || 'Failed to submit observation'
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
      }

      const observation = await res.json()
      // Store the submitted entry with captured_at from server
      setSubmittedKpis(prev => ({
        ...prev,
        [kpiId]: {
          observation_id: observation.id,
          kpi_id: kpiId,
          captured_at: observation.captured_at,
          submitted_at: observation.submitted_at,
          check_result: observation.check_result,
          value_numeric: observation.value_numeric != null ? String(observation.value_numeric) : null,
          value_text: observation.value_text,
          status: observation.status,
          edit_count: observation.edit_count || 0,
        },
      }))
      setSuccess('KPI value submitted successfully')
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
      return isInputValid(input, assignment) && !submittedKpis[kpiId]
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
        const idempotencyKey = `${kpiId}-${selectedDate}-${dbUser?.id || 'anon'}-${Date.now()}`

        return apiFetch('/api/v1/observations', {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        }).then(async (res) => {
          if (!res.ok) {
            const body = await res.json().catch(() => null)
            const msg = body?.detail || body?.error?.message || 'Failed'
            throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
          }
          const observation = await res.json()
          return { kpiId, observation }
        })
      })

      const results = await Promise.allSettled(submissions)
      const succeeded = results.filter(r => r.status === 'fulfilled') as PromiseFulfilledResult<{ kpiId: string; observation: any }>[]
      const failed = results.filter(r => r.status === 'rejected')

      // Update submitted state from successful responses
      const newSubmitted = { ...submittedKpis }
      succeeded.forEach(({ value }) => {
        newSubmitted[value.kpiId] = {
          observation_id: value.observation.id,
          kpi_id: value.kpiId,
          captured_at: value.observation.captured_at,
          submitted_at: value.observation.submitted_at,
          check_result: value.observation.check_result,
          value_numeric: value.observation.value_numeric != null ? String(value.observation.value_numeric) : null,
          value_text: value.observation.value_text,
          status: value.observation.status,
          edit_count: value.observation.edit_count || 0,
        }
      })
      setSubmittedKpis(newSubmitted)

      if (failed.length > 0 && failed.length < validInputs.length) {
        setSuccess(`${succeeded.length} submitted, ${failed.length} failed`)
      } else if (failed.length > 0) {
        throw new Error(`${failed.length} submission(s) failed`)
      } else {
        setSuccess(`${validInputs.length} KPI values submitted successfully`)
      }

      localStorage.removeItem(DRAFT_KEY)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit some KPI values')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Edit flow ────────────────────────────────────────────────────────────
  const startEdit = async (kpiId: string) => {
    const entry = submittedKpis[kpiId]
    if (!entry) return

    // Fetch fresh observation data
    try {
      const res = await apiFetch(`/api/v1/observations/${entry.observation_id}`)
      if (!res.ok) throw new Error('Failed to load observation')
      const obs = await res.json()

      setEditValues(prev => ({
        ...prev,
        [kpiId]: {
          value_numeric: obs.value_numeric != null ? Number(obs.value_numeric) : undefined,
          value_text: obs.value_text || undefined,
          check_result: obs.check_result || undefined,
          reason: obs.reason || undefined,
        },
      }))
      setEditingKpiId(kpiId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load entry for editing')
    }
  }

  const cancelEdit = () => {
    setEditingKpiId(null)
    setEditValues({})
  }

  const saveEdit = async (kpiId: string) => {
    const entry = submittedKpis[kpiId]
    if (!entry) return

    setEditSaving(true)
    setError(null)

    try {
      const editData = editValues[kpiId] || {}
      const body: any = {}
      if (editData.value_numeric !== undefined) body.value_numeric = editData.value_numeric
      if (editData.value_text !== undefined) body.value_text = editData.value_text
      if (editData.check_result !== undefined) body.check_result = editData.check_result
      if (editData.reason !== undefined) body.reason = editData.reason

      const res = await apiFetch(`/api/v1/observations/${entry.observation_id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const respBody = await res.json().catch(() => null)
        const msg = respBody?.detail || respBody?.error?.message || 'Failed to save edit'
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
      }

      const updated = await res.json()
      // Update submitted entry
      setSubmittedKpis(prev => ({
        ...prev,
        [kpiId]: {
          ...prev[kpiId],
          captured_at: updated.captured_at,
          check_result: updated.check_result,
          value_numeric: updated.value_numeric != null ? String(updated.value_numeric) : null,
          value_text: updated.value_text,
          status: updated.status,
          edit_count: updated.edit_count || 0,
        },
      }))
      setSuccess('Entry updated successfully')
      setEditingKpiId(null)
      setEditValues({})
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save edit')
    } finally {
      setEditSaving(false)
    }
  }

  // ── Audit history ────────────────────────────────────────────────────────
  const loadAuditHistory = async (kpiId: string) => {
    const entry = submittedKpis[kpiId]
    if (!entry) return

    setAuditLoading(true)
    setAuditHistoryKpiId(kpiId)
    try {
      const res = await apiFetch(`/api/v1/observations/${entry.observation_id}/audit-history`)
      if (res.ok) {
        const records: AuditRecord[] = await res.json()
        setAuditHistory(records)
      } else {
        setAuditHistory([])
      }
    } catch {
      setAuditHistory([])
    } finally {
      setAuditLoading(false)
    }
  }

  const closeAuditHistory = () => {
    setAuditHistoryKpiId(null)
    setAuditHistory([])
  }

  // ── Compute edit window info ─────────────────────────────────────────────
  const getEditWindowInfo = (entry: SubmittedEntry) => {
    if (!entry.captured_at) return { withinWindow: false, remaining: null }
    const capturedAt = new Date(entry.captured_at).getTime()
    const now = Date.now()
    const elapsed = (now - capturedAt) / 1000  // seconds
    const remaining = Math.max(0, 1800 - elapsed)  // 30 min = 1800 seconds
    return { withinWindow: remaining > 0, remaining }
  }

  const canEdit = (kpiId: string) => {
    const entry = submittedKpis[kpiId]
    if (!entry) return false
    const { withinWindow } = getEditWindowInfo(entry)
    const isAdmin = (dbUser?.roles || []).some(r => ['admin', 'superadmin', 'dept_head'].includes(r.toLowerCase()))
    return withinWindow || isAdmin
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
              const valid = isInputValid(input, assignment)
              const submittedEntry = submittedKpis[assignment.kpi_id]
              const submitted = !!submittedEntry
              const showNotes = !!notesOpen[assignment.kpi_id]
              const isEventTime = assignment.capture_type === 'event_time' || assignment.capture_type === 'value_and_event_time'
              const isValueAndEventTime = assignment.capture_type === 'value_and_event_time'
              const isEditing = editingKpiId === assignment.kpi_id
              const showAudit = auditHistoryKpiId === assignment.kpi_id

              const editWindowInfo = submittedEntry ? getEditWindowInfo(submittedEntry) : null
              const isEditable = submitted ? canEdit(assignment.kpi_id) : false

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
                        <span className="capture-badge" style={{ fontSize: 'var(--text-micro)', background: 'var(--ink-700)', color: 'var(--ink-300)', padding: '2px 6px', borderRadius: 4 }}>
                          {assignment.capture_type === 'check' ? 'check' : assignment.capture_type}
                        </span>
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

                    {/* ── SUBMITTED STATE ──────────────────────────────── */}
                    {submitted && !isEditing && (
                      <div className="submitted-info">
                        <div className="submitted-info__row">
                          <span className="submitted-info__label">Status:</span>
                          <span className="submitted-info__value">{submittedEntry!.status}</span>
                        </div>
                        {submittedEntry!.edit_count > 0 && (
                          <div className="submitted-info__row">
                            <span className="submitted-info__label">Edits:</span>
                            <span className="submitted-info__value">{submittedEntry!.edit_count}</span>
                          </div>
                        )}

                        {/* Edit window status */}
                        {editWindowInfo && (
                          <div className={`edit-window-status ${editWindowInfo.withinWindow ? 'edit-window-status--active' : 'edit-window-status--expired'}`}>
                            {editWindowInfo.withinWindow ? (
                              <>
                                <span className="edit-window-icon">✏️</span>
                                <span>Edit window: {formatRemaining(editWindowInfo.remaining)}</span>
                              </>
                            ) : (
                              <>
                                <span className="edit-window-icon">🔒</span>
                                <span>Edit window expired — Admin/DeptHead can still edit</span>
                              </>
                            )}
                          </div>
                        )}

                        <div className="submitted-actions">
                          {isEditable && (
                            <button onClick={() => startEdit(assignment.kpi_id)} className="btn btn-sm btn-secondary">
                              Edit Entry
                            </button>
                          )}
                          <button onClick={() => loadAuditHistory(assignment.kpi_id)} className="btn btn-sm btn-ghost">
                            {showAudit ? 'Hide Audit' : 'Audit History'}
                          </button>
                        </div>

                        {/* Audit history panel */}
                        {showAudit && (
                          <div className="audit-history-panel">
                            {auditLoading ? (
                              <p className="audit-loading">Loading audit history…</p>
                            ) : auditHistory.length === 0 ? (
                              <p className="audit-empty">No audit records found.</p>
                            ) : (
                              <div className="audit-records">
                                <h4>Audit Trail</h4>
                                {auditHistory.map(record => (
                                  <div key={record.id} className="audit-record">
                                    <div className="audit-record__header">
                                      <span className="audit-record__field">{record.field_name}</span>
                                      <span className={`audit-record__type audit-record__type--${record.change_type}`}>
                                        {record.change_type.replace(/_/g, ' ')}
                                      </span>
                                    </div>
                                    <div className="audit-record__values">
                                      <span className="audit-record__old">{record.old_value || '(none)'}</span>
                                      <span className="audit-record__arrow">→</span>
                                      <span className="audit-record__new">{record.new_value || '(none)'}</span>
                                    </div>
                                    <div className="audit-record__meta">
                                      <span>{record.actor_role}</span>
                                      <span>{record.created_at ? new Date(record.created_at).toLocaleString() : '—'}</span>
                                      {record.is_within_edit_window && <span className="audit-record__window-badge">within window</span>}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                            <button onClick={closeAuditHistory} className="btn btn-sm btn-ghost" style={{ marginTop: 8 }}>
                              Close
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* ── EDIT MODE ──────────────────────────────────── */}
                    {submitted && isEditing && (
                      <div className="edit-mode">
                        <h4>Edit Entry</h4>
                        <p className="edit-mode__hint">Modifying this entry will create an audit record.</p>

                        {assignment.capture_type === 'check' ? (
                          <div className="input-group">
                            <label>Check Result</label>
                            <div className="boolean-segmented">
                              <button
                                type="button"
                                className={`boolean-segmented-btn ${editValues[assignment.kpi_id]?.check_result === 'Yes' ? 'active' : ''}`}
                                onClick={() => setEditValues(prev => ({ ...prev, [assignment.kpi_id]: { ...prev[assignment.kpi_id], check_result: 'Yes' } }))}
                                disabled={editSaving}
                              >Yes</button>
                              <button
                                type="button"
                                className={`boolean-segmented-btn ${editValues[assignment.kpi_id]?.check_result === 'No' ? 'active' : ''}`}
                                onClick={() => setEditValues(prev => ({ ...prev, [assignment.kpi_id]: { ...prev[assignment.kpi_id], check_result: 'No' } }))}
                                disabled={editSaving}
                              >No</button>
                            </div>
                            {editValues[assignment.kpi_id]?.check_result === 'No' && (
                              <div className="input-group" style={{ marginTop: 8 }}>
                                <label>Reason (required when No)</label>
                                <input
                                  type="text"
                                  value={editValues[assignment.kpi_id]?.reason || ''}
                                  onChange={(e) => setEditValues(prev => ({ ...prev, [assignment.kpi_id]: { ...prev[assignment.kpi_id], reason: e.target.value } }))}
                                  className="input-field"
                                  placeholder="Reason for No"
                                  disabled={editSaving}
                                />
                              </div>
                            )}
                          </div>
                        ) : assignment.data_type === 'boolean' ? (
                          <div className="input-group">
                            <label>Value</label>
                            <div className="boolean-segmented">
                              <button
                                type="button"
                                className={`boolean-segmented-btn ${editValues[assignment.kpi_id]?.check_result === 'Yes' ? 'active' : ''}`}
                                onClick={() => setEditValues(prev => ({ ...prev, [assignment.kpi_id]: { ...prev[assignment.kpi_id], check_result: 'Yes', value_numeric: 1 } }))}
                                disabled={editSaving}
                              >Yes</button>
                              <button
                                type="button"
                                className={`boolean-segmented-btn ${editValues[assignment.kpi_id]?.check_result === 'No' ? 'active' : ''}`}
                                onClick={() => setEditValues(prev => ({ ...prev, [assignment.kpi_id]: { ...prev[assignment.kpi_id], check_result: 'No', value_numeric: 0 } }))}
                                disabled={editSaving}
                              >No</button>
                            </div>
                          </div>
                        ) : (
                          <div className="input-group">
                            <label>Value ({assignment.kpi_unit})</label>
                            <input
                              type={assignment.data_type === 'text' ? 'text' : 'number'}
                              step={assignment.data_type === 'text' ? undefined : '0.01'}
                              value={editValues[assignment.kpi_id]?.value_numeric ?? editValues[assignment.kpi_id]?.value_text ?? ''}
                              onChange={(e) => {
                                const val = assignment.data_type === 'text'
                                  ? { value_text: e.target.value }
                                  : { value_numeric: parseFloat(e.target.value) || 0 }
                                setEditValues(prev => ({ ...prev, [assignment.kpi_id]: { ...prev[assignment.kpi_id], ...val } }))
                              }}
                              className="input-field"
                              disabled={editSaving}
                            />
                          </div>
                        )}

                        <div className="edit-mode__actions">
                          <button onClick={cancelEdit} disabled={editSaving} className="btn btn-sm btn-ghost">Cancel</button>
                          <button onClick={() => saveEdit(assignment.kpi_id)} disabled={editSaving} className="btn btn-sm btn-primary">
                            {editSaving ? 'Saving…' : 'Save Changes'}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* ── INPUT FORM (not submitted) ──────────────────── */}
                    {!submitted && !isEditing && (
                      <>
                        {/* Event-time: text description + time pickers (no manual timestamp) */}
                        {isEventTime && (
                          <div className="event-time-section">
                            <div className="input-group">
                              <label htmlFor={`value-${assignment.kpi_id}`}>
                                {isValueAndEventTime ? `Value (${assignment.kpi_unit})` : 'Description'}
                              </label>
                              {isValueAndEventTime ? (
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
                              ) : (
                                <input
                                  id={`value-${assignment.kpi_id}`}
                                  type="text"
                                  value={input.value}
                                  onChange={(e) => handleInputChange(assignment.kpi_id, 'value', e.target.value)}
                                  placeholder="Describe the observation…"
                                  className="input-field"
                                  disabled={submitting}
                                />
                              )}
                            </div>

                            {/* Event time points — no manual captured_at picker */}
                            {(input.event_times || []).map((et, idx) => (
                              <div key={idx} className="event-time-point" style={{ border: '1px solid var(--ink-600)', borderRadius: 8, padding: '10px 12px', marginTop: 8 }}>
                                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--ink-300)', marginBottom: 6 }}>
                                  {et.point_name}
                                </div>
                                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                  <div className="input-group" style={{ flex: '0 0 120px' }}>
                                    <label style={{ fontSize: 'var(--text-micro)' }}>Mode</label>
                                    <select
                                      value={et.capture_mode}
                                      onChange={(e) => handleEventTimeChange(assignment.kpi_id, idx, 'capture_mode', e.target.value)}
                                      className="input-field"
                                      disabled={submitting}
                                      style={{ fontSize: 'var(--text-sm)' }}
                                    >
                                      <option value="manual">Manual</option>
                                      <option value="auto" disabled={et.capture_mode_allowed === 'manual_only'}>Auto</option>
                                    </select>
                                  </div>
                                </div>
                                {et.capture_mode === 'manual' && (
                                  <div className="input-group" style={{ marginTop: 6 }}>
                                    <label style={{ fontSize: 'var(--text-micro)' }}>Reason for manual entry</label>
                                    <input
                                      type="text"
                                      value={et.reason || ''}
                                      onChange={(e) => handleEventTimeChange(assignment.kpi_id, idx, 'reason', e.target.value)}
                                      placeholder="Why manual? (required)"
                                      className="input-field"
                                      disabled={submitting}
                                      style={{ fontSize: 'var(--text-sm)' }}
                                    />
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Boolean (check) */}
                        {!isEventTime && assignment.data_type === 'boolean' && (
                          <div className="input-group">
                            <label>Value ({assignment.kpi_unit})</label>
                            <div className="boolean-segmented">
                              <button
                                type="button"
                                className={`boolean-segmented-btn ${input.value_boolean === true ? 'active' : ''}`}
                                onClick={() => handleInputChange(assignment.kpi_id, 'value_boolean', true)}
                                disabled={submitting}
                              >Yes</button>
                              <button
                                type="button"
                                className={`boolean-segmented-btn ${input.value_boolean === false ? 'active' : ''}`}
                                onClick={() => handleInputChange(assignment.kpi_id, 'value_boolean', false)}
                                disabled={submitting}
                              >No</button>
                            </div>
                            {/* Validation hint for check + reason */}
                            {assignment.capture_type === 'check' && input.value_boolean === false && (
                              <p style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-400)', marginTop: 4 }}>
                                Reason is required when capture type is No.
                              </p>
                            )}
                          </div>
                        )}

                        {/* Text */}
                        {!isEventTime && assignment.data_type === 'text' && (
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
                        )}

                        {/* Numeric (default) */}
                        {!isEventTime && assignment.data_type !== 'boolean' && assignment.data_type !== 'text' && (
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

                        {/* Submit button */}
                        <div className="kpi-input-card__actions">
                          <button
                            onClick={() => handleSubmit(assignment.kpi_id)}
                            disabled={!valid || submitting}
                            className="btn btn-primary btn-sm"
                          >
                            {submitting ? 'Submitting…' : 'Submit'}
                          </button>
                        </div>
                      </>
                    )}
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

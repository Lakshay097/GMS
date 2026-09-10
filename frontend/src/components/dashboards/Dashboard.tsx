import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Info } from 'lucide-react'
import { apiFetch } from '../../lib/api'
import { useAuthContext } from '../../contexts/AuthContext'
import { formatDate, formatDateTime, sortItems } from '../../lib/utils'
import ExpirationWidget from './ExpirationWidget'
import FrequencyProgress from './FrequencyProgress'
import './Dashboard.css'

// ─── Summary API types ─────────────────────────────────────────────────────────

interface SummaryFilters {
  period: string
  date_from: string | null
  date_to: string | null
  school_id: string | null
  department_id: string | null
  filters_applied: string[]
}

interface SummaryTrendPoint {
  label: string
  date: string
  entered: number
  missing: number
  tasks_completed: number
}

interface DashboardSummary {
  role: string
  generated_at: string
  filters: SummaryFilters
  kpi_library: { total_kras: number; total_kpis: number; assigned_kpis: number; unassigned_kpis: number }
  entries: {
    expected_entries: number
    entered: number
    missing: number
    late: number
    follow_up: number
    entered_rate: number
    missing_rate: number
    follow_up_rate: number
  }
  tasks: {
    assigned_open: number
    pending_approval: number
    completed: number
    overdue: number
    escalated: number
    on_time_rate: number
  }
  trend: SummaryTrendPoint[]
  by_department: Array<{ department_id: string; department_name: string; kpis_assigned: number; entered: number; missing: number; pct_entered: number }> | null
  by_school: Array<{ school_id: string; school_name: string; kpis_assigned: number; entered: number; missing: number; pct_entered: number }> | null
}

interface LegacyDashboardData {
  role: string
  school_id: string | null
  department_id: string | null
  generated_at: string
  kpi_summary: { total_kpis: number; met: number; not_met: number; amber: number; pct_met: number } | null
  compliance_summary: { total_due: number; submitted: number; missed: number; late: number; pct_submitted: number } | null
  task_summary: { open_tasks: number; overdue_tasks: number; completed_this_period: number; pct_on_time: number } | null
  discrepancy_summary: { open_discrepancies: number; under_investigation: number; pending_approval: number; resolved_this_period: number; breached_sla: number } | null
  escalation_summary: { open_escalations: number; acknowledged: number; by_level: Array<{ level: string; count: number }> } | null
  rag_distribution: { green: number; amber: number; red: number; not_submitted: number } | null
  frequency_progress: {
    periods: Array<{ frequency: string; label: string; total_kpis: number; submitted: number; pending: number; pct_complete: number; period_start: string; period_end: string }>
    overall_submitted: number
    overall_total: number
    overall_pct: number
  } | null
  recent_activity: Array<{ entity_type: string; entity_id: string; action: string; actor_name: string; timestamp: string }> | null
  pending_my_action: Array<{ task_id: string; title: string; status: string; eta: string | null }> | null
}

type SortDir = 'asc' | 'desc'
const PERIODS = ['today', 'week', 'month', 'custom'] as const
type Period = (typeof PERIODS)[number]

const PERIOD_LABEL: Record<Period, string> = {
  today: 'Today',
  week: 'This week',
  month: 'This month',
  custom: 'Custom',
}

// ─── Legacy sub-components (kept) ──────────────────────────────────────────────

function CollapsibleSection({
  id, title, meta, expanded, onToggle, children,
}: {
  id: string
  title: string
  meta?: string
  expanded: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="dashboard-section">
      <button className="dashboard-section__header" aria-expanded={expanded} aria-controls={`section-body-${id}`} onClick={onToggle}>
        <span className="dashboard-section__chevron" aria-hidden="true">▶</span>
        <span className="dashboard-section__title">{title}</span>
        {meta && <span className="dashboard-section__meta">{meta}</span>}
      </button>
      {expanded && (
        <div id={`section-body-${id}`} className="dashboard-section__body" role="region" aria-labelledby={`section-header-${id}`}>
          {children}
        </div>
      )}
    </div>
  )
}


function RagCard({
  label, value, sub, valueVariant, onClick,
}: {
  label: string
  value: number
  sub: string
  valueVariant?: 'rag-green' | 'rag-amber' | 'rag-red'
  onClick: () => void
}) {
  const valueClass = valueVariant ? `summary-card__value summary-card__value--${valueVariant}` : 'summary-card__value'
  return (
    <div className="interactive-summary-card" role="button" tabIndex={0} onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } }}>
      <span className="interactive-summary-card__arrow" aria-hidden="true">→</span>
      <div className="summary-card__label">{label}</div>
      <div className={valueClass}>{value}</div>
      <div className="summary-card__sub">{sub}</div>
    </div>
  )
}

// ─── Charts (dependency-free SVG) ──────────────────────────────────────────────

function Donut({ entered, followUp, missing }: { entered: number; followUp: number; missing: number }) {
  const plain = Math.max(entered - followUp, 0)
  const total = plain + followUp + missing
  const R = 60
  const C = 2 * Math.PI * R
  const segs = [
    { v: plain, color: 'var(--moss-600)', label: 'Entered' },
    { v: followUp, color: 'var(--amber-600)', label: 'Follow-up' },
    { v: missing, color: 'var(--rose-600)', label: 'Missing' },
  ]
  let offset = 0
  const pct = total > 0 ? Math.round((100 * (plain + followUp)) / total) : 0
  return (
    <div className="dashsum-donut-wrap">
      <div className="dashsum-donut" role="img" aria-label={`Entry rate ${pct}%: ${entered} entered, ${missing} missing, ${followUp} need follow-up`}>
        <svg viewBox="0 0 168 168">
          <circle cx="84" cy="84" r={R} fill="none" stroke="var(--paper-1)" strokeWidth="16" />
          {total > 0 && segs.map((s) => {
            const frac = s.v / total
            const el = (
              <circle
                key={s.label}
                cx="84" cy="84" r={R} fill="none"
                stroke={s.color}
                strokeWidth="16"
                strokeDasharray={`${frac * C} ${C}`}
                strokeDashoffset={-offset * C}
                transform="rotate(-90 84 84)"
              />
            )
            offset += frac
            return el
          })}
        </svg>
        <div className="dashsum-donut__center">
          <span className="dashsum-donut__pct">{pct}%</span>
          <span className="dashsum-donut__cap">entered</span>
        </div>
      </div>
      <div className="dashsum-donut-legend">
        {segs.map((s) => (
          <div className="row" key={s.label}>
            <span className="dot" style={{ background: s.color }} />
            <span className="num">{s.v}</span>
            <span>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TrendChart({ points }: { points: SummaryTrendPoint[] }) {
  if (points.length === 0) return <div className="dashsum-card__sub">No activity in this window.</div>
  const W = 640
  const H = 200
  const PAD_L = 30
  const PAD_B = 24
  const PAD_T = 10
  const innerW = W - PAD_L - 8
  const innerH = H - PAD_T - PAD_B
  const maxVal = Math.max(
    ...points.map((p) => p.entered + p.missing),
    ...points.map((p) => p.tasks_completed),
    1,
  )
  const bw = innerW / points.length
  const barW = Math.max(Math.min(bw * 0.55, 34), 3)
  const labelEvery = Math.ceil(points.length / 10)
  const taskPts = points.map((p, i) => {
    const x = PAD_L + i * bw + bw / 2
    const y = PAD_T + innerH - (p.tasks_completed / maxVal) * innerH
    return `${x},${y}`
  }).join(' ')

  return (
    <div className="dashsum-trend" role="img" aria-label="Entries entered versus missing, and tasks completed, over the selected window">
      <svg viewBox={`0 0 ${W} ${H}`}>
        <line className="axis-line" x1={PAD_L} y1={PAD_T + innerH} x2={W - 8} y2={PAD_T + innerH} />
        {points.map((p, i) => {
          const x = PAD_L + i * bw + (bw - barW) / 2
          const hE = (p.entered / maxVal) * innerH
          const hM = (p.missing / maxVal) * innerH
          const base = PAD_T + innerH
          return (
            <g key={p.label + i}>
              {p.missing > 0 && <rect className="bar-missing" x={x} y={base - hE - hM} width={barW} height={hM} rx="2" />}
              {p.entered > 0 && <rect className="bar-entered" x={x} y={base - hE} width={barW} height={hE} rx="2" />}
              {i % labelEvery === 0 && (
                <text className="tick-label" x={PAD_L + i * bw + bw / 2} y={H - 8} textAnchor="middle">{p.label}</text>
              )}
            </g>
          )
        })}
        <polyline className="task-line" points={taskPts} />
        {points.map((p, i) => {
          const x = PAD_L + i * bw + bw / 2
          const y = PAD_T + innerH - (p.tasks_completed / maxVal) * innerH
          return <circle key={`d${i}`} className="task-dot" cx={x} cy={y} r="3" />
        })}
      </svg>
      <div className="dashsum-legend">
        <span><span className="dot" style={{ background: 'var(--moss-600)' }} />Entered</span>
        <span><span className="dot" style={{ background: 'var(--rose-600)', opacity: 0.35 }} />Missing</span>
        <span><span className="dot" style={{ background: 'var(--gold-600)' }} />Tasks completed</span>
      </div>
    </div>
  )
}

function MiniMeter({ pct }: { pct: number }) {
  const cls = pct >= 80 ? '' : pct >= 50 ? 'mid' : 'low'
  return (
    <div className="dashsum-mini" aria-label={`${pct}% entered`}>
      <div className="track"><span className={cls} style={{ width: `${Math.min(pct, 100)}%` }} /></div>
      <span className="pct">{pct}%</span>
    </div>
  )
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, roles, loading: authLoading } = useAuthContext()

  // Filters
  const [period, setPeriod] = useState<Period>('month')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [school, setSchool] = useState('')
  const [dept, setDept] = useState('')

  // Data
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [data, setData] = useState<LegacyDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter options
  const [schools, setSchools] = useState<Array<{ id: string; name: string }>>([])
  const [depts, setDepts] = useState<Array<{ id: string; name: string; school_id?: string }>>([])

  const [showDeptBannerDismissed, setDeptBannerDismissed] = useState(false)
  const [sections, setSections] = useState<Record<string, boolean>>({
    kpi: false, compliance: false, discrepancy: false, rag: true, pending: true, recent: false, expiration: true, freqProgress: true,
  })
  const [pendingSort, setPendingSort] = useState<{ key: 'title' | 'eta'; dir: SortDir }>({ key: 'eta', dir: 'asc' })
  const [recentSort, setRecentSort] = useState<{ key: 'actor_name' | 'timestamp'; dir: SortDir }>({ key: 'timestamp', dir: 'desc' })

  const isSuperadmin = roles.map((r) => r.toLowerCase()).includes('superadmin')
  const isAdmin = isSuperadmin || roles.map((r) => r.toLowerCase()).includes('admin')
  const isDeptScoped = roles.map((r) => r.toLowerCase()).some((r) => ['dept_head', 'checker', 'auditor'].includes(r))

  // Legacy dashboard fetch (widgets below the summary)
  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const response = await apiFetch('/api/v1/dashboard', { signal: controller.signal })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        setData(await response.json())
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        // Legacy widgets are secondary — a failure here must not kill the page.
        setData(null)
      }
    }
    if (authLoading) return
    load()
    return () => controller.abort()
  }, [authLoading])

  // Summary fetch — refires on every filter change
  useEffect(() => {
    if (authLoading) return
    const controller = new AbortController()
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const params = new URLSearchParams()
        if (period === 'custom') {
          params.set('period', 'custom')
          if (dateFrom) params.set('date_from', dateFrom)
          if (dateTo) params.set('date_to', dateTo)
        } else {
          params.set('period', period)
        }
        if (school) params.set('school_id', school)
        if (dept) params.set('department_id', dept)
        const qs = params.toString()
        const response = await apiFetch(`/api/v1/dashboard/summary${qs ? `?${qs}` : ''}`, { signal: controller.signal })
        if (!response.ok) {
          throw new Error(
            response.status === 401
              ? 'Session expired. Please sign in again.'
              : response.status === 403
                ? 'You do not have permission to view this dashboard.'
                : `Failed to load dashboard (HTTP ${response.status})`
          )
        }
        setSummary(await response.json())
        setLoading(false)
      } catch (err) {
        // Aborted attempt (StrictMode double-mount, filter change) must NOT
        // clear loading — the surviving fetch is still in flight and the
        // zeroed cards would paint first (the "loads with zero" bug).
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
        setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [authLoading, period, dateFrom, dateTo, school, dept])

  // School & department options (only for roles that may actually choose)
  useEffect(() => {
    if (authLoading) return
    if (!isAdmin) return
    const controller = new AbortController()
    const load = async () => {
      try {
        const sResp = await apiFetch('/api/v1/schools?page_size=100', { signal: controller.signal })
        if (sResp.ok) {
          const sJson = await sResp.json()
          setSchools((sJson.data || []).map((s: { id: string; name: string }) => ({ id: s.id, name: s.name })))
        }
        const dResp = await apiFetch('/api/v1/departments?page_size=200', { signal: controller.signal })
        if (dResp.ok) {
          const dJson = await dResp.json()
          setDepts((dJson.data || []).map((d: { id: string; name: string; school_id?: string }) => ({ id: d.id, name: d.name, school_id: d.school_id })))
        }
      } catch {
        // Options stay empty; selects simply render disabled.
      }
    }
    load()
    return () => controller.abort()
  }, [authLoading, isAdmin])

  const deptBannerVisible = !!data && !data.department_id && !showDeptBannerDismissed

  const toggleSection = (key: string) => setSections((prev) => ({ ...prev, [key]: !prev[key] }))
  const cyclePendingSort = (key: 'title' | 'eta') =>
    setPendingSort((prev) => (prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  const cycleRecentSort = (key: 'actor_name' | 'timestamp') =>
    setRecentSort((prev) => (prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  const sortIndicator = (key: string, activeKey: string, dir: SortDir) =>
    key !== activeKey ? <span className="sort-indicator">↕</span> : <span className="sort-indicator">{dir === 'asc' ? '↑' : '↓'}</span>

  const deptOptions = useMemo(() => {
    const pool = school ? depts.filter((d) => !d.school_id || d.school_id === school) : depts
    return pool
  }, [depts, school])

  // ── Loading / error states ──────────────────────────────────────────────────
  const userName = user?.full_name || 'there'

  if (error && !summary) {
    return (
      <div className="dashboard">
        <div className="page-head"><div><div className="eyebrow">Dashboard</div><h1>Dashboard</h1></div></div>
        <div className="error-banner" style={{ margin: 'var(--space-5) 40px 0' }}>
          <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>!</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Could not load dashboard</div>
            <div style={{ fontSize: 'var(--text-small)', opacity: 0.8 }}>{error}</div>
          </div>
          <button className="btn btn-sm btn-secondary" onClick={() => window.location.reload()}>Retry</button>
        </div>
      </div>
    )
  }

  // ── Derived summary values ──────────────────────────────────────────────────
  const e = summary?.entries
  const kl = summary?.kpi_library
  const t = summary?.tasks
  const scopeNote = summary
    ? [
        `Role: ${summary.role}`,
        summary.filters.department_id ? 'department view' : summary.filters.school_id ? 'school view' : 'all schools',
      ].join(' · ')
    : ''

  const sortedPending = data?.pending_my_action ? sortItems(data.pending_my_action, pendingSort.key, pendingSort.dir) : []
  const sortedRecent = data?.recent_activity ? sortItems(data.recent_activity, recentSort.key, recentSort.dir) : []

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <div className="eyebrow">Dashboard</div>
          <h1>Welcome back — {userName}</h1>
        </div>
      </div>

      <div className="dashsum">
        {/* ── Filter bar ──────────────────────────────────────────────────── */}
        <div className="dashsum-filters" role="group" aria-label="Dashboard filters">
          <div className="dashsum-seg" role="group" aria-label="Time period">
            {PERIODS.map((p) => (
              <button key={p} aria-pressed={period === p} onClick={() => setPeriod(p)}>{PERIOD_LABEL[p]}</button>
            ))}
          </div>

          {period === 'custom' && (
            <div className="dashsum-date">
              <label htmlFor="dash-from">From</label>
              <input id="dash-from" type="date" value={dateFrom} onChange={(ev) => setDateFrom(ev.target.value)} />
              <label htmlFor="dash-to">to</label>
              <input id="dash-to" type="date" value={dateTo} onChange={(ev) => setDateTo(ev.target.value)} />
            </div>
          )}

          {isSuperadmin && (
            <div className="dashsum-select">
              <span>School</span>
              <select value={school} onChange={(ev) => { setSchool(ev.target.value); setDept('') }} aria-label="Filter by school">
                <option value="">All schools</option>
                {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}

          {(isAdmin || (isDeptScoped && false)) && (
            <div className="dashsum-select">
              <span>Department</span>
              <select value={dept} onChange={(ev) => setDept(ev.target.value)} aria-label="Filter by department" disabled={isDeptScoped}>
                <option value="">All departments</option>
                {deptOptions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          )}

          <div className="dashsum-filters__spacer" />
          <span className="dashsum-scope-note">
            {loading ? 'Loading…' : (
              <>Viewing <strong>{scopeNote}</strong>{summary && summary.filters.filters_applied.length > 0 && <> — filters: <strong>{summary.filters.filters_applied.join(', ')}</strong></>}</>
            )}
          </span>
        </div>

        {/* ── KPI library + entry-rate cards ──────────────────────────────── */}
        {loading && !summary ? (
          <div className="dashsum-grid" aria-hidden="true">
            {[...Array(5)].map((_, i) => <div key={i} className="dashsum-skel" style={{ height: 116, animationDelay: `${i * 0.1}s` }} />)}
          </div>
        ) : summary && e && kl ? (
          <>
            <div className="dashsum-grid">
              <div
                className="dashsum-card dashsum-card--info"
                title={`The number is the KRA count (${kl.total_kras} active KRAs in the library) — not a KPI count. The lines below break down the KPI library: ${kl.total_kpis} KPIs total, ${kl.assigned_kpis} assigned to departments, ${kl.unassigned_kpis} unassigned.`}
              >
                <div className="dashsum-card__label">
                  KRAs
                  <span
                    className="dashsum-card__info"
                    tabIndex={0}
                    role="note"
                    aria-label={`KRA count: ${kl.total_kras} active KRAs in the library, not a KPI count. The KPI library holds ${kl.total_kpis} KPIs — ${kl.assigned_kpis} assigned to departments, ${kl.unassigned_kpis} unassigned.`}
                  >
                    <Info size={12} aria-hidden="true" />
                    <span className="dashsum-card__info-tip">
                      The number is the <strong>KRA count</strong> — active KRAs in the library, not a KPI count.
                      Below it: <strong>{kl.total_kpis} KPIs</strong> in the library ({kl.assigned_kpis} assigned to departments, {kl.unassigned_kpis} unassigned).
                    </span>
                  </span>
                </div>
                <div className="dashsum-card__num">{kl.total_kras}</div>
                <div className="dashsum-card__sub"><em>{kl.total_kpis}</em> KPIs in library</div>
                <div className="dashsum-card__sub">{kl.assigned_kpis} assigned · {kl.unassigned_kpis} unassigned</div>
              </div>

              <div className="dashsum-card dashsum-card--good">
                <div className="dashsum-card__label">Entered</div>
                <div className="dashsum-card__num">{e.entered}<small>of {e.expected_entries} expected</small></div>
                <div className="dashsum-meter dashsum-meter--good"><span style={{ width: `${e.entered_rate}%` }} /></div>
                <div className="dashsum-card__sub"><em>{e.entered_rate}%</em> entry rate</div>
              </div>

              <div className="dashsum-card dashsum-card--bad">
                <div className="dashsum-card__label">Missing</div>
                <div className="dashsum-card__num">{e.missing}</div>
                <div className="dashsum-meter dashsum-meter--bad"><span style={{ width: `${e.missing_rate}%` }} /></div>
                <div className="dashsum-card__sub"><em>{e.missing_rate}%</em> of expected entries not logged</div>
              </div>

              <div className="dashsum-card dashsum-card--warn">
                <div className="dashsum-card__label">Follow-up</div>
                <div className="dashsum-card__num">{e.follow_up}</div>
                <div className="dashsum-meter dashsum-meter--warn"><span style={{ width: `${e.follow_up_rate}%` }} /></div>
                <div className="dashsum-card__sub"><em>{e.follow_up_rate}%</em> of entries flagged amber — needs review</div>
              </div>

              <div className="dashsum-card">
                <div className="dashsum-card__label">Late entries</div>
                <div className="dashsum-card__num">{e.late}</div>
                <div className="dashsum-card__sub">Submitted after the deadline in this window</div>
              </div>
            </div>

            {/* ── Task pipeline strip ─────────────────────────────────────────── */}
            <div className="dashsum-tasks">
              <div className="dashsum-card__label">Tasks — assigned, pending, completed, overdue</div>
              <div className="dashsum-tasks__row">
                <div className="dashsum-task dashsum-task--open">
                  <span className="dashsum-task__num">{t!.assigned_open}</span>
                  <span className="dashsum-task__label">Assigned / open</span>
                </div>
                <div className="dashsum-task dashsum-task--approval">
                  <span className="dashsum-task__num">{t!.pending_approval}</span>
                  <span className="dashsum-task__label">Pending approval</span>
                </div>
                <div className="dashsum-task dashsum-task--done">
                  <span className="dashsum-task__num">{t!.completed}</span>
                  <span className="dashsum-task__label">Completed ({PERIOD_LABEL[period as Period] || 'period'})</span>
                </div>
                <div className="dashsum-task dashsum-task--overdue">
                  <span className="dashsum-task__num">{t!.overdue}</span>
                  <span className="dashsum-task__label">Overdue</span>
                </div>
                <div className="dashsum-task dashsum-task--escalated">
                  <span className="dashsum-task__num">{t!.escalated}</span>
                  <span className="dashsum-task__label">Escalated</span>
                </div>
              </div>
              {(() => {
                const parts = [
                  { key: 'pp-open', v: t!.assigned_open, title: 'Open' },
                  { key: 'pp-approval', v: t!.pending_approval, title: 'Pending approval' },
                  { key: 'pp-done', v: t!.completed, title: 'Completed' },
                  { key: 'pp-overdue', v: t!.overdue, title: 'Overdue' },
                  { key: 'pp-escalated', v: t!.escalated, title: 'Escalated' },
                ]
                const total = parts.reduce((a, p) => a + p.v, 0)
                if (total === 0) return <div className="dashsum-card__sub">No tasks in this scope yet.</div>
                return (
                  <>
                    <div className="dashsum-pipeline" aria-hidden="true">
                      {parts.filter((p) => p.v > 0).map((p) => (
                        <span key={p.key} className={p.key} style={{ width: `${(100 * p.v) / total}%` }} title={`${p.title}: ${p.v}`} />
                      ))}
                    </div>
                    <div className="dashsum-legend">
                      <span><span className="dot" style={{ background: 'var(--ink-300)' }} />Open {t!.assigned_open}</span>
                      <span><span className="dot" style={{ background: 'var(--amber-600)' }} />Pending approval {t!.pending_approval}</span>
                      <span><span className="dot" style={{ background: 'var(--moss-600)' }} />Completed {t!.completed}</span>
                      <span><span className="dot" style={{ background: 'var(--rose-600)' }} />Overdue {t!.overdue}</span>
                      <span><span className="dot" style={{ background: 'var(--clay-500)' }} />Escalated {t!.escalated}</span>
                      <span>· on-time rate <strong>{t!.on_time_rate}%</strong></span>
                    </div>
                  </>
                )
              })()}
            </div>

            {/* ── Charts row ─────────────────────────────────────────────────── */}
            <div className="dashsum-charts">
              <div className="dashsum-panel">
                <div className="dashsum-panel__title">Entry outcome</div>
                <Donut entered={e.entered} followUp={e.follow_up} missing={e.missing} />
              </div>
              <div className="dashsum-panel">
                <div className="dashsum-panel__title">Trend — entries &amp; tasks</div>
                <TrendChart points={summary.trend} />
              </div>
            </div>

            {/* ── Breakdowns ─────────────────────────────────────────────────── */}
            {summary.by_school && summary.by_school.length > 0 && (
              <div className="dashsum-panel">
                <div className="dashsum-panel__title">Schools</div>
                <div style={{ overflowX: 'auto' }}>
                  <table className="dashsum-table">
                    <thead>
                      <tr><th>School</th><th>KPIs assigned</th><th>Entered</th><th>Missing</th><th>Entry rate</th></tr>
                    </thead>
                    <tbody>
                      {summary.by_school.map((s) => (
                        <tr key={s.school_id}>
                          <td style={{ fontWeight: 600, color: 'var(--ink-900)' }}>{s.school_name}</td>
                          <td className="num">{s.kpis_assigned}</td>
                          <td className="num">{s.entered}</td>
                          <td className="num" style={{ color: s.missing > 0 ? 'var(--rose-600)' : undefined }}>{s.missing}</td>
                          <td><MiniMeter pct={s.pct_entered} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {summary.by_department && summary.by_department.length > 0 && (
              <div className="dashsum-panel">
                <div className="dashsum-panel__title">Departments</div>
                <div style={{ overflowX: 'auto' }}>
                  <table className="dashsum-table">
                    <thead>
                      <tr><th>Department</th><th>KPIs assigned</th><th>Entered</th><th>Missing</th><th>Entry rate</th></tr>
                    </thead>
                    <tbody>
                      {summary.by_department.map((d) => (
                        <tr key={d.department_id}>
                          <td style={{ fontWeight: 600, color: 'var(--ink-900)' }}>{d.department_name}</td>
                          <td className="num">{d.kpis_assigned}</td>
                          <td className="num">{d.entered}</td>
                          <td className="num" style={{ color: d.missing > 0 ? 'var(--rose-600)' : undefined }}>{d.missing}</td>
                          <td><MiniMeter pct={d.pct_entered} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        ) : null}

        {/* ── Department-less user banner ─────────────────────────────────── */}
        {deptBannerVisible && (
          <div className="banner banner-warning" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', padding: 'var(--space-4) var(--space-5)', background: 'var(--amber-100)', borderRadius: 'var(--radius)', borderLeft: '4px solid var(--amber-600)' }}>
            <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>!</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: 'var(--ink-900)', fontSize: 'var(--text-body)' }}>No department assigned yet</div>
              <div style={{ color: 'var(--ink-500)', fontSize: 'var(--text-small)', marginTop: 2 }}>Ask your admin to assign you to a department to see personalized KPIs and tasks.</div>
            </div>
            <button onClick={() => setDeptBannerDismissed(true)} aria-label="Dismiss banner"
              style={{ background: 'none', border: 'none', fontSize: '1.1rem', color: 'var(--ink-500)', cursor: 'pointer', padding: 4 }}>✕</button>
          </div>
        )}
      </div>

      {/* ── RAG Distribution ─────────────────────────────────────────────────── */}
      {data?.rag_distribution && (
        <CollapsibleSection id="rag" title="RAG Distribution"
          meta={`${data.rag_distribution.green} green · ${data.rag_distribution.amber} amber · ${data.rag_distribution.red} red`}
          expanded={sections.rag} onToggle={() => toggleSection('rag')}>
          <div className="summary-card-grid">
            <RagCard label="Green" value={data.rag_distribution.green} sub="On track — view in KPI Verification" valueVariant="rag-green" onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'green' } })} />
            <RagCard label="Amber" value={data.rag_distribution.amber} sub="Warning — view in KPI Verification" valueVariant="rag-amber" onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'amber' } })} />
            <RagCard label="Red" value={data.rag_distribution.red} sub="Critical — view in KPI Verification" valueVariant="rag-red" onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'red' } })} />
            <RagCard label="Not Submitted" value={data.rag_distribution.not_submitted} sub="Missing — view in KPI Verification" onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'not_submitted' } })} />
          </div>
        </CollapsibleSection>
      )}

      {/* ── Frequency Progress ───────────────────────────────────────────────── */}
      {data?.frequency_progress && data.frequency_progress.periods.length > 0 && (
        <FrequencyProgress data={data.frequency_progress} expanded={sections.freqProgress} onToggle={() => toggleSection('freqProgress')} />
      )}

      {/* ── Expiration Reminders ─────────────────────────────────────────────── */}
      <ExpirationWidget expanded={sections.expiration} onToggle={() => toggleSection('expiration')} />

      {/* ── Pending My Action ────────────────────────────────────────────────── */}
      {sortedPending.length > 0 && (
        <CollapsibleSection id="pending" title="Pending My Action"
          meta={`${data!.pending_my_action!.length} item${data!.pending_my_action!.length !== 1 ? 's' : ''}`}
          expanded={sections.pending} onToggle={() => toggleSection('pending')}>
          <div className="table-wrap dashboard-table-wrap dashboard-table-pending">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="sortable" onClick={() => cyclePendingSort('title')}
                    aria-sort={pendingSort.key === 'title' ? (pendingSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    Task {sortIndicator('title', pendingSort.key, pendingSort.dir)}
                  </th>
                  <th>Status</th>
                  <th className="sortable col-eta" onClick={() => cyclePendingSort('eta')}
                    aria-sort={pendingSort.key === 'eta' ? (pendingSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    ETA {sortIndicator('eta', pendingSort.key, pendingSort.dir)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedPending.map((task, i) => (
                  <tr key={`${task.task_id}-${i}`} style={{ cursor: 'pointer' }} onClick={() => navigate(`/tasks/${task.task_id}`)}>
                    <td><span style={{ fontWeight: 600, color: 'var(--ink-900)' }}>{task.title}</span></td>
                    <td>
                      <span className={`status-pill ${task.status === 'open' ? 'pending' : task.status === 'in_progress' ? 'progress' : 'completed'}`}>
                        {task.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="col-eta" style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)' }}>{formatDate(task.eta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* ── Recent Activities ────────────────────────────────────────────────── */}
      {sortedRecent.length > 0 && (
        <CollapsibleSection id="recent" title="Recent Activities"
          meta={`${data!.recent_activity!.length} recent`}
          expanded={sections.recent} onToggle={() => toggleSection('recent')}>
          <div className="table-wrap dashboard-table-wrap dashboard-table-recent">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th className="col-action">Action</th>
                  <th className="sortable" onClick={() => cycleRecentSort('actor_name')}
                    aria-sort={recentSort.key === 'actor_name' ? (recentSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    Actor {sortIndicator('actor_name', recentSort.key, recentSort.dir)}
                  </th>
                  <th className="sortable col-time" onClick={() => cycleRecentSort('timestamp')}
                    aria-sort={recentSort.key === 'timestamp' ? (recentSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    Time {sortIndicator('timestamp', recentSort.key, recentSort.dir)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedRecent.map((activity, i) => (
                  <tr key={`${activity.entity_id}-${i}`}>
                    <td><span className="status-pill progress">{activity.entity_type}</span></td>
                    <td className="col-action">{activity.action}</td>
                    <td style={{ fontWeight: 500 }}>{activity.actor_name}</td>
                    <td className="col-time" style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)' }}>{formatDateTime(activity.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}
    </div>
  )
}

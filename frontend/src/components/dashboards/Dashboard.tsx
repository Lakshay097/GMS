import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { formatDate, formatDateTime, sortItems } from '../../lib/utils'

// ─── Data types ────────────────────────────────────────────────────────────────

interface DashboardData {
  role: string
  school_id: string | null
  department_id: string | null
  generated_at: string
  kpi_summary: {
    total_kpis: number
    met: number
    not_met: number
    amber: number
    pct_met: number
  } | null
  compliance_summary: {
    total_due: number
    submitted: number
    missed: number
    late: number
    pct_submitted: number
  } | null
  task_summary: {
    open_tasks: number
    overdue_tasks: number
    completed_this_period: number
    pct_on_time: number
  } | null
  discrepancy_summary: {
    open_discrepancies: number
    under_investigation: number
    pending_approval: number
    resolved_this_period: number
    breached_sla: number
  } | null
  escalation_summary: {
    open_escalations: number
    acknowledged: number
    by_level: Array<{ level: string; count: number }>
  } | null
  rag_distribution: {
    green: number
    amber: number
    red: number
    not_submitted: number
  } | null
  recent_activity: Array<{
    entity_type: string
    entity_id: string
    action: string
    actor_name: string
    timestamp: string
  }> | null
  pending_my_action: Array<{
    task_id: string
    title: string
    status: string
    eta: string | null
  }> | null
}

type SortDir = 'asc' | 'desc'

// ─── Sub-components ────────────────────────────────────────────────────────────

/**
 * CollapsibleSection — section wrapper with accessible chevron toggle.
 * Used for KPI Summary, Compliance Summary, Discrepancy Summary,
 * RAG Distribution, Pending My Action, Recent Activities.
 */
function CollapsibleSection({
  id,
  title,
  meta,
  expanded,
  onToggle,
  children,
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
      <button
        className="dashboard-section__header"
        aria-expanded={expanded}
        aria-controls={`section-body-${id}`}
        onClick={onToggle}
      >
        <span className="dashboard-section__chevron" aria-hidden="true">▶</span>
        <span className="dashboard-section__title">{title}</span>
        {meta && <span className="dashboard-section__meta">{meta}</span>}
      </button>
      {expanded && (
        <div
          id={`section-body-${id}`}
          className="dashboard-section__body"
          role="region"
          aria-labelledby={`section-header-${id}`}
        >
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * Plain (read-only) summary card — no border accent, no click affordance.
 * Use for KPI Summary, Compliance Summary, Discrepancy Summary cards.
 */
function SummaryCard({
  label,
  value,
  sub,
  valueVariant,
}: {
  label: string
  value: string | number
  sub?: string
  valueVariant?: 'not-met' | 'amber' | 'good'
}) {
  const valueClass = valueVariant
    ? `summary-card__value summary-card__value--${valueVariant}`
    : 'summary-card__value'

  return (
    <div className="summary-card">
      <div className="summary-card__label">{label}</div>
      <div className={valueClass}>{value}</div>
      {sub && <div className="summary-card__sub">{sub}</div>}
    </div>
  )
}

/**
 * Interactive summary card — gold-600 3px left border, hover → paper-1,
 * arrow-right icon top-right, cursor pointer.
 * Design system v1.8 named pattern — use whenever a summary card navigates.
 * Expected to recur on Discrepancy Detail and Approval Chains.
 */
function RagCard({
  label,
  value,
  sub,
  valueVariant,
  onClick,
}: {
  label: string
  value: number
  sub: string
  valueVariant?: 'rag-green' | 'rag-amber' | 'rag-red'
  onClick: () => void
}) {
  const valueClass = valueVariant
    ? `summary-card__value summary-card__value--${valueVariant}`
    : 'summary-card__value'

  return (
    <div
      className="interactive-summary-card"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } }}
    >
      <span className="interactive-summary-card__arrow" aria-hidden="true">→</span>
      <div className="summary-card__label">{label}</div>
      <div className={valueClass}>{value}</div>
      <div className="summary-card__sub">{sub}</div>
    </div>
  )
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()

  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showDeptBanner, setShowDeptBanner] = useState(false)

  // Section expand/collapse defaults per spec:
  // expanded: RAG Distribution, Pending My Action (most actionable)
  // collapsed: KPI Summary, Compliance Summary, Discrepancy Summary, Recent Activities
  const [sections, setSections] = useState<Record<string, boolean>>({
    kpi: false,
    compliance: false,
    discrepancy: false,
    rag: true,
    pending: true,
    recent: false,
  })

  // Sort state for Pending My Action table
  const [pendingSort, setPendingSort] = useState<{ key: 'title' | 'eta'; dir: SortDir }>({
    key: 'eta',
    dir: 'asc',
  })

  // Sort state for Recent Activities table
  const [recentSort, setRecentSort] = useState<{ key: 'actor_name' | 'timestamp'; dir: SortDir }>({
    key: 'timestamp',
    dir: 'desc',
  })

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await apiFetch('/api/v1/dashboard', { signal: controller.signal })
        if (!response.ok) throw new Error('Failed to fetch dashboard data')
        setData(await response.json())
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (data) {
      setShowDeptBanner(!data.department_id)
    }
  }, [data])

  const toggleSection = (key: string) =>
    setSections(prev => ({ ...prev, [key]: !prev[key] }))

  const cyclePendingSort = (key: 'title' | 'eta') => {
    setPendingSort(prev =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' }
    )
  }

  const cycleRecentSort = (key: 'actor_name' | 'timestamp') => {
    setRecentSort(prev =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' }
    )
  }

  const sortIndicator = (key: string, activeKey: string, dir: SortDir) => {
    if (key !== activeKey) return <span className="sort-indicator">↕</span>
    return <span className="sort-indicator">{dir === 'asc' ? '↑' : '↓'}</span>
  }

  // ── Loading / error states ──────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="dashboard">
        <div className="loading-state">Loading dashboard…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="error-banner">{error}</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="dashboard">
        <div className="empty-state">No dashboard data available.</div>
      </div>
    )
  }

  // ── Derived display values ──────────────────────────────────────────────────

  const contextLine = [
    data.role,
    data.school_id || null,
    data.department_id || null,
  ]
    .filter(Boolean)
    .join(' · ')

  const ts = data.task_summary

  // Sorted table data
  const sortedPending = data.pending_my_action
    ? sortItems(data.pending_my_action, pendingSort.key, pendingSort.dir)
    : []

  const sortedRecent = data.recent_activity
    ? sortItems(data.recent_activity, recentSort.key, recentSort.dir)
    : []

  // Section meta summaries
  const kpiMeta = data.kpi_summary
    ? `${data.kpi_summary.met}/${data.kpi_summary.total_kpis} met`
    : undefined
  const complianceMeta = data.compliance_summary
    ? `${data.compliance_summary.pct_submitted}% submitted`
    : undefined
  const discrepancyMeta = data.discrepancy_summary
    ? `${data.discrepancy_summary.open_discrepancies} open`
    : undefined
  const ragMeta = data.rag_distribution
    ? `${data.rag_distribution.green} green · ${data.rag_distribution.amber} amber · ${data.rag_distribution.red} red`
    : undefined
  const pendingMeta = data.pending_my_action
    ? `${data.pending_my_action.length} item${data.pending_my_action.length !== 1 ? 's' : ''}`
    : undefined
  const recentMeta = data.recent_activity
    ? `${data.recent_activity.length} recent`
    : undefined

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="dashboard">

      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">Dashboard</div>
          {/* Single consolidated H1 — role/school/dept are the content, not decoration */}
          <h1>Welcome back — {contextLine || 'your workspace'}</h1>
        </div>
      </div>

      {/* ── Department-less user banner ──────────────────────────────────────── */}
      {showDeptBanner && (
        <div className="banner banner-warning" style={{ margin: 'var(--space-5) var(--space-10) 0' }}>
          <div className="banner-content">
            <div className="banner-message">
              <strong>You're not part of a department yet</strong>
              <span>Request one to unlock full functionality</span>
            </div>
            <button
              className="banner-dismiss"
              onClick={() => setShowDeptBanner(false)}
              aria-label="Dismiss banner"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* ── Stats ribbon — flat ink-900, no gradient ─────────────────────────── */}
      {ts && (
        <div className="ribbon">
          <div className="ribbon-item">
            <div className="ribbon-num">{ts.open_tasks}</div>
            <div className="ribbon-label">Open Tasks</div>
          </div>
          <div className="ribbon-item warn">
            <div className="ribbon-num">{ts.overdue_tasks}</div>
            <div className="ribbon-label">Overdue</div>
          </div>
          <div className="ribbon-item">
            <div className="ribbon-num">{ts.completed_this_period}</div>
            <div className="ribbon-label">Completed</div>
          </div>
          <div className="ribbon-item accent">
            <div className="ribbon-num">{ts.pct_on_time}%</div>
            <div className="ribbon-label">On Time Rate</div>
          </div>
        </div>
      )}

      {/* ── KPI Summary — default collapsed ─────────────────────────────────── */}
      {data.kpi_summary && (
        <CollapsibleSection
          id="kpi"
          title="KPI Summary"
          meta={kpiMeta}
          expanded={sections.kpi}
          onToggle={() => toggleSection('kpi')}
        >
          <div className="summary-card-grid">
            <SummaryCard
              label="Total KPIs"
              value={data.kpi_summary.total_kpis}
              sub={`${data.kpi_summary.pct_met}% met this period`}
            />
            <SummaryCard
              label="Met"
              value={data.kpi_summary.met}
              sub="On track"
              valueVariant="good"
            />
            <SummaryCard
              label="Not Met"
              value={data.kpi_summary.not_met}
              sub="Need attention"
              valueVariant={data.kpi_summary.not_met > 0 ? 'not-met' : undefined}
            />
            <SummaryCard
              label="Amber"
              value={data.kpi_summary.amber}
              sub="Warning zone"
              valueVariant={data.kpi_summary.amber > 0 ? 'amber' : undefined}
            />
          </div>
        </CollapsibleSection>
      )}

      {/* ── Compliance Summary — default collapsed ───────────────────────────── */}
      {data.compliance_summary && (
        <CollapsibleSection
          id="compliance"
          title="Compliance Summary"
          meta={complianceMeta}
          expanded={sections.compliance}
          onToggle={() => toggleSection('compliance')}
        >
          <div className="summary-card-grid">
            <SummaryCard
              label="Total Due"
              value={data.compliance_summary.total_due}
              sub="This period"
            />
            <SummaryCard
              label="Submitted"
              value={data.compliance_summary.submitted}
              sub={`${data.compliance_summary.pct_submitted}% submission rate`}
              valueVariant="good"
            />
            <SummaryCard
              label="Missed"
              value={data.compliance_summary.missed}
              sub="Not submitted"
              valueVariant={data.compliance_summary.missed > 0 ? 'not-met' : undefined}
            />
            <SummaryCard
              label="Late"
              value={data.compliance_summary.late}
              sub="Submitted after deadline"
              valueVariant={data.compliance_summary.late > 0 ? 'amber' : undefined}
            />
          </div>
        </CollapsibleSection>
      )}

      {/* ── Discrepancy Summary — default collapsed ──────────────────────────── */}
      {data.discrepancy_summary && (
        <CollapsibleSection
          id="discrepancy"
          title="Discrepancy Summary"
          meta={discrepancyMeta}
          expanded={sections.discrepancy}
          onToggle={() => toggleSection('discrepancy')}
        >
          <div className="summary-card-grid">
            <SummaryCard
              label="Open"
              value={data.discrepancy_summary.open_discrepancies}
              sub={`${data.discrepancy_summary.under_investigation} under investigation`}
              valueVariant={data.discrepancy_summary.open_discrepancies > 0 ? 'not-met' : undefined}
            />
            <SummaryCard
              label="Pending Approval"
              value={data.discrepancy_summary.pending_approval}
              sub="Awaiting review"
              valueVariant={data.discrepancy_summary.pending_approval > 0 ? 'amber' : undefined}
            />
            <SummaryCard
              label="Resolved This Period"
              value={data.discrepancy_summary.resolved_this_period}
              sub="Closed out"
              valueVariant="good"
            />
            <SummaryCard
              label="SLA Breached"
              value={data.discrepancy_summary.breached_sla}
              sub="Critical — overdue SLA"
              valueVariant={data.discrepancy_summary.breached_sla > 0 ? 'not-met' : undefined}
            />
          </div>
        </CollapsibleSection>
      )}

      {/* ── RAG Distribution — default expanded, interactive cards ───────────── */}
      {data.rag_distribution && (
        <CollapsibleSection
          id="rag"
          title="RAG Distribution"
          meta={ragMeta}
          expanded={sections.rag}
          onToggle={() => toggleSection('rag')}
        >
          {/* Interactive cards (gold-600 left border + hover + arrow) live alongside
              plain cards so the contrast between the two types carries the affordance. */}
          <div className="summary-card-grid">
            <RagCard
              label="Green"
              value={data.rag_distribution.green}
              sub="On track — view in KPI Verification"
              valueVariant="rag-green"
              onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'green' } })}
            />
            <RagCard
              label="Amber"
              value={data.rag_distribution.amber}
              sub="Warning — view in KPI Verification"
              valueVariant="rag-amber"
              onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'amber' } })}
            />
            <RagCard
              label="Red"
              value={data.rag_distribution.red}
              sub="Critical — view in KPI Verification"
              valueVariant="rag-red"
              onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'red' } })}
            />
            <RagCard
              label="Not Submitted"
              value={data.rag_distribution.not_submitted}
              sub="Missing — view in KPI Verification"
              onClick={() => navigate('/kpi-verification', { state: { filterStatus: 'not_submitted' } })}
            />
          </div>
        </CollapsibleSection>
      )}

      {/* ── Pending My Action — default expanded ─────────────────────────────── */}
      {sortedPending.length > 0 && (
        <CollapsibleSection
          id="pending"
          title="Pending My Action"
          meta={pendingMeta}
          expanded={sections.pending}
          onToggle={() => toggleSection('pending')}
        >
          {/* Desktop/tablet table */}
          <div className="table-wrap dashboard-table-wrap dashboard-table-pending">
            <table className="data-table">
              <thead>
                <tr>
                  <th
                    className="sortable"
                    onClick={() => cyclePendingSort('title')}
                    aria-sort={pendingSort.key === 'title' ? (pendingSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Task {sortIndicator('title', pendingSort.key, pendingSort.dir)}
                  </th>
                  <th>Status</th>
                  <th
                    className="sortable col-eta"
                    onClick={() => cyclePendingSort('eta')}
                    aria-sort={pendingSort.key === 'eta' ? (pendingSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    ETA {sortIndicator('eta', pendingSort.key, pendingSort.dir)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedPending.map((task, i) => (
                  <tr
                    key={`${task.task_id}-${i}`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/tasks/${task.task_id}`)}
                  >
                    <td>
                      <span style={{ fontWeight: 600, color: 'var(--ink-900)' }}>
                        {task.title}
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill ${task.status === 'open' ? 'pending' : task.status === 'in_progress' ? 'progress' : 'completed'}`}>
                        {task.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="col-eta" style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)' }}>
                      {formatDate(task.eta)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked cards */}
          <div className="dashboard-mobile-cards">
            {sortedPending.map((task, i) => (
              <div
                key={`mob-pending-${task.task_id}-${i}`}
                className="dashboard-mobile-card"
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/tasks/${task.task_id}`)}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/tasks/${task.task_id}`) }}
                style={{ cursor: 'pointer' }}
              >
                <div className="dashboard-mobile-card__title">{task.title}</div>
                <div className="dashboard-mobile-card__meta">
                  <span className={`status-pill ${task.status === 'open' ? 'pending' : task.status === 'in_progress' ? 'progress' : 'completed'}`}>
                    {task.status.replace('_', ' ')}
                  </span>
                  <span>ETA: {formatDate(task.eta)}</span>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* ── Recent Activities — default collapsed ────────────────────────────── */}
      {sortedRecent.length > 0 && (
        <CollapsibleSection
          id="recent"
          title="Recent Activities"
          meta={recentMeta}
          expanded={sections.recent}
          onToggle={() => toggleSection('recent')}
        >
          {/* Desktop/tablet table */}
          <div className="table-wrap dashboard-table-wrap dashboard-table-recent">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th className="col-action">Action</th>
                  <th
                    className="sortable"
                    onClick={() => cycleRecentSort('actor_name')}
                    aria-sort={recentSort.key === 'actor_name' ? (recentSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Actor {sortIndicator('actor_name', recentSort.key, recentSort.dir)}
                  </th>
                  <th
                    className="sortable col-time"
                    onClick={() => cycleRecentSort('timestamp')}
                    aria-sort={recentSort.key === 'timestamp' ? (recentSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Time {sortIndicator('timestamp', recentSort.key, recentSort.dir)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedRecent.map((activity, i) => (
                  <tr key={`${activity.entity_id}-${i}`}>
                    <td>
                      <span className="status-pill progress">{activity.entity_type}</span>
                    </td>
                    <td className="col-action">{activity.action}</td>
                    <td style={{ fontWeight: 500 }}>{activity.actor_name}</td>
                    <td className="col-time" style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)' }}>
                      {formatDateTime(activity.timestamp)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked cards */}
          <div className="dashboard-mobile-cards">
            {sortedRecent.map((activity, i) => (
              <div
                key={`mob-recent-${activity.entity_id}-${i}`}
                className="dashboard-mobile-card"
              >
                <div className="dashboard-mobile-card__title">{activity.action}</div>
                <div className="dashboard-mobile-card__meta">
                  <span className="status-pill progress">{activity.entity_type}</span>
                  <span>{activity.actor_name}</span>
                  <span>{formatDateTime(activity.timestamp)}</span>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

    </div>
  )
}

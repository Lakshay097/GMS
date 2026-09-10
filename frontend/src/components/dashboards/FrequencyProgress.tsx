import './FrequencyProgress.css'

interface SchoolFrequencyRow {
  school_id: string
  school_name: string
  total_kpis: number
  submitted: number
  pct_complete: number
}

interface FrequencyPeriod {
  frequency: string
  label: string
  total_kpis: number
  submitted: number
  pending: number
  pct_complete: number
  period_start: string
  period_end: string
  kra_names?: string[]
  schools?: SchoolFrequencyRow[]
}

interface FrequencyProgressData {
  periods: FrequencyPeriod[]
  overall_submitted: number
  overall_total: number
  overall_pct: number
}

interface FrequencyProgressProps {
  data: FrequencyProgressData
  expanded: boolean
  onToggle: () => void
}

const FREQ_LABELS: Record<string, string> = {
  daily: 'D',
  weekly: 'W',
  monthly: 'M',
  quarterly: 'Q',
  half_yearly: 'H',
  annual: 'A',
}

const FREQ_COLORS: Record<string, string> = {
  daily: '#6366f1',       // indigo
  weekly: '#8b5cf6',      // violet
  monthly: '#3b82f6',     // blue
  quarterly: '#f59e0b',   // amber
  half_yearly: '#10b981',  // emerald
  annual: '#ef4444',       // red
}

function formatDateShort(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function progressColor(pct: number): string {
  if (pct >= 80) return 'var(--green-600, #16a34a)'
  if (pct >= 40) return 'var(--amber-600, #d97706)'
  return 'var(--red-600, #dc2626)'
}

export default function FrequencyProgress({ data, expanded, onToggle }: FrequencyProgressProps) {
  if (!data || data.periods.length === 0) return null

  const meta = `${data.overall_submitted}/${data.overall_total} submitted · ${data.overall_pct}%`

  return (
    <div className="dashboard-section">
      <button
        className="dashboard-section__header"
        aria-expanded={expanded}
        aria-controls="section-body-freq-progress"
        onClick={onToggle}
      >
        <span className="dashboard-section__chevron" aria-hidden="true">▶</span>
        <span className="dashboard-section__title">KPI Progress by Frequency</span>
        <span className="dashboard-section__meta">{meta}</span>
      </button>
      {expanded && (
        <div id="section-body-freq-progress" className="dashboard-section__body">

          {/* Overall progress bar */}
          <div className="freq-overall">
            <div className="freq-overall__label">
              <span>Overall Completion</span>
              <span className="freq-overall__pct">{data.overall_pct}%</span>
            </div>
            <div className="freq-bar freq-bar--lg">
              <div
                className="freq-bar__fill"
                style={{
                  width: `${data.overall_pct}%`,
                  backgroundColor: progressColor(data.overall_pct),
                }}
              />
            </div>
            <div className="freq-overall__detail">
              {data.overall_submitted} of {data.overall_total} KPIs submitted this period
            </div>
          </div>

          {/* Per-frequency cards */}
          <div className="freq-grid">
            {data.periods.map(p => {
              const barColor = FREQ_COLORS[p.frequency] || '#6b7280'
              return (
                <div key={p.frequency} className="freq-card">
                  <div className="freq-card__header">
                    <span className="freq-card__icon" style={{ fontSize: 'var(--text-micro)', fontWeight: 700, color: 'var(--ink-500)' }}>{FREQ_LABELS[p.frequency] || '?'}</span>
                    <span className="freq-card__label">{p.label}</span>
                  </div>

                  {p.kra_names && p.kra_names.length > 0 && (
                    <div className="freq-card__kra" title={`KRAs: ${p.kra_names.join(', ')}`}>
                      {p.kra_names.length === 1 ? p.kra_names[0] : `${p.kra_names.length} KRAs`}
                    </div>
                  )}

                  <div className="freq-card__bar-wrap">
                    <div className="freq-bar">
                      <div
                        className="freq-bar__fill"
                        style={{ width: `${p.pct_complete}%`, backgroundColor: barColor }}
                      />
                    </div>
                    <span className="freq-card__pct">{p.pct_complete}%</span>
                  </div>

                  <div className="freq-card__stats">
                    <span className="freq-card__stat">
                      <span className="freq-card__stat-num" style={{ color: barColor }}>{p.submitted}</span>
                      <span className="freq-card__stat-label">done</span>
                    </span>
                    <span className="freq-card__stat">
                      <span className="freq-card__stat-num">{p.pending}</span>
                      <span className="freq-card__stat-label">pending</span>
                    </span>
                    <span className="freq-card__stat">
                      <span className="freq-card__stat-num">{p.total_kpis}</span>
                      <span className="freq-card__stat-label">total</span>
                    </span>
                  </div>

                  <div className="freq-card__period">
                    {formatDateShort(p.period_start)} – {formatDateShort(p.period_end)}
                  </div>

                  {p.schools && p.schools.length > 1 && (
                    <div className="freq-card__schools">
                      {p.schools.map(s => (
                        <div key={s.school_id} className="freq-card__school-row" title={`${s.school_name}: ${s.submitted} of ${s.total_kpis} KPIs submitted`}>
                          <span className="freq-card__school-name">{s.school_name}</span>
                          <span className="freq-card__school-nums">
                            {s.total_kpis > 0 ? `${s.submitted}/${s.total_kpis} · ${s.pct_complete}%` : `${s.submitted} submitted`}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

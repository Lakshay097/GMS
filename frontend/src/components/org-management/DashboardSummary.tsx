import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'
import { useSchools, useDepartments } from './useOrgData'

interface DashboardData {
  total_schools: number
  total_departments: number
  total_kras: number
  total_kpis: number
  total_entries: number
  entries_by_status: Record<string, number>
  entries_by_school: Array<{
    school_id: string
    school_name: string
    pass: number
    fail: number
    pending: number
  }>
  entries_by_kpi: Array<{
    kpi_id: string
    title: string
    pass: number
    fail: number
    pending: number
  }>
}

export default function DashboardSummary() {
  const { schools } = useSchools()
  const [selectedSchoolId, setSelectedSchoolId] = useState<string>('')
  const { departments } = useDepartments(selectedSchoolId || null)
  const [selectedDeptId, setSelectedDeptId] = useState<string>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchDashboard = async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (selectedSchoolId) params.set('school_id', selectedSchoolId)
    if (selectedDeptId) params.set('department_id', selectedDeptId)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)

    try {
      const res = await apiFetch(`/api/v1/dashboard/summary?${params}`)
      if (res.ok) {
        const d = await res.json()
        setData(d)
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboard()
  }, [selectedSchoolId, selectedDeptId, dateFrom, dateTo])

  const statusColor = (status: string) => {
    switch (status) {
      case 'pass': return '#22c55e'
      case 'fail': return '#ef4444'
      case 'pending': return '#f59e0b'
      case 'under_review': return '#3b82f6'
      default: return '#6b7280'
    }
  }

  const passRate = (pass: number, fail: number) => {
    const total = pass + fail
    if (total === 0) return '—'
    return `${Math.round((pass / total) * 100)}%`
  }

  if (loading && !data) {
    return <div className="dashboard-loading">Loading dashboard...</div>
  }

  return (
    <div className="dashboard-summary">
      <h2>Dashboard</h2>

      {/* Filters */}
      <div className="dashboard-filters">
        <label>
          School
          <select value={selectedSchoolId} onChange={e => {
            setSelectedSchoolId(e.target.value)
            setSelectedDeptId('')
          }}>
            <option value="">All Schools</option>
            {schools.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>

        <label>
          Department
          <select
            value={selectedDeptId}
            onChange={e => setSelectedDeptId(e.target.value)}
            disabled={!selectedSchoolId}
          >
            <option value="">All Departments</option>
            {departments.map(d => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </label>

        <label>
          From
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
        </label>

        <label>
          To
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} />
        </label>
      </div>

      {data && (
        <>
          {/* Summary Cards */}
          <div className="summary-cards">
            <div className="summary-card">
              <div className="card-value">{data.total_schools}</div>
              <div className="card-label">Schools</div>
            </div>
            <div className="summary-card">
              <div className="card-value">{data.total_departments}</div>
              <div className="card-label">Departments</div>
            </div>
            <div className="summary-card">
              <div className="card-value">{data.total_kras}</div>
              <div className="card-label">KRAs</div>
            </div>
            <div className="summary-card">
              <div className="card-value">{data.total_kpis}</div>
              <div className="card-label">KPIs</div>
            </div>
            <div className="summary-card">
              <div className="card-value">{data.total_entries}</div>
              <div className="card-label">Entries</div>
            </div>
          </div>

          {/* Status Breakdown */}
          <div className="status-breakdown">
            <h3>Entries by Status</h3>
            <div className="status-bars">
              {Object.entries(data.entries_by_status).map(([status, count]) => (
                <div key={status} className="status-bar-item">
                  <span className="status-dot" style={{ backgroundColor: statusColor(status) }} />
                  <span className="status-label">{status}</span>
                  <span className="status-count">{count}</span>
                </div>
              ))}
              {Object.keys(data.entries_by_status).length === 0 && (
                <div className="empty-state">No entries yet</div>
              )}
            </div>
          </div>

          {/* By School */}
          {data.entries_by_school.length > 0 && (
            <div className="by-school">
              <h3>Pass Rate by School</h3>
              <table>
                <thead>
                  <tr>
                    <th>School</th>
                    <th>Pass</th>
                    <th>Fail</th>
                    <th>Pending</th>
                    <th>Pass Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {data.entries_by_school.map(row => (
                    <tr key={row.school_id}>
                      <td>{row.school_name}</td>
                      <td style={{ color: '#22c55e' }}>{row.pass || 0}</td>
                      <td style={{ color: '#ef4444' }}>{row.fail || 0}</td>
                      <td style={{ color: '#f59e0b' }}>{row.pending || 0}</td>
                      <td>{passRate(row.pass || 0, row.fail || 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* By KPI */}
          {data.entries_by_kpi.length > 0 && (
            <div className="by-kpi">
              <h3>Pass Rate by KPI</h3>
              <table>
                <thead>
                  <tr>
                    <th>KPI</th>
                    <th>Pass</th>
                    <th>Fail</th>
                    <th>Pending</th>
                    <th>Pass Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {data.entries_by_kpi.map(row => (
                    <tr key={row.kpi_id}>
                      <td>{row.title}</td>
                      <td style={{ color: '#22c55e' }}>{row.pass || 0}</td>
                      <td style={{ color: '#ef4444' }}>{row.fail || 0}</td>
                      <td style={{ color: '#f59e0b' }}>{row.pending || 0}</td>
                      <td>{passRate(row.pass || 0, row.fail || 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

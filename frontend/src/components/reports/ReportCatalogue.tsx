import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useUser } from '@clerk/clerk-react'
import { apiFetch } from '../../lib/api'
import './ReportCatalogue.css'

interface Report {
  slug: string
  title: string
  description: string
  available_formats: string[]
  required_roles: string[]
}

export default function ReportCatalogue() {
  const { user } = useUser()
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  // Current user's roles (lowercased for comparison)
  const userRoles = useMemo(() => {
    const roles = (user?.publicMetadata?.roles as string[]) || []
    return roles.map(r => r.toLowerCase())
  }, [user])

  useEffect(() => {
    fetchReports()
  }, [])

  const fetchReports = async () => {
    try {
      setLoading(true)
      const response = await apiFetch('/api/v1/reports')
      if (!response.ok) throw new Error('Failed to fetch reports')
      const data = await response.json()
      setReports(data.reports || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setReports([])
    } finally {
      setLoading(false)
    }
  }

  // Search matches title, description, and required-role names
  const filteredReports = useMemo(() => {
    if (!searchTerm.trim()) return reports
    const term = searchTerm.toLowerCase()
    return reports.filter(report =>
      report.title.toLowerCase().includes(term) ||
      report.description.toLowerCase().includes(term) ||
      report.required_roles.some(role => role.toLowerCase().includes(term))
    )
  }, [reports, searchTerm])

  /** Check if user qualifies for this report */
  const userQualifies = (report: Report): boolean => {
    if (!report.required_roles || report.required_roles.length === 0) return true
    return report.required_roles.some(role => userRoles.includes(role.toLowerCase()))
  }

  if (loading) return <div className="loading-state">Loading reports…</div>
  if (error) return <div className="error">{error}</div>

  return (
    <div className="report-catalogue page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <div className="eyebrow">Reports</div>
          <h1>Report Catalogue</h1>
        </div>
        <div className="report-search">
          <span className="report-search__icon" aria-hidden="true">🔍</span>
          <input
            type="text"
            placeholder="Search reports…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="report-search__input"
          />
        </div>
      </div>

      {/* ── Report Cards Grid ────────────────────────────────────────── */}
      {filteredReports.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">📄</div>
          <h3>{searchTerm ? 'No matching reports' : 'No reports available'}</h3>
          <p>{searchTerm ? 'Try a different search term.' : 'Check back later or contact your administrator for report access.'}</p>
        </div>
      ) : (
        <div className="report-grid">
          {filteredReports.map((report, index) => (
            <ReportCard
              key={`${report.slug}-${index}`}
              report={report}
              qualifies={userQualifies(report)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ReportCard({ report, qualifies }: { report: Report; qualifies: boolean }) {
  const requiredRolesText = report.required_roles?.length > 0
    ? `Requires: ${report.required_roles.join(' or ')} role`
    : ''

  return (
    <div className="report-card">
      <h3 className="report-card__title">{report.title}</h3>
      <p className="report-card__desc">{report.description}</p>

      {/* Required Roles */}
      {report.required_roles && report.required_roles.length > 0 && (
        <div className="report-card__section">
          <span className="report-card__label">Required Roles</span>
          <div className="report-card__badges">
            {report.required_roles.map((role, i) => {
              const isQualified = qualifies // if user qualifies for the report, all role badges get tint
              return (
                <span
                  key={`role-${i}`}
                  className={`badge badge-role ${isQualified ? 'badge-role--qualified' : ''}`}
                >
                  {role}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* Available Formats */}
      {report.available_formats && report.available_formats.length > 0 && (
        <div className="report-card__section">
          <span className="report-card__label">Available Formats</span>
          <div className="report-card__badges">
            {report.available_formats.map((format, i) => (
              <span key={`format-${i}`} className="badge badge-format">
                {format.toUpperCase()}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Run Report button — disabled + tooltip when role-gated */}
      {qualifies ? (
        <Link
          to={`/reports/${report.slug}`}
          className="btn btn-primary btn-full"
        >
          Run Report
        </Link>
      ) : (
        <button
          className="btn btn-primary btn-full"
          disabled
          title={requiredRolesText}
        >
          Run Report
        </button>
      )}
    </div>
  )
}

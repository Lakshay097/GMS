import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import {
  ArrowLeft,
  Filter,
  ChevronDown,
  ChevronUp,
  Loader2,
  CheckCircle,
  XCircle,
  Download,
  FileText,
  RotateCcw,
} from 'lucide-react'
import './ReportRunner.css'

/* ── Types ────────────────────────────────────────────────────────────────── */

interface ReportData {
  report_type: string
  generated_at: string
  total_rows: number
  page: number
  page_size: number
  has_next: boolean
  columns?: string[]
  rows?: Array<Record<string, any>>
}

type ExportStatus = 'idle' | 'queuing' | 'in-progress' | 'ready' | 'failed'

interface ExportJob {
  job_id: string
  status: string
  result_url?: string
  error_detail?: string
  row_count?: number
  file_size_bytes?: number
}

/* ── Report type → has-status-dimension mapping ────────────────────────────
   Only report types whose rows naturally include a "status" column render
   the Status filter.  Derived from inspecting each handler's SQL in
   report_service.py.  Interim default per v3.3: if unsure, omit.         */

const REPORTS_WITH_STATUS = new Set([
  'compliance',        // compliance_status
  'audit',             // auto_result, rag_status
  'pending_audits',    // compliance_status (filtered to submitted)
  'task_aging',        // status
  'open_discrepancies', // state
  'discrepancy_sla',   // state
  'overdue_kpi',       // compliance_status
  'escalation_summary', // status
  'inventory',         // status
  'compliance_dashboard', // aggregated compliance status counts
])

/* ── Helper: format report slug into human-readable title ────────────────── */

function formatTitle(slug: string): string {
  return slug
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/* ── Helper: format file size ────────────────────────────────────────────── */

function formatFileSize(bytes?: number): string {
  if (bytes == null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/* ── Helper: format cell values ──────────────────────────────────────────── */

function formatCellValue(value: any): string {
  if (value === null || value === undefined) return '–'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (value instanceof Date) return value.toLocaleString()
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    try {
      return new Date(value).toLocaleString()
    } catch {
      return value
    }
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/* ── Export Status Chip ──────────────────────────────────────────────────── */

function ExportStatusChip({
  status,
  job,
  onDownload,
  onRetry,
}: {
  status: ExportStatus
  job: ExportJob | null
  onDownload: () => void
  onRetry: () => void
}) {
  if (status === 'idle') return null

  return (
    <span className={`export-chip export-chip--${status}`}>
      {status === 'queuing' && (
        <>
          <Loader2 className="export-chip__icon export-chip__icon--spin" size={14} />
          <span>Queuing…</span>
        </>
      )}
      {status === 'in-progress' && (
        <>
          <Loader2 className="export-chip__icon export-chip__icon--spin" size={14} />
          <span>Export in progress…</span>
        </>
      )}
      {status === 'ready' && (
        <>
          <CheckCircle size={14} />
          <span>Export ready{job?.row_count ? ` (${job.row_count} rows${job?.file_size_bytes ? `, ${formatFileSize(job.file_size_bytes)}` : ''})` : ''}</span>
          <button className="export-chip__download" onClick={onDownload} title="Download file">
            <Download size={14} />
          </button>
        </>
      )}
      {status === 'failed' && (
        <>
          <XCircle size={14} />
          <span>Export failed{job?.error_detail ? `: ${job.error_detail}` : ''}</span>
          <button className="export-chip__retry" onClick={onRetry} title="Retry export">
            <RotateCcw size={14} />
          </button>
        </>
      )}
    </span>
  )
}

/* ── Main Component ──────────────────────────────────────────────────────── */

export default function ReportRunner() {
  const { reportType } = useParams()

  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  // Filters
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    status: '',
  })
  const [filtersExpanded, setFiltersExpanded] = useState(false)

  // Export
  const [exportFormat, setExportFormat] = useState<'csv' | 'excel' | 'pdf'>('excel')
  const [exportStatus, setExportStatus] = useState<ExportStatus>('idle')
  const [exportJob, setExportJob] = useState<ExportJob | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Derived columns from first row
  const columns = data?.rows?.length ? Object.keys(data.rows[0]) : data?.columns ?? []

  /* ── Scroll shadow detection ───────────────────────────────────────────── */
  const updateScrollShadows = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const tolerance = 2
    el.classList.toggle('has-scroll-left', el.scrollLeft > tolerance)
    el.classList.toggle(
      'has-scroll-right',
      el.scrollLeft < el.scrollWidth - el.clientWidth - tolerance
    )
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    updateScrollShadows()
    el.addEventListener('scroll', updateScrollShadows, { passive: true })
    window.addEventListener('resize', updateScrollShadows)
    return () => {
      el.removeEventListener('scroll', updateScrollShadows)
      window.removeEventListener('resize', updateScrollShadows)
    }
  }, [data, updateScrollShadows])

  const hasStatusFilter = reportType ? REPORTS_WITH_STATUS.has(reportType) : false

  /* ── Fetch report data ─────────────────────────────────────────────────── */

  const fetchReport = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '100',
      })
      if (filters.date_from) params.set('date_from', filters.date_from)
      if (filters.date_to) params.set('date_to', filters.date_to)
      if (hasStatusFilter && filters.status) params.set('status', filters.status)

      const response = await apiFetch(`/api/v1/reports/${reportType}?${params}`)
      if (!response.ok) throw new Error('Failed to run report')
      const result = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [reportType, page, filters, hasStatusFilter])

  useEffect(() => {
    if (reportType) fetchReport()
  }, [reportType, page, filters, fetchReport])

  /* ── Export flow with polling ──────────────────────────────────────────── */

  const startPolling = useCallback((jobId: string) => {
    setExportStatus('in-progress')
    if (pollRef.current) clearInterval(pollRef.current)

    pollRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/v1/reports/export/${jobId}`)
        if (!res.ok) return // keep polling
        const job: ExportJob = await res.json()
        setExportJob(job)

        if (job.status === 'completed') {
          setExportStatus('ready')
          if (pollRef.current) clearInterval(pollRef.current)
        } else if (job.status === 'failed') {
          setExportStatus('failed')
          if (pollRef.current) clearInterval(pollRef.current)
        }
        // 'pending' or 'processing' → keep polling
      } catch {
        // network error — keep polling, will retry next tick
      }
    }, 1500)
  }, [])

  const handleExport = useCallback(async () => {
    try {
      setExportStatus('queuing')
      setExportJob(null)
      const response = await apiFetch('/api/v1/reports/export', {
        method: 'POST',
        body: JSON.stringify({
          report_type: reportType,
          format: exportFormat,
          filters: {
            date_from: filters.date_from || undefined,
            date_to: filters.date_to || undefined,
            status: hasStatusFilter && filters.status ? filters.status : undefined,
          },
        }),
      })

      if (!response.ok) throw new Error('Failed to queue export')
      const job: ExportJob = await response.json()

      if (job.status === 'completed') {
        // Phase 1: synchronous completion
        setExportStatus('ready')
        setExportJob(job)
      } else {
        // Async — start polling
        startPolling(job.job_id)
      }
    } catch (err) {
      setExportStatus('failed')
      setExportJob((prev) => ({
        ...prev,
        job_id: '',
        status: 'failed',
        error_detail: err instanceof Error ? err.message : 'Export failed',
      }))
    }
  }, [reportType, exportFormat, filters, hasStatusFilter, startPolling])

  const handleDownload = useCallback(() => {
    if (exportJob?.job_id) {
      window.open(`/api/v1/reports/export/${exportJob.job_id}/download`, '_blank')
    }
  }, [exportJob])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  /* ── Filter handlers ───────────────────────────────────────────────────── */

  const handleApplyFilters = () => {
    setPage(1) // reset to first page on filter change
  }

  const handleClearFilters = () => {
    setFilters({ date_from: '', date_to: '', status: '' })
    setPage(1)
  }

  /* ── Derived values ────────────────────────────────────────────────────── */

  const totalPages = data ? Math.ceil(data.total_rows / data.page_size) : 0
  const startRow = data ? (data.page - 1) * data.page_size + 1 : 0
  const endRow = data ? Math.min(data.page * data.page_size, data.total_rows) : 0

  const filterCount = [filters.date_from, filters.date_to, hasStatusFilter && filters.status].filter(Boolean).length

  /* ── Render ────────────────────────────────────────────────────────────── */

  return (
    <div className="report-runner page-shell">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="report-runner__header">
        <div className="report-runner__header-top">
          <Link to="/reports" className="report-runner__back btn btn-ghost btn-sm">
            <ArrowLeft size={16} />
            <span>Reports</span>
          </Link>
        </div>
        <div className="report-runner__header-main">
          <div>
            <span className="eyebrow">
              <span className="eyebrow__dot" />
              Report Runner
            </span>
            <h1>{formatTitle(reportType ?? '')}</h1>
          </div>
        </div>
      </div>

      {/* ── Filter Bar ──────────────────────────────────────────────────── */}
      {/* Desktop/tablet: inline row.  Mobile: collapsed into expandable panel. */}

      {/* Mobile filter toggle */}
      <div className="report-runner__filter-toggle">
        <button
          className="btn btn-ghost btn-sm report-runner__filter-toggle-btn"
          onClick={() => setFiltersExpanded(!filtersExpanded)}
        >
          <Filter size={16} />
          <span>Filters{filterCount > 0 ? ` (${filterCount})` : ''}</span>
          {filtersExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        {filterCount > 0 && (
          <button className="btn btn-ghost btn-sm" onClick={handleClearFilters}>
            Clear
          </button>
        )}
      </div>

      <div className={`report-runner__filters ${filtersExpanded ? 'report-runner__filters--expanded' : ''}`}>
        <div className="report-runner__filters-inner">
          <div className="report-runner__filter-group">
            <label className="report-runner__filter-label">Date From</label>
            <input
              type="date"
              className="input"
              value={filters.date_from}
              onChange={(e) => setFilters((p) => ({ ...p, date_from: e.target.value }))}
            />
          </div>
          <div className="report-runner__filter-group">
            <label className="report-runner__filter-label">Date To</label>
            <input
              type="date"
              className="input"
              value={filters.date_to}
              onChange={(e) => setFilters((p) => ({ ...p, date_to: e.target.value }))}
            />
          </div>
          {hasStatusFilter && (
            <div className="report-runner__filter-group">
              <label className="report-runner__filter-label">Status</label>
              <select
                className="input"
                value={filters.status}
                onChange={(e) => setFilters((p) => ({ ...p, status: e.target.value }))}
              >
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
                <option value="overdue">Overdue</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
              </select>
            </div>
          )}
          <div className="report-runner__filter-actions">
            <button className="btn btn-primary btn-sm" onClick={handleApplyFilters}>
              Apply Filters
            </button>
            {filterCount > 0 && (
              <button className="btn btn-ghost btn-sm" onClick={handleClearFilters}>
                Clear Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Export Row ───────────────────────────────────────────────────── */}
      <div className="report-runner__export-row">
        <div className="report-runner__export-controls">
          <select
            className="input report-runner__format-select"
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as 'csv' | 'excel' | 'pdf')}
          >
            <option value="csv">CSV</option>
            <option value="excel">Excel</option>
            <option value="pdf">PDF</option>
          </select>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleExport}
            disabled={exportStatus === 'queuing' || exportStatus === 'in-progress'}
          >
            <Download size={14} />
            <span>Export</span>
          </button>
        </div>
        <ExportStatusChip
          status={exportStatus}
          job={exportJob}
          onDownload={handleDownload}
          onRetry={handleExport}
        />
      </div>

      {/* ── Results Table ────────────────────────────────────────────────── */}

      {loading ? (
        <div className="report-runner__loading">
          <Loader2 className="report-runner__loading-icon" size={24} />
          <span>Loading report…</span>
        </div>
      ) : error ? (
        <div className="report-runner__error">
          <XCircle size={20} />
          <span>{error}</span>
          <button className="btn btn-ghost btn-sm" onClick={fetchReport}>
            Retry
          </button>
        </div>
      ) : !data || columns.length === 0 ? (
        <div className="report-runner__empty">
          <FileText size={40} />
          <p>No data available</p>
        </div>
      ) : (
        <>
          <div className="report-runner__table-scroll" ref={scrollRef}>
            <table className="data-table report-runner__table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col}>{col.replace(/_/g, ' ').toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows!.map((row, rowIndex) => (
                  <tr key={`row-${rowIndex}`}>
                    {columns.map((col) => (
                      <td key={`cell-${rowIndex}-${col}`}>
                        {formatCellValue(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Pagination ───────────────────────────────────────────────── */}
          <div className="report-runner__pagination">
            <div className="report-runner__pagination-info">
              <span className="report-runner__pagination-range">
                {startRow}–{endRow} of {data.total_rows.toLocaleString()}
              </span>
            </div>
            <div className="report-runner__pagination-controls">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </button>
              <span className="report-runner__pagination-page">
                Page {page} of {totalPages}
              </span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.has_next}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

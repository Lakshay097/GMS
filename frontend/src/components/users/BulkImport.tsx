import { useState } from 'react'
import { apiFetch } from '../../lib/api'
import './UserList.css'

/**
 * Bulk Create Users (spec §5): upload CSV/XLSX → server-side validation
 * preview → import → results with downloadable error report.
 * Passwords are never part of the import; imported users start PENDING and
 * activate via invitation code or admin-issued reset token.
 */

interface ImportRow {
  row_number: number
  name: string
  email: string
  employee_id?: string | null
  department: string
  manager_email?: string | null
  designation?: string | null
  location?: string | null
  role: string
}

interface ImportError {
  row_number: number
  email: string
  reason: string
}

interface PreviewResult {
  valid_rows: ImportRow[]
  errors: ImportError[]
  total: number
}

interface ImportResult {
  successful: number
  failed: number
  duplicates: number
  errors: ImportError[]
  created_user_ids: string[]
}

const TEMPLATE_HEADER = 'Name,Email,Employee ID,Department,Manager Email,Designation,Location,Role'

export default function BulkImport({ onClose, onDone }: { onClose: () => void; onDone?: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFile = async (f: File | null) => {
    setFile(f)
    setPreview(null)
    setResult(null)
    setError(null)
    if (!f) return
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', f)
      const res = await apiFetch('/api/v1/users/bulk-import/preview', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail || err?.error?.message || 'Failed to validate file')
      }
      setPreview(await res.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate file')
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await apiFetch('/api/v1/users/bulk-import', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail || err?.error?.message || 'Import failed')
      }
      setResult(await res.json())
      onDone?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setLoading(false)
    }
  }

  const downloadTemplate = () => {
    const sample = `${TEMPLATE_HEADER}\nJane Doe,jane.doe@school.edu,EMP-1042,Operations,manager@school.edu,Coordinator,Block A,checker\nJohn Smith,john.smith@school.edu,EMP-1043,Quality,manager@school.edu,Analyst,Block B,auditor\n`
    const blob = new Blob([sample], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'bulk-import-template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadErrorReport = () => {
    const rows = (result?.errors ?? preview?.errors ?? [])
    const csv = ['Row,Email,Reason', ...rows.map(e => `${e.row_number},"${e.email}","${e.reason.replace(/"/g, '""')}"`)].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'import-errors.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720, width: '92%' }}>
        <div className="modal-header">
          <h2>Bulk Create Users</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && <div className="alert alert-error"><span style={{ fontWeight: 700 }}>!</span><span>{error}</span></div>}

        {!result && (
          <>
            <p style={{ color: 'var(--ink-400)', fontSize: 'var(--text-sm)', margin: '0 0 var(--space-3)' }}>
              Upload a CSV or XLSX with columns: <strong>Name, Email, Employee ID, Department, Manager Email, Designation, Location, Role</strong>.
              Do not include passwords — imported users start as <strong>Pending</strong> and activate via an invitation code.
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-3)', alignItems: 'center' }}>
              <input
                type="file" accept=".csv,.xlsx,.xls"
                onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
                disabled={loading}
              />
              <button className="btn btn-ghost btn-sm" onClick={downloadTemplate}>Download template</button>
            </div>
          </>
        )}

        {loading && <div className="loading-state">Working…</div>}

        {preview && !result && (
          <div style={{ marginBottom: 'var(--space-3)' }}>
            <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-2)' }}>
              <span style={{ color: 'var(--green-500, #2ea043)', fontWeight: 600 }}>Valid: {preview.valid_rows.length}</span>
              <span style={{ color: 'var(--red-500, #da3633)', fontWeight: 600 }}>Errors: {preview.errors.length}</span>
              <span style={{ color: 'var(--ink-400)' }}>Total rows: {preview.total}</span>
            </div>
            {preview.errors.length > 0 && (
              <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid var(--ink-700)', borderRadius: 8, padding: 'var(--space-2)' }}>
                <table className="data-table" style={{ width: '100%' }}>
                  <thead><tr><th>Row</th><th>Email</th><th>Problem</th></tr></thead>
                  <tbody>
                    {preview.errors.slice(0, 50).map((e, i) => (
                      <tr key={i}><td>{e.row_number}</td><td>{e.email || '—'}</td><td>{e.reason}</td></tr>
                    ))}
                  </tbody>
                </table>
                {preview.errors.length > 50 && <p style={{ color: 'var(--ink-400)', fontSize: 'var(--text-xs)' }}>…and {preview.errors.length - 50} more</p>}
              </div>
            )}
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
              <button className="btn btn-primary" onClick={handleImport} disabled={loading || preview.valid_rows.length === 0}>
                Import {preview.valid_rows.length} user{preview.valid_rows.length === 1 ? '' : 's'}
              </button>
              {preview.errors.length > 0 && (
                <button className="btn btn-ghost" onClick={downloadErrorReport}>Download error report</button>
              )}
            </div>
          </div>
        )}

        {result && (
          <div>
            <div className="floating-cards-grid" style={{ marginBottom: 'var(--space-3)' }}>
              <div className="floating-card" style={{ padding: 'var(--space-3)' }}>
                <div className="floating-card__title" style={{ color: 'var(--green-500, #2ea043)' }}>{result.successful}</div>
                <div className="floating-card__meta">Successful</div>
              </div>
              <div className="floating-card" style={{ padding: 'var(--space-3)' }}>
                <div className="floating-card__title" style={{ color: 'var(--red-500, #da3633)' }}>{result.failed}</div>
                <div className="floating-card__meta">Failed</div>
              </div>
              <div className="floating-card" style={{ padding: 'var(--space-3)' }}>
                <div className="floating-card__title" style={{ color: 'var(--gold-500, #d29922)' }}>{result.duplicates}</div>
                <div className="floating-card__meta">Duplicates</div>
              </div>
            </div>
            {result.errors.length > 0 && (
              <button className="btn btn-ghost" onClick={downloadErrorReport} style={{ marginBottom: 'var(--space-3)' }}>
                Download error report
              </button>
            )}
            <p style={{ color: 'var(--ink-400)', fontSize: 'var(--text-sm)' }}>
              Imported users start as <strong>Pending</strong>. Generate invitation codes so they can activate their accounts.
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <button className="btn btn-primary" onClick={onClose}>Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'
import './UserList.css'

/**
 * Generate Invite Code + Invite Code Management (spec §6/§10/§23).
 * Scope comes from the backend: dept_head sees own department, admin their
 * school, superadmin everything. The raw code is shown exactly once.
 */

interface Invite {
  id: string
  code_prefix: string
  department_id?: string | null
  department_name?: string | null
  role: string
  expires_at: string
  max_uses: number
  used_count: number
  status: 'active' | 'expired' | 'revoked' | 'exhausted'
  created_at: string
}

interface Department {
  id: string
  name: string
  code: string
}

// Roles that any authorised actor (superadmin/admin/dept_head) may bind to an
// invitation. Superadmin/Admin are excluded here — they are created directly
// via User Management, not through the invitation flow.
// Order matches the role hierarchy (highest assignable first).
const ROLE_OPTIONS = [
  { value: 'dept_head', label: 'Department Head' },
  { value: 'auditor',   label: 'Auditor' },
  { value: 'verifier',  label: 'Verifier' },
  { value: 'checker',   label: 'Checker' },
  { value: 'viewer',    label: 'Viewer' },
]

const STATUS_STYLE: Record<string, string> = {
  active: 'status-active',
  expired: 'status-inactive',
  revoked: 'status-inactive',
  exhausted: 'status-pending',
}

export default function InviteCodes({ onClose }: { onClose: () => void }) {
  const [invites, setInvites] = useState<Invite[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)

  // Generate form
  const [departmentId, setDepartmentId] = useState('')
  const [role, setRole] = useState('checker')
  const [maxUses, setMaxUses] = useState(1)
  const [expiresHours, setExpiresHours] = useState(72)
  const [generatedCode, setGeneratedCode] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [invRes, deptRes] = await Promise.all([
        apiFetch('/api/v1/invitations?page=1&page_size=100'),
        apiFetch('/api/v1/departments?page=1&page_size=200'),
      ])
      if (invRes.ok) {
        const data = await invRes.json()
        setInvites(data.data || [])
      } else if (invRes.status === 403) {
        setError('You do not have permission to manage invitation codes.')
      }
      if (deptRes.ok) {
        const data = await deptRes.json()
        setDepartments(data.data || [])
      }
    } catch {
      setError('Failed to load invitations')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!departmentId) return
    setCreating(true)
    setError(null)
    setGeneratedCode(null)
    try {
      const res = await apiFetch('/api/v1/invitations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          department_id: departmentId,
          role,
          max_uses: maxUses,
          expires_in_hours: expiresHours,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        const message = err?.error?.message || err?.detail?.error?.message || 'Failed to generate code'
        throw new Error(message)
      }
      const data = await res.json()
      setGeneratedCode(data.code)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate code')
    } finally {
      setCreating(false)
    }
  }

  const handleRevoke = async (id: string) => {
    try {
      const res = await apiFetch(`/api/v1/invitations/${id}/revoke`, { method: 'POST' })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.error?.message || 'Failed to revoke')
      }
      setBanner('Invitation revoked')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke')
    }
  }

  const copyCode = () => {
    if (generatedCode) navigator.clipboard?.writeText(generatedCode).catch(() => undefined)
  }

  const departmentOptions = departments.map(d => ({ value: d.id, label: d.name, sublabel: d.code }))

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760, width: '92%', maxHeight: '85vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <h2>Invitation Codes</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && <div className="alert alert-error"><span style={{ fontWeight: 700 }}>!</span><span>{error}</span></div>}
        {banner && <div className="alert alert-success"><span style={{ fontWeight: 700 }}>✓</span><span>{banner}</span></div>}

        {/* Generate */}
        <form onSubmit={handleGenerate} style={{ display: 'grid', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Department *</label>
              <SearchableSelect
                id="department-select"
                name="department"
                value={departmentId}
                onChange={setDepartmentId}
                options={departmentOptions}
                placeholder="Select department…"
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Role *</label>
              <select className="form-input" value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Max uses</label>
              <input
                type="number" min={1} max={100} className="form-input"
                value={maxUses} onChange={(e) => setMaxUses(parseInt(e.target.value || '1', 10))}
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Expires in (hours)</label>
              <input
                type="number" min={1} max={720} className="form-input"
                value={expiresHours} onChange={(e) => setExpiresHours(parseInt(e.target.value || '72', 10))}
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button type="submit" className="btn btn-primary" disabled={creating || !departmentId}>
              {creating ? 'Generating…' : 'Generate invite code'}
            </button>
          </div>
        </form>

        {generatedCode && (
          <div style={{
            padding: 'var(--space-3)', borderRadius: 10, marginBottom: 'var(--space-4)',
            background: 'rgba(46,160,67,0.10)', border: '1px solid rgba(46,160,67,0.4)',
          }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-400)', marginBottom: 4 }}>
              Share this code now — it is shown only once and stored hashed:
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <code style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '0.08em' }}>{generatedCode}</code>
              <button className="btn btn-sm btn-ghost" onClick={copyCode}>Copy</button>
            </div>
          </div>
        )}

        {/* List */}
        {loading ? (
          <div className="loading-state">Loading…</div>
        ) : invites.length === 0 ? (
          <p style={{ color: 'var(--ink-400)' }}>No invitation codes yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr><th>Code</th><th>Department</th><th>Role</th><th>Uses</th><th>Expires</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {invites.map(inv => (
                  <tr key={inv.id}>
                    <td><code>{inv.code_prefix}-••••-••••</code></td>
                    <td>{inv.department_name || '—'}</td>
                    <td><span className="role-badge">{inv.role}</span></td>
                    <td>{inv.used_count}/{inv.max_uses}</td>
                    <td>{new Date(inv.expires_at).toLocaleString()}</td>
                    <td><span className={`status ${STATUS_STYLE[inv.status] || ''}`}>{inv.status}</span></td>
                    <td>
                      {inv.status === 'active' && (
                        <button className="icon-btn icon-btn-danger" title="Revoke" onClick={() => handleRevoke(inv.id)}>⌫</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

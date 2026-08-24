import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'
import './ApprovalChains.css'

/* ── Types ─────────────────────────────────────────────────────────────── */

interface ApprovalLevel {
  level: number
  role_id: string
  auto_escalation_sla_hours?: number
}

interface ApprovalChain {
  chain_version_id: string
  levels: ApprovalLevel[]
  is_active: boolean
  created_at: string
  created_by?: string
}

interface Role {
  id: string
  name: string
}

/* ── Helpers ───────────────────────────────────────────────────────────── */

/** Resolve a role_id to its display name, falling back to raw id. */
function resolveRoleName(
  roleId: string,
  roles: Role[],
  roleLookup: Map<string, string>,
): string {
  if (roleLookup.has(roleId)) return roleLookup.get(roleId)!
  return roleId.slice(0, 8) + '…'
}

/* ── Main component ────────────────────────────────────────────────────── */

export default function ApprovalChains() {
  const [chains, setChains] = useState<ApprovalChain[]>([])
  const [activeChain, setActiveChain] = useState<ApprovalChain | null>(null)
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const [formData, setFormData] = useState({
    levels: [{ level: 1, role_id: '', auto_escalation_sla_hours: 24 }],
  })

  const [submitting, setSubmitting] = useState(false)

  // v2.8 activate confirm dialog state
  const [activateTarget, setActivateTarget] = useState<ApprovalChain | null>(null)

  /* ── Data fetching ──────────────────────────────────────────────────── */

  useEffect(() => {
    fetchChains()
    fetchActiveChain()
    fetchRoles()
  }, [])

  const fetchChains = async () => {
    try {
      setLoading(true)
      const res = await apiFetch('/api/v1/audit-discrepancy/approval-chains')
      if (res.ok) {
        setChains(await res.json())
      } else {
        setChains([])
      }
    } catch {
      setChains([])
    } finally {
      setLoading(false)
    }
  }

  const fetchActiveChain = async () => {
    try {
      const res = await apiFetch('/api/v1/audit-discrepancy/approval-chains/active')
      if (res.ok) {
        setActiveChain(await res.json())
      } else {
        setActiveChain(null)
      }
    } catch {
      setActiveChain(null)
    }
  }

  const fetchRoles = async () => {
    try {
      const res = await apiFetch('/api/v1/roles')
      if (res.ok) {
        const data = await res.json()
        setRoles(data.roles || data || [])
      }
    } catch {
      /* ignore — roles will display as raw UUID fallback */
    }
  }

  /* ── Role lookup map ────────────────────────────────────────────────── */

  const roleLookup = new Map<string, string>()
  for (const r of roles) {
    roleLookup.set(r.id, r.name)
  }

  /* ── Form: dynamic levels ───────────────────────────────────────────── */

  const handleAddLevel = () => {
    const newLevel = formData.levels.length + 1
    setFormData((prev) => ({
      ...prev,
      levels: [
        ...prev.levels,
        { level: newLevel, role_id: '', auto_escalation_sla_hours: 24 },
      ],
    }))
  }

  const handleRemoveLevel = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      levels: prev.levels
        .filter((_, i) => i !== index)
        .map((l, i) => ({ ...l, level: i + 1 })),
    }))
  }

  const handleRoleChange = (index: number, roleId: string) => {
    setFormData((prev) => ({
      ...prev,
      levels: prev.levels.map((l, i) =>
        i === index ? { ...l, role_id: roleId } : l,
      ),
    }))
  }

  const handleSlaChange = (index: number, hours: number) => {
    setFormData((prev) => ({
      ...prev,
      levels: prev.levels.map((l, i) =>
        i === index ? { ...l, auto_escalation_sla_hours: hours } : l,
      ),
    }))
  }

  /* ── Submit new chain ───────────────────────────────────────────────── */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const res = await apiFetch('/api/v1/audit-discrepancy/approval-chains', {
        method: 'POST',
        body: JSON.stringify({ levels: formData.levels }),
      })

      if (!res.ok) {
        const errBody = await res.json().catch(() => null)
        throw new Error(
          errBody?.error?.message || 'Failed to create approval chain',
        )
      }

      await fetchChains()
      await fetchActiveChain()
      setShowForm(false)
      setFormData({
        levels: [{ level: 1, role_id: '', auto_escalation_sla_hours: 24 }],
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  /* ── Activate chain (v2.8 confirm dialog) ───────────────────────────── */

  const handleActivateConfirm = async () => {
    if (!activateTarget) return
    setSubmitting(true)
    setError(null)

    try {
      const res = await apiFetch(
        `/api/v1/audit-discrepancy/approval-chains/${activateTarget.chain_version_id}/activate`,
        { method: 'PATCH' },
      )

      if (!res.ok) {
        throw new Error('Failed to activate approval chain')
      }

      await fetchChains()
      await fetchActiveChain()
      setActivateTarget(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to activate chain')
    } finally {
      setSubmitting(false)
    }
  }

  /* ── Derived data ───────────────────────────────────────────────────── */

  const inactiveChains = chains.filter((c) => !c.is_active)

  const roleOptions = roles.map((r) => ({ value: r.id, label: r.name }))

  /* ── Loading ────────────────────────────────────────────────────────── */

  if (loading) {
    return <div className="loading-state">Loading approval chains…</div>
  }

  /* ── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="approval-chains page-shell">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="page-head ac-page-head">
        <div>
          <div className="eyebrow">Policy Configuration</div>
          <h1>Approval Chains</h1>
        </div>
        <button
          className={`btn ${showForm ? 'btn-ghost' : 'btn-primary'}`}
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? 'Cancel' : 'Create New Chain'}
        </button>
      </div>

      {/* ── Error alert ──────────────────────────────────────────────── */}
      {error && (
        <div className="ac-alert ac-alert-error" style={{ margin: 'var(--space-5) 40px 0' }}>
          <span className="ac-alert__icon">⚠️</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ac-alert__close">
            ×
          </button>
        </div>
      )}

      <div style={{ padding: 'var(--space-5) 40px 0' }}>

        {/* ── Active Chain Card ─────────────────────────────────────── */}
        {activeChain ? (
          <div className="ac-active-card">
            <div className="ac-active-card__head">
              <div>
                <h3 className="ac-active-card__title">Active Approval Chain</h3>
                <div className="ac-active-card__chain-id">
                  {activeChain.chain_version_id}
                </div>
              </div>
              <span className="status status-active">Active</span>
            </div>
            <LevelsTable
              levels={activeChain.levels}
              roles={roles}
              roleLookup={roleLookup}
            />
            <div className="ac-active-card__footer">
              Created: {new Date(activeChain.created_at).toLocaleString()}
            </div>
          </div>
        ) : (
          <div className="ac-empty">
            <div className="ac-empty__icon">⛓️</div>
            <h3>No active approval chain</h3>
            <p>Create a chain and activate it to configure discrepancy approval flow.</p>
          </div>
        )}

        {/* ── Create Chain Form ─────────────────────────────────────── */}
        {showForm && (
          <form onSubmit={handleSubmit} className="ac-form">
            <h3 className="ac-form__title">Create New Approval Chain</h3>

            <div className="ac-form__section-header">
              <span className="ac-form__section-label">Approval Levels</span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleAddLevel}
              >
                Add Level
              </button>
            </div>

            {formData.levels.map((level, index) => (
              <div key={`level-${index}`} className="ac-level-card">
                <div className="ac-level-card__head">
                  <span className="ac-level-card__number">
                    Level {level.level}
                  </span>
                  {formData.levels.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ color: 'var(--rose-600)' }}
                      onClick={() => handleRemoveLevel(index)}
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="ac-level-card__fields">
                  <div className="form-group">
                    <label htmlFor={`role-${index}`}>Role *</label>
                    <SearchableSelect
                      id={`role-${index}`}
                      name={`role_id_${index}`}
                      value={level.role_id}
                      onChange={(val) => handleRoleChange(index, val)}
                      options={roleOptions}
                      placeholder="Select role…"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor={`sla-${index}`}>
                      Auto-escalation SLA (Hours)
                    </label>
                    <input
                      id={`sla-${index}`}
                      type="number"
                      min="1"
                      value={level.auto_escalation_sla_hours}
                      onChange={(e) =>
                        handleSlaChange(
                          index,
                          parseInt(e.target.value) || 1,
                        )
                      }
                      className="form-input"
                    />
                  </div>
                </div>
              </div>
            ))}

            <div className="ac-form__actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
              >
                {submitting ? 'Saving…' : 'Save Chain'}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* ── All Chains (inactive) ─────────────────────────────────── */}
        <div className="ac-section-head">
          <h3>All Chains</h3>
          {inactiveChains.length > 0 && (
            <span style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)' }}>
              {inactiveChains.length} inactive
            </span>
          )}
        </div>

        {inactiveChains.length === 0 ? (
          <div className="ac-empty">
            <div className="ac-empty__icon">📋</div>
            <h3>No other chains</h3>
            <p>Create a new chain to define an alternative approval flow.</p>
          </div>
        ) : (
          <div className="ac-inactive-stack">
            {inactiveChains.map((chain) => (
              <div
                key={chain.chain_version_id}
                className="ac-inactive-card"
              >
                <div className="ac-inactive-card__head">
                  <div className="ac-inactive-card__meta">
                    <span className="ac-inactive-card__chain-id">
                      {chain.chain_version_id}
                    </span>
                    <span className="status status-inactive">Inactive</span>
                  </div>
                  <span className="ac-inactive-card__arrow">→</span>
                </div>

                <LevelsTable
                  levels={chain.levels}
                  roles={roles}
                  roleLookup={roleLookup}
                />

                <div className="ac-inactive-card__footer">
                  <span>
                    Created: {new Date(chain.created_at).toLocaleDateString()}
                  </span>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={submitting}
                    onClick={() => setActivateTarget(chain)}
                  >
                    Activate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Activate Confirm Dialog (v2.8) ──────────────────────────── */}
      {activateTarget && (
        <div
          className="ac-confirm-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setActivateTarget(null)
          }}
        >
          <div className="ac-confirm-dialog">
            <h3 className="ac-confirm-dialog__title">Activate this chain?</h3>
            <div className="ac-confirm-dialog__body">
              <strong>Consequence:</strong>
              This will deactivate the current active chain immediately.
              All future approvals will use this chain's levels.
              In-flight discrepancies retain their bound chain version (BR-21).
            </div>
            <div className="ac-confirm-dialog__actions">
              <button
                className="btn btn-ghost"
                onClick={() => setActivateTarget(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={submitting}
                onClick={handleActivateConfirm}
              >
                {submitting ? 'Activating…' : 'Activate Chain'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Levels table (shared between active + inactive cards) ─────────────── */

function LevelsTable({
  levels,
  roles,
  roleLookup,
}: {
  levels: ApprovalLevel[]
  roles: Role[]
  roleLookup: Map<string, string>
}) {
  return (
    <>
      {/* Desktop / tablet table */}
      <div className="ac-levels-table-wrap">
        <table className="ac-levels-table">
          <thead>
            <tr>
              <th>Level</th>
              <th>Role</th>
              <th>Auto-escalation SLA</th>
            </tr>
          </thead>
          <tbody>
            {levels.map((lvl, i) => (
              <tr key={`lvl-${i}`}>
                <td className="cell-level">{lvl.level}</td>
                <td className="cell-role">
                  {resolveRoleName(lvl.role_id, roles, roleLookup)}
                </td>
                <td className="cell-sla">
                  {lvl.auto_escalation_sla_hours
                    ? `${lvl.auto_escalation_sla_hours}h`
                    : 'N/A'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile stacked rows — shown via CSS at < 600px */}
      <div className="ac-levels-table--mobile">
        {levels.map((lvl, i) => (
          <div key={`lvl-mob-${i}`} className="ac-level-mobile-row">
            <div className="ac-level-mobile-row__header">
              <span className="ac-level-mobile-row__level">
                Level {lvl.level}
              </span>
              <span className="ac-level-mobile-row__sla">
                {lvl.auto_escalation_sla_hours
                  ? `${lvl.auto_escalation_sla_hours}h`
                  : 'N/A'}
              </span>
            </div>
            <div className="ac-level-mobile-row__role">
              {resolveRoleName(lvl.role_id, roles, roleLookup)}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

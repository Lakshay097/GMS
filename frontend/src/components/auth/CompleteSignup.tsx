import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthContext } from '../../contexts/AuthContext'
import { authFetch } from '../../lib/auth'
import SearchableSelect from '../common/SearchableSelect'

/**
 * Complete signup: attach a school to the signed-in user who has none yet.
 * Replaces the Clerk-based flow — the user authenticates via the platform's
 * own session, then picks their school here.
 */

interface SchoolOption {
  value: string
  label: string
  sublabel?: string
}

export default function CompleteSignup() {
  const navigate = useNavigate()
  const { user, roles, loading: authLoading, refresh, logout } = useAuthContext()

  const [schoolCode, setSchoolCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [schoolOptions, setSchoolOptions] = useState<SchoolOption[]>([])
  const [schoolsLoading, setSchoolsLoading] = useState(true)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/auth/sign-in')
      return
    }
    if (!authLoading && user) {
      const hasSchool = !!user.school_id
      const isSuperAdmin = roles.some((r) => r.toLowerCase() === 'superadmin')
      if (hasSchool || isSuperAdmin) {
        navigate('/dashboard')
      }
    }
  }, [user, navigate, authLoading, roles])

  useEffect(() => {
    const fetchSchools = async () => {
      try {
        const res = await fetch('/auth/schools')
        if (res.ok) {
          const data: { code: string; name: string }[] = await res.json()
          setSchoolOptions(
            data
              .filter((s) => s.code)
              .map((s) => ({ value: s.code, label: s.code, sublabel: s.name })),
          )
        }
      } catch {
        /* API not reachable — show empty list */
      } finally {
        setSchoolsLoading(false)
      }
    }
    fetchSchools()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return
    setLoading(true)
    setError(null)
    try {
      const res = await authFetch('/auth/complete-signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ school_code: schoolCode }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.error?.message || 'Account setup failed')
      }
      await refresh()
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Account setup failed')
      setLoading(false)
    }
  }

  if (!user) {
    return <div className="loading-state">Loading…</div>
  }

  return (
    <div className="auth">
      <div className="auth-form">
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-4)' }}>
          <h2 style={{ marginBottom: 'var(--space-2)' }}>Welcome, {user.full_name?.split(' ')[0]}</h2>
          <p style={{ color: 'var(--ink-500)', fontSize: 'var(--text-body)', lineHeight: 1.6 }}>
            One last step — pick your school to get started.
          </p>
        </div>

        {error && (
          <div className="error-message" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontWeight: 700 }}>!</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={user.email} disabled title="Email is set by your account" />
          </div>

          <div className="form-group">
            <label htmlFor="school_code">School Code *</label>
            <SearchableSelect
              id="school_code"
              name="school_code"
              value={schoolCode}
              onChange={(val) => setSchoolCode(val)}
              options={schoolOptions}
              placeholder={schoolsLoading ? 'Loading schools…' : 'Select your school…'}
              required
              disabled={schoolsLoading}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !schoolCode}
            style={{
              width: '100%',
              background: 'var(--gold-600)',
              borderColor: 'var(--gold-600)',
              color: '#fff',
              minHeight: '44px',
            }}
          >
            {loading ? 'Creating Account…' : 'Complete Setup'}
          </button>
        </form>

        <div className="auth-switch">
          <span className="auth-switch-text">Wrong account?</span>
          <button className="auth-switch-link" onClick={() => logout().then(() => navigate('/auth/sign-in'))}>
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, useUser } from '@clerk/clerk-react'
import { setAuthCookie } from '../../lib/auth'
import { autoLinkAccount } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'

/* ── Known school codes — fixed finite list ──────────────────────────── */

const SCHOOL_CODES = [
  { value: 'GUR-JAI', label: 'GUR-JAI', sublabel: 'Jaipur Campus' },
  { value: 'GUR-VAR', label: 'GUR-VAR', sublabel: 'Varanasi Campus' },
  { value: 'GUR-MOT', label: 'GUR-MOT', sublabel: 'Motihari Campus' },
  { value: 'GUR-GWA', label: 'GUR-GWA', sublabel: 'Gwalior Campus' },
  { value: 'GUR-RAN', label: 'GUR-RAN', sublabel: 'Ranchi Campus' },
  { value: 'GUR-IND', label: 'GUR-IND', sublabel: 'Indore Campus' },
  { value: 'GUR-MUZ', label: 'GUR-MUZ', sublabel: 'Muzaffarpur Campus' },
  { value: 'GUR-GUR', label: 'GUR-GUR', sublabel: 'Gurugram Campus' },
  { value: 'GUR-FAR', label: 'GUR-FAR', sublabel: 'Faridabad Campus' },
  { value: 'GUR-LUC', label: 'GUR-LUC', sublabel: 'Lucknow Campus' },
  { value: 'GUR-SUR', label: 'GUR-SUR', sublabel: 'Suratgarh Campus' },
  { value: 'GUR-BHO', label: 'GUR-BHO', sublabel: 'Bhopal Campus' },
]

/* ── Component ─────────────────────────────────────────────────────────── */

export default function CompleteSignup() {
  const navigate = useNavigate()
  const { isSignedIn, getToken } = useAuth()
  const { user } = useUser()

  const [schoolCode, setSchoolCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  /* ── Redirect if already provisioned ───────────────────────────────── */

  useEffect(() => {
    if (!isSignedIn || !user) {
      navigate('/auth/sign-in')
      return
    }
    checkProvisioning()
  }, [isSignedIn, user, navigate])

  const checkProvisioning = async () => {
    if (!user) return
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch('/auth/verify', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })
      const data = await res.json()
      if (data.valid && data.user_id && data.school_id) {
        navigate('/dashboard')
      }
    } catch {
      /* not provisioned — stay on form */
    }
  }

  /* ── Submit ─────────────────────────────────────────────────────────── */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return

    setLoading(true)
    setError(null)

    try {
      // Get a fresh token from Clerk's React hook (always up-to-date)
      const freshToken = await getToken()
      const linked = await autoLinkAccount(schoolCode, freshToken || undefined)
      if (!linked) {
        throw new Error('Failed to create or link account')
      }

      if (freshToken) {
        await setAuthCookie(freshToken)
      }

      setSuccess(true)
      setTimeout(() => {
        navigate('/dashboard')
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Account creation failed')
    } finally {
      setLoading(false)
    }
  }

  /* ── Guard ──────────────────────────────────────────────────────────── */

  if (!user) {
    return <div className="loading-state">Loading…</div>
  }

  const email = user.emailAddresses[0]?.emailAddress || ''

  /* ── Success state ──────────────────────────────────────────────────── */

  if (success) {
    return (
      <div className="auth">
        <div className="auth-success">
          <h2>Setup complete — redirecting…</h2>
          <p>Your account has been created with VIEWER access.</p>
          <p>Redirecting to dashboard…</p>
        </div>
      </div>
    )
  }

  /* ── Form ───────────────────────────────────────────────────────────── */

  return (
    <div className="auth">
      <div className="auth-form">

        {/* ── Header ─────────────────────────────────────────────────── */}
        <h2>Complete Your Account Setup</h2>
        <p>
          Welcome, {user.fullName}! Please select your school code to complete
          your account setup.
        </p>

        {/* ── Error banner ───────────────────────────────────────────── */}
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>

          {/* ── Email (disabled — external system controlled) ─────────── */}
          <div className="form-group">
            <label htmlFor="email">
              Email
              <span
                style={{
                  fontSize: 'var(--text-micro)',
                  color: 'var(--ink-300)',
                  fontWeight: 500,
                  cursor: 'help',
                }}
                title="Email is set by your account provider"
              >
                🔒
              </span>
            </label>
            <input
              id="email"
              type="email"
              value={email}
              disabled
              title="Email is set by your account provider"
            />
          </div>

          {/* ── School Code (searchable select — known fixed list) ───── */}
          <div className="form-group">
            <label htmlFor="school_code">School Code *</label>
            <SearchableSelect
              id="school_code"
              name="school_code"
              value={schoolCode}
              onChange={(val) => setSchoolCode(val)}
              options={SCHOOL_CODES}
              placeholder="Select your school…"
              required
            />
          </div>

          {/* ── Submit ────────────────────────────────────────────────── */}
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

        {/* ── Dashboard link ─────────────────────────────────────────── */}
        <div className="auth-switch">
          <span className="auth-switch-text">Already set up?</span>
          <a href="/dashboard" className="auth-switch-link">
            Go to Dashboard →
          </a>
        </div>
      </div>
    </div>
  )
}

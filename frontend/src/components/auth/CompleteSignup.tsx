import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, useUser } from '@clerk/clerk-react'
import { setAuthCookie } from '../../lib/auth'
import { autoLinkAccount } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'

/* ── Component ─────────────────────────────────────────────────────────── */

export default function CompleteSignup() {
  const navigate = useNavigate()
  const { isSignedIn, getToken } = useAuth()
  const { user } = useUser()

  const [schoolCode, setSchoolCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [schoolOptions, setSchoolOptions] = useState<{ value: string; label: string; sublabel?: string }[]>([])
  const [schoolsLoading, setSchoolsLoading] = useState(true)
  const provisioningChecked = useRef(false)

  /* ── Redirect if already provisioned ───────────────────────────────── */

  useEffect(() => {
    if (!isSignedIn || !user) {
      navigate('/auth/sign-in')
      return
    }
    if (!provisioningChecked.current) {
      provisioningChecked.current = true
      checkProvisioning()
    }
  }, [isSignedIn, user, navigate])

  /* ── Fetch schools dynamically from API ─────────────────────────────── */

  useEffect(() => {
    const fetchSchools = async () => {
      try {
        // Use plain fetch (not apiFetch) to avoid the auto-link redirect loop
        // that fires when the user isn't yet provisioned.
        const res = await fetch('/api/v1/schools?page_size=200', {
          credentials: 'include',
        })
        if (res.ok) {
          const data = await res.json()
          const schools = (data.data || []).map((s: any) => ({
            value: s.code || s.school_code || '',
            label: s.code || s.school_code || 'Unknown',
            sublabel: s.name || '',
          })).filter((s: any) => s.value)
          setSchoolOptions(schools)
        }
      } catch {
        /* API not reachable — show empty list */
      } finally {
        setSchoolsLoading(false)
      }
    }
    fetchSchools()
  }, [])

  const checkProvisioning = async () => {
    if (!user) return
    try {
      // Check Clerk metadata for SuperAdmin role (fallback when DB role is stale)
      const clerkRoles: string[] = (user.publicMetadata?.roles as string[]) || []
      const isClerkSuperAdmin = clerkRoles.some(
        (r: string) => r.toLowerCase() === 'superadmin',
      )

      // If Clerk metadata shows SuperAdmin, bypass DB check entirely —
      // the user is already authorized regardless of Neon DB state.
      if (isClerkSuperAdmin) {
        navigate('/dashboard')
        return
      }

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
      const hasUser = data.valid === true && data.user_id != null
      const hasSchool = data.school_id != null
      const isSuperAdmin = (data.roles || []).some(
        (r: string) => r.toLowerCase() === 'superadmin',
      )
      // SuperAdmins don't need a school — they manage all schools.
      // Other roles without a school need to complete signup.
      if (hasUser && (hasSchool || isSuperAdmin)) {
        navigate('/dashboard')
      }
    } catch {
      // If /auth/verify fails, check Clerk metadata as last resort
      const clerkRoles: string[] = (user.publicMetadata?.roles as string[]) || []
      const isClerkSuperAdmin = clerkRoles.some(
        (r: string) => r.toLowerCase() === 'superadmin',
      )
      if (isClerkSuperAdmin) {
        navigate('/dashboard')
      }
      /* otherwise not provisioned — stay on form */
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
              options={schoolOptions}
              placeholder={schoolsLoading ? 'Loading schools…' : 'Select your school…'}
              required
              disabled={schoolsLoading}
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

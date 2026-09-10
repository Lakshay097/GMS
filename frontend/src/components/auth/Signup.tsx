import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

/**
 * Sign up with an invitation code (user-management spec §8).
 * Role and department come from the code — the backend ignores any
 * client-supplied role. Peek shows what the code grants before submitting.
 */

interface PeekResult {
  valid: boolean
  department_name?: string | null
  role?: string | null
  expires_at?: string | null
  remaining_uses?: number | null
  error?: string | null
}

export default function Signup() {
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [peek, setPeek] = useState<PeekResult | null>(null)
  const [peeking, setPeeking] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handlePeek = async () => {
    if (!inviteCode.trim()) return
    setPeeking(true)
    setPeek(null)
    try {
      const res = await fetch('/auth/invitations/peek', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invitation_code: inviteCode.trim() }),
      })
      setPeek(await res.json())
    } catch {
      setPeek({ valid: false, error: 'Could not validate the code right now' })
    } finally {
      setPeeking(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim().toLowerCase(),
          invitation_code: inviteCode.trim(),
          password,
        }),
        credentials: 'include',
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        const message = err?.detail?.error?.message || err?.error?.message || 'Signup failed'
        throw new Error(message)
      }
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
      setLoading(false)
    }
  }

  return (
    <div className="auth">
      <Link to="/" className="auth-back-link">← Back</Link>
      <h1>Create your account</h1>
      <p className="auth-subtitle" style={{ color: 'var(--ink-400)', marginBottom: 'var(--space-4)' }}>
        Sign up with the invitation code from your administrator
      </p>

      {error && (
        <div className="error-message" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
          <span style={{ fontWeight: 700 }}>!</span>
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="full_name">Full name</label>
          <input
            id="full_name" type="text" required autoComplete="name"
            value={fullName} onChange={(e) => setFullName(e.target.value)}
            className="form-input" placeholder="Your name" autoFocus
          />
        </div>

        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email" type="email" required autoComplete="email"
            value={email} onChange={(e) => setEmail(e.target.value)}
            className="form-input" placeholder="you@school.edu"
          />
        </div>

        <div className="form-group">
          <label htmlFor="invitation_code">Invitation code</label>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <input
              id="invitation_code" type="text" required
              value={inviteCode}
              onChange={(e) => { setInviteCode(e.target.value.toUpperCase()); setPeek(null) }}
              className="form-input" placeholder="OPS-X7K9-P4Q2"
              style={{ textTransform: 'uppercase', letterSpacing: '0.06em', flex: 1 }}
            />
            <button type="button" className="btn btn-ghost" onClick={handlePeek} disabled={peeking || !inviteCode.trim()}>
              {peeking ? '…' : 'Check'}
            </button>
          </div>
          {peek && (
            <div
              className="form-hint"
              style={{
                marginTop: 'var(--space-2)', padding: '8px 12px', borderRadius: 8,
                background: peek.valid ? 'rgba(46,160,67,0.12)' : 'rgba(218,54,51,0.12)',
                color: peek.valid ? 'var(--green-500, #2ea043)' : 'var(--red-500, #da3633)',
                fontWeight: 500,
              }}
            >
              {peek.valid
                ? `✓ Role: ${peek.role} · Department: ${peek.department_name} · ${peek.remaining_uses} use(s) left`
                : `✗ ${peek.error || 'Invitation code is invalid or expired.'}`}
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password" type="password" required autoComplete="new-password" minLength={10}
            value={password} onChange={(e) => setPassword(e.target.value)}
            className="form-input" placeholder="At least 10 characters, letters and numbers"
          />
        </div>

        <div className="form-group">
          <label htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password" type="password" required autoComplete="new-password" minLength={10}
            value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
            className="form-input"
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-full"
          disabled={loading || !peek?.valid}
          style={{ minHeight: 44, marginTop: 'var(--space-2)' }}
          title={!peek?.valid ? 'Check your invitation code first' : undefined}
        >
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      <div className="auth-switch">
        <span className="auth-switch-text">Already have an account?</span>
        <a className="auth-switch-link" href="/auth/sign-in">Sign in</a>
      </div>
    </div>
  )
}

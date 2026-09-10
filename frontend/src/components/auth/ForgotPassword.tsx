import { useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword, resetPassword } from '../../lib/auth'

/**
 * Password recovery: request a single-use reset token, then set a new
 * password. The request step always "succeeds" to prevent account
 * enumeration; token delivery happens via the notification/email service.
 */
export default function ForgotPassword() {
  const [step, setStep] = useState<'request' | 'reset'>('request')
  const [email, setEmail] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await forgotPassword(email)
      setStep('reset')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await resetPassword(token, newPassword)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth">
      <Link to="/auth/sign-in" className="auth-back-link">← Back to sign in</Link>
      <h1>{done ? 'Password reset' : 'Forgot password'}</h1>

      {done ? (
        <>
          <p style={{ color: 'var(--ink-400)', marginBottom: 'var(--space-4)' }}>
            Your password has been reset. You can now sign in with your new password.
          </p>
          <Link to="/auth/sign-in" className="btn btn-primary btn-full" style={{ textAlign: 'center' }}>
            Sign In
          </Link>
        </>
      ) : step === 'request' ? (
        <>
          <p style={{ color: 'var(--ink-400)', marginBottom: 'var(--space-4)' }}>
            Enter your account email. If it is registered, a single-use reset
            token will be sent to you.
          </p>
          <form onSubmit={handleRequest}>
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="form-input"
                placeholder="you@school.edu"
                autoFocus
              />
            </div>
            <button type="submit" className="btn btn-primary btn-full" disabled={loading} style={{ minHeight: 44 }}>
              {loading ? 'Sending…' : 'Send reset token'}
            </button>
          </form>
        </>
      ) : (
        <>
          {error && (
            <div className="error-message" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
              <span style={{ fontWeight: 700 }}>!</span>
              <span>{error}</span>
            </div>
          )}
          <form onSubmit={handleReset}>
            <div className="form-group">
              <label htmlFor="token">Reset token</label>
              <input
                id="token"
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="form-input"
                placeholder="Paste the token you received"
                autoFocus
              />
            </div>
            <div className="form-group">
              <label htmlFor="new-password">New password</label>
              <input
                id="new-password"
                type="password"
                required
                minLength={10}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="form-input"
                placeholder="At least 10 characters, letters and numbers"
              />
            </div>
            <div className="form-group">
              <label htmlFor="confirm-password">Confirm new password</label>
              <input
                id="confirm-password"
                type="password"
                required
                minLength={10}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="form-input"
              />
            </div>
            <button type="submit" className="btn btn-primary btn-full" disabled={loading} style={{ minHeight: 44 }}>
              {loading ? 'Resetting…' : 'Reset password'}
            </button>
          </form>
        </>
      )}
    </div>
  )
}

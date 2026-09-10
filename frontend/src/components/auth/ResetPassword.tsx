import { useState, useEffect } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { resetPassword } from '../../lib/auth'

/**
 * Deep-link password reset page.
 *
 * Reached via a URL like:
 *   /auth/reset-password?token=<raw_token>
 *
 * The backend delivers this URL in the password-reset email / in-app
 * notification (POST /auth/forgot-password → Resend / notification row).
 *
 * If the user arrives without a token query param they are redirected to the
 * manual forgot-password flow instead.
 *
 * Security notes:
 *   - The token is consumed server-side (single-use, hashed at rest).
 *   - We never log or display the raw token after submission.
 *   - Password policy is enforced by the backend; we mirror the minimums in
 *     the client for instant feedback only.
 */
export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const tokenFromUrl = searchParams.get('token') ?? ''

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  // If there is no token in the URL, send the user to forgot-password so they
  // can request a fresh one — never show an empty token field here.
  useEffect(() => {
    if (!tokenFromUrl) {
      navigate('/auth/forgot-password', { replace: true })
    }
  }, [tokenFromUrl, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (newPassword.length < 10) {
      setError('Password must be at least 10 characters')
      return
    }
    if (!/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) {
      setError('Password must contain at least one letter and one number')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await resetPassword(tokenFromUrl, newPassword)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed. The link may have expired.')
    } finally {
      setLoading(false)
    }
  }

  // While we wait for the redirect effect — render nothing to avoid flash.
  if (!tokenFromUrl) return null

  return (
    <div className="auth">
      <Link to="/auth/sign-in" className="auth-back-link">← Back to sign in</Link>
      <h1>{done ? 'Password reset' : 'Set a new password'}</h1>

      {done ? (
        <>
          <p style={{ color: 'var(--ink-400)', marginBottom: 'var(--space-4)' }}>
            Your password has been reset successfully. You can now sign in with your new password.
          </p>
          <Link
            to="/auth/sign-in"
            className="btn btn-primary btn-full"
            style={{ textAlign: 'center', display: 'block' }}
          >
            Sign In
          </Link>
        </>
      ) : (
        <>
          <p style={{ color: 'var(--ink-400)', marginBottom: 'var(--space-4)' }}>
            Choose a new password for your account. This link is single-use and
            expires after 30 minutes.
          </p>

          {error && (
            <div
              className="error-message"
              role="alert"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                marginBottom: 'var(--space-3)',
              }}
            >
              <span style={{ fontWeight: 700 }}>!</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="new-password">New password</label>
              <input
                id="new-password"
                type="password"
                required
                minLength={10}
                autoComplete="new-password"
                autoFocus
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value)
                  if (error) setError(null)
                }}
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
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                  if (error) setError(null)
                }}
                className="form-input"
                placeholder="Re-enter your new password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={loading}
              style={{ minHeight: 44, marginTop: 'var(--space-2)' }}
            >
              {loading ? 'Setting password…' : 'Set new password'}
            </button>
          </form>

          <div className="auth-switch" style={{ marginTop: 'var(--space-3)' }}>
            <span className="auth-switch-text">Link expired?</span>{' '}
            <Link to="/auth/forgot-password" className="auth-switch-link">
              Request a new one
            </Link>
          </div>
        </>
      )}
    </div>
  )
}

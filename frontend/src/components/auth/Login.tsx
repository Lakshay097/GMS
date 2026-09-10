import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuthContext } from '../../contexts/AuthContext'

/**
 * Sign-in page — email + password against the self-managed FastAPI auth.
 * Preserves the original auth-screen look (centered card, gold accents).
 */
export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuthContext()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const from = (location.state as { from?: string } | null)?.from || '/dashboard'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
      setLoading(false)
    }
  }

  return (
    <div className="auth">
      <Link to="/" className="auth-back-link">← Back</Link>
      <h1>Sign in</h1>
      <p className="auth-subtitle" style={{ color: 'var(--ink-400)', marginBottom: 'var(--space-4)' }}>
        Use your SchoolOps account
      </p>

      {error && (
        <div className="error-message" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
          <span style={{ fontWeight: 700 }}>!</span>
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="form-input"
            placeholder="you@school.edu"
            autoFocus
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="form-input"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-full"
          disabled={loading}
          style={{ minHeight: 44, marginTop: 'var(--space-2)' }}
        >
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
      </form>

      <div className="auth-switch">
        <a className="auth-switch-link" href="/auth/forgot-password">Forgot password?</a>
      </div>
      <div className="auth-switch">
        <span className="auth-switch-text">Have an invitation code?</span>
        <a className="auth-switch-link" href="/auth/sign-up">Create an account</a>
      </div>
    </div>
  )
}

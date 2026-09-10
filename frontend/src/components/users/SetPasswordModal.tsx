import { useEffect, useRef, useState } from 'react'
import { adminSetPassword } from '../../lib/auth'

interface SetPasswordModalProps {
  userId: string
  userName: string
  onClose: (issued: boolean) => void
}

type Mode = 'choose' | 'password' | 'token' | 'result'

/**
 * Admin action: issue a user's credential without an email provider.
 *
 * Two paths (backend: POST /api/v1/users/{id}/set-password):
 *  - Set a password directly and share it over a trusted channel.
 *  - Get a one-time reset token shown HERE once; the user pastes it on the
 *    Forgot-password page and chooses their own password.
 *
 * Either path revokes the user's existing sessions (force-reset semantics).
 */
export default function SetPasswordModal({ userId, userName, onClose }: SetPasswordModalProps) {
  const [mode, setMode] = useState<Mode>('choose')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [resultMessage, setResultMessage] = useState('')
  const [resultToken, setResultToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const passwordRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [submitting, onClose])

  const policyError = (pw: string): string | null => {
    if (pw.length < 10) return 'Password must be at least 10 characters'
    if (!/[A-Za-z]/.test(pw)) return 'Password must contain at least one letter'
    if (!/\d/.test(pw)) return 'Password must contain at least one number'
    return null
  }

  const submit = async (withPassword: boolean) => {
    if (withPassword) {
      const policyIssue = policyError(password)
      if (policyIssue) {
        setError(policyIssue)
        passwordRef.current?.focus()
        return
      }
    }
    setSubmitting(true)
    setError(null)
    try {
      const result = await adminSetPassword(userId, withPassword ? password : undefined)
      if (result.mode === 'reset_token' && result.reset_token) {
        setMode('result')
        setResultToken(result.reset_token)
        setResultMessage('One-time reset token generated.')
      } else {
        setMode('result')
        setResultToken(null)
        setResultMessage('Password set. Share it with the user over a trusted channel.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set password')
    } finally {
      setSubmitting(false)
    }
  }

  const copyToken = async () => {
    if (!resultToken) return
    await navigator.clipboard.writeText(resultToken).catch(() => undefined)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="modal-overlay" onClick={() => !submitting && onClose(false)}>
      <div
        className="modal-content set-password-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`Set password for ${userName}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3>Set password — {userName}</h3>
          <button onClick={() => onClose(false)} className="modal-close" aria-label="Close" disabled={submitting}>×</button>
        </div>

        <div className="modal-body">
          {mode === 'choose' && (
            <div className="set-password__options">
              <button className="set-password__option" onClick={() => setMode('password')}>
                <span className="set-password__option-title">Set a password now</span>
                <span className="set-password__option-desc">You choose it and share it with the user yourself.</span>
              </button>
              <button className="set-password__option" onClick={() => setMode('token')}>
                <span className="set-password__option-title">Give a one-time reset token</span>
                <span className="set-password__option-desc">The user pastes the token on the Forgot-password page and picks their own password.</span>
              </button>
            </div>
          )}

          {mode === 'password' && (
            <form
              className="set-password__form"
              onSubmit={(e) => { e.preventDefault(); submit(true) }}
            >
              <div className="form-group">
                <label htmlFor="set-password-input">New password</label>
                <input
                  id="set-password-input"
                  ref={passwordRef}
                  type="text"
                  className="form-input"
                  autoComplete="off"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
                <span className="form-hint">Minimum 10 characters with letters and numbers.</span>
              </div>
              {error && <p className="form-error">{error}</p>}
              <p className="set-password__warning">This revokes the user's current sessions.</p>
              <div className="modal-footer set-password__footer">
                <button type="button" className="btn btn-ghost" onClick={() => { setMode('choose'); setError(null) }} disabled={submitting}>
                  Back
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Setting…' : 'Set password'}
                </button>
              </div>
            </form>
          )}

          {mode === 'token' && (
            <div className="set-password__form">
              <p>Generate a single-use token, valid for 30 minutes, that this user can use once to choose a password.</p>
              {error && <p className="form-error">{error}</p>}
              <p className="set-password__warning">This revokes the user's current sessions.</p>
              <div className="modal-footer set-password__footer">
                <button className="btn btn-ghost" onClick={() => { setMode('choose'); setError(null) }} disabled={submitting}>
                  Back
                </button>
                <button className="btn btn-primary" onClick={() => submit(false)} disabled={submitting}>
                  {submitting ? 'Generating…' : 'Generate token'}
                </button>
              </div>
            </div>
          )}

          {mode === 'result' && (
            <div className="set-password__result">
              <p>{resultMessage}</p>
              {resultToken && (
                <>
                  <p className="set-password__once">Shown once — copy it now. It will not be displayed again.</p>
                  <div className="set-password__token-row">
                    <code className="set-password__token">{resultToken}</code>
                    <button className="btn btn-sm btn-primary" onClick={copyToken}>
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <p className="form-hint">
                    The user goes to Forgot password, pastes this token, and sets their own password.
                  </p>
                </>
              )}
              <div className="modal-footer set-password__footer">
                <button className="btn btn-primary" onClick={() => onClose(true)}>Done</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

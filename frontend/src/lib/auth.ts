/**
 * Auth client — centralized authentication abstraction.
 *
 * The ONLY module that knows HOW authentication works (HTTP-only session
 * cookies against the FastAPI backend). Components consume `useAuth()`
 * from contexts/AuthContext and never touch cookies or endpoints directly.
 */

const BASE = ''

/** Capability flags derived from the backend permission matrix (R-48).
 *
 *  The backend (`shared/permissions.py → capabilities_for_roles`) derives
 *  every flag from the same matrix rows that enforce API requests, so the
 *  frontend must render exactly what the backend enforces — no local role
 *  literals.
 */
export interface Capabilities {
  observation: {
    /** R-22: Checker/DeptHead only */
    create: boolean
    /** Auditor only */
    verify: boolean
  }
  /** Module visibility flags — one per nav-gated page, each mapped to the
   *  matrix row(s) the corresponding API route enforces. */
  modules: {
    dashboard: boolean
    kpiEntry: boolean
    kpiVerification: boolean
    schools: boolean
    departments: boolean
    users: boolean
    observations: boolean
    tasks: boolean
    reports: boolean
    audit: boolean
    kra: boolean
    settings: boolean
    approvalChains: boolean
    escalationRules: boolean
  }
  /** Coarse action flags (unions of matrix rows) consumed by RoleGuard. */
  canView: boolean
  canCreate: boolean
  canEdit: boolean
  canDelete: boolean
  canExport: boolean
  /** Broadest scope of the user's grants: 'all' | 'school' | 'department' */
  scope: 'all' | 'school' | 'department'
}

export interface SessionUser {
  id: string
  email: string
  full_name: string
  roles: string[]
  school_id: string | null
  department_id: string | null
  mfa_enabled: boolean
  capabilities?: Capabilities
}

interface SessionPayload {
  user: SessionUser | null
  session: { expires_at?: string } | null
  valid: boolean
}

async function parse(res: Response): Promise<SessionPayload> {
  try {
    return await res.json()
  } catch {
    return { user: null, session: null, valid: false }
  }
}

/**
 * Authenticated fetch. The browser attaches the HttpOnly session cookie
 * automatically via `credentials: 'include'` — no token handling in app code.
 */
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...options,
    credentials: 'include',
  })
}

/** POST /auth/login → sets the HttpOnly session cookie. */
export async function login(email: string, password: string): Promise<SessionPayload> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    credentials: 'include',
  })

  if (!res.ok) {
    const err = await res.json().catch(() => null)
    const message =
      err?.error?.message ||
      (res.status === 423 ? 'Account temporarily locked. Try again later.' : 'Invalid email or password')
    throw new Error(message)
  }
  return parse(res)
}

/** POST /auth/logout → invalidates the server-side session row. */
export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  }).catch(() => undefined)
}

/** GET /auth/get-session → current user from the DB-backed session. */
export async function getSession(): Promise<SessionPayload> {
  try {
    const res = await fetch(`${BASE}/auth/get-session`, {
      credentials: 'include',
    })
    return await parse(res)
  } catch {
    return { user: null, session: null, valid: false }
  }
}

/** POST /auth/change-password */
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.error?.message || 'Failed to change password')
  }
}

/** POST /auth/forgot-password — always succeeds (no enumeration). */
export async function forgotPassword(email: string): Promise<void> {
  await fetch(`${BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    credentials: 'include',
  }).catch(() => undefined)
}

/** POST /auth/reset-password — consumes a single-use token. */
export async function resetPassword(token: string, newPassword: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.error?.message || 'Failed to reset password')
  }
}

/** Admin password issuance — response of POST /api/v1/users/{id}/set-password. */
export interface SetPasswordResult {
  success: boolean
  mode: 'password' | 'reset_token'
  message: string
  reset_token: string | null
}

/**
 * POST /api/v1/users/{id}/set-password — admin sets a user's password or
 * issues a one-time reset token. With `password` the credential is stored
 * directly; without it the backend returns a single-use reset token to hand
 * to the user. Both revoke the user's existing sessions.
 */
export async function adminSetPassword(userId: string, password?: string): Promise<SetPasswordResult> {
  const res = await authFetch(`/api/v1/users/${userId}/set-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(password ? { password } : {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.error?.message || 'Failed to set password')
  }
  return res.json()
}

/**
 * Placeholder auth hook surface kept for backwards compatibility with the
 * old Clerk-based `authClient.useAuth()` calls. Components should migrate to
 * `useAuth()` from contexts/AuthContext (which is backed by this module).
 */
export const authClient = {
  login,
  logout,
  getSession,
  authFetch,
  changePassword,
  forgotPassword,
  resetPassword,
  adminSetPassword,
}

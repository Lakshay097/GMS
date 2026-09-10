import { debug, warn } from './debug'

/**
 * API helpers — authentication is a Secure, HttpOnly session cookie managed
 * by the backend. No tokens are read or stored in JavaScript (XSS-safe).
 */

/** Legacy no-op kept for import compatibility; cookies are handled by the browser. */
export async function getAccessToken(): Promise<string | null> {
  return null
}

/**
 * React hook for making authenticated API calls.
 * The session cookie travels automatically via `credentials: 'include'`.
 */
export function useAuthenticatedApi() {
  return async (url: string, options: RequestInit = {}): Promise<Response> => {
    return fetch(url, {
      ...options,
      credentials: 'include',
    })
  }
}

/**
 * Generate a signed URL for evidence access (A7 security fix)
 * Required because evidence is stored with type='authenticated' in Cloudinary
 */
export async function getEvidenceSignedUrl(observationId: string, publicId: string): Promise<string | null> {
  try {
    const response = await fetch(`/api/v1/evidence/signed-url/${observationId}/${publicId}`, {
      credentials: 'include',
    })

    if (response.ok) {
      const data = await response.json()
      return data.signed_url
    } else {
      console.error('Failed to get signed URL for evidence')
      return null
    }
  } catch (error) {
    console.error('Error getting evidence signed URL:', error)
    return null
  }
}

/**
 * Check if the current user is provisioned in the platform
 * Returns true if user exists with any role, false otherwise
 */
export async function isUserProvisioned(): Promise<boolean> {
  try {
    const response = await fetch('/auth/get-session', {
      credentials: 'include',
    })

    if (response.ok) {
      const data = await response.json()
      return data.valid && data.user && data.user.roles && data.user.roles.length > 0
    }
    return false
  } catch (error) {
    console.error('Error checking user provisioning:', error)
    return false
  }
}

/**
 * Fetch with automatic 403 provisioning retry.
 * Auth is the HttpOnly session cookie — nothing to inject.
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  // Auto-detect JSON body and set Content-Type if not already set
  const hasJsonBody = options.body && typeof options.body === 'string'
  const existingHeaders = options.headers as Record<string, string> | undefined
  const contentType = existingHeaders?.['Content-Type'] || existingHeaders?.['content-type']

  const headers: Record<string, string> = {
    ...options.headers as Record<string, string>,
    ...(hasJsonBody && !contentType ? { 'Content-Type': 'application/json' } : {}),
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Essential for the HttpOnly session cookie
  })

  // If the session expired mid-use, sign out cleanly by letting the guards
  // handle it — components already treat 401 as "session invalid".
  if (response.status === 401) {
    debug('Session invalid or expired (401)')
  }

  // If user not provisioned, redirect to complete signup (same as before)
  if (response.status === 403) {
    let error: { error?: { code?: string } } | null = null
    try {
      const ct = response.headers.get('content-type') || ''
      if (ct.includes('application/json')) {
        error = await response.clone().json()
      }
    } catch {
      // Response body is not JSON — skip
    }
    if (error?.error?.code === 'USER_NOT_PROVISIONED') {
      warn('User not provisioned — redirecting to complete signup')
      window.location.href = '/auth/complete-signup'
      // Return a never-resolving promise substitute: the redirect takes over
      return new Promise<Response>(() => {})
    }
  }

  return response
}

/** Alias for fetchWithAuth for backwards compatibility */
export const apiFetch = fetchWithAuth

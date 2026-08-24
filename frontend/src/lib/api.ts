import { getJwtToken, authClient } from './auth'

/**
 * Resolve the current Clerk session JWT for API Bearer auth.
 * 
 * Uses Clerk's getToken() method which provides JWT tokens for API authentication.
 * No longer stores token in localStorage for security (XSS protection).
 * Relies on httpOnly cookies managed by Clerk.
 */
export async function getAccessToken(): Promise<string | null> {
  try {
    // Try to get JWT token from Clerk
    const jwtToken = await getJwtToken()
    if (jwtToken) {
      console.log('Using JWT token for API authentication')
      return jwtToken
    }
    
    console.log('JWT token not available, will rely on cookies')
  } catch (err) {
    console.error('Failed to read Clerk session', err)
  }

  return null
}

/**
 * React hook for making authenticated API calls
 * This should be used within React components
 */
export function useAuthenticatedApi() {
  const { getToken } = authClient.useAuth();
  
  return async (url: string, options: RequestInit = {}): Promise<Response> => {
    const token = await getToken();
    
    console.log(`useAuthenticatedApi: token ${token ? 'available' : 'not available'}`);
    
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      credentials: 'include',
    });
  };
}

/**
 * Generate a signed URL for evidence access (A7 security fix)
 * Required because evidence is stored with type='authenticated' in Cloudinary
 */
export async function getEvidenceSignedUrl(observationId: string, publicId: string): Promise<string | null> {
  try {
    const token = await getAccessToken()
    const response = await fetch(`/api/v1/evidence/signed-url/${observationId}/${publicId}`, {
      method: 'GET',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
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
 * Auto-link account after Clerk signup with school code
 * This creates the platform user automatically if they don't exist
 */
export async function autoLinkAccount(schoolCode: string): Promise<boolean> {
  try {
    const response = await fetch('/auth/link-account', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ school_code: schoolCode }),
      credentials: 'include',
    })

    if (response.ok) {
      const data = await response.json()
      console.log('Account linked/created:', data)
      return true
    } else {
      const error = await response.json()
      console.error('Failed to link account:', error)
      return false
    }
  } catch (error) {
    console.error('Error linking account:', error)
    return false
  }
}

/**
 * Get the current user's email from Clerk session.
 * Reads directly from the global Clerk instance (no React hook needed).
 */
async function getSessionEmail(): Promise<string | null> {
  try {
    // Access Clerk's global instance to get user email
    // @ts-ignore - Clerk is available globally after initialization
    if (typeof window !== 'undefined' && window.Clerk) {
      // @ts-ignore
      const user = window.Clerk.user;
      if (user && user.emailAddresses && user.emailAddresses.length > 0) {
        return user.emailAddresses[0].emailAddress;
      }
    }
    console.warn('Could not get email from Clerk session');
    return null;
  } catch {
    return null
  }
}

/**
 * Check if the current user is provisioned in the platform
 * Returns true if user exists with any role, false otherwise
 */
export async function isUserProvisioned(): Promise<boolean> {
  try {
    const token = await getAccessToken()
    console.log('isUserProvisioned: token =', token ? 'exists' : 'null')
    if (!token) return false

    const response = await fetch('/auth/get-session', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      credentials: 'include',
    })

    console.log('isUserProvisioned: response status =', response.status)
    
    if (response.ok) {
      const data = await response.json()
      console.log('isUserProvisioned: response data =', data)
      // User is provisioned if they have a valid session with roles
      return data.valid && data.user && data.user.roles && data.user.roles.length > 0
    } else {
      console.log('isUserProvisioned: response not ok')
      return false
    }
  } catch (error) {
    console.error('Error checking user provisioning:', error)
    return false
  }
}

/**
 * Auto-link the Neon Auth sub to the platform user record.
 * Called when a 403 USER_NOT_PROVISIONED is returned by require_tenant_context.
 * The backend will match by email and write the real neon_auth_user_id.
 */
async function tryLinkAccount(token: string): Promise<boolean> {
  try {
    const email = await getSessionEmail()
    const body = email ? JSON.stringify({ email }) : undefined
    const response = await fetch('/auth/link-account', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        ...(body && { 'Content-Type': 'application/json' }),
      },
      body,
      credentials: 'include',
    })

    if (response.ok) {
      const data = await response.json()
      // Check if account was fully linked or needs school code (A5 security fix)
      if (data.linked === true) {
        console.log('Account linked via auto-link:', data)
        return true
      } else if (data.requires_school_code === true) {
        console.log('Account requires school code, redirecting to complete signup')
        // Redirect to CompleteSignup so the user can select their school
        window.location.href = '/auth/complete-signup'
        return false
      } else {
        console.log('Account link pending:', data)
        return false
      }
    } else {
      console.error('Auto-link failed:', response.status)
      return false
    }
  } catch (error) {
    console.error('Error in auto-link:', error)
    return false
  }
}

/**
 * Fetch with automatic token handling and 403 auto-link retry.
 * Uses both httpOnly cookie and Bearer token for maximum compatibility and security.
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAccessToken()
  
  console.log(`fetchWithAuth: token ${token ? 'available' : 'not available'}`)
  
  // Use both cookie auth and Bearer token for maximum compatibility
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      // Include Bearer token if available (for API-to-API calls)
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    credentials: 'include', // Essential for httpOnly cookies
  })

  console.log(`fetchWithAuth: response status ${response.status}`)

  // If user not provisioned, try auto-link and retry
  if (response.status === 401 || response.status === 403) {
    const error = await response.json()
    if (error?.error?.code === 'USER_NOT_PROVISIONED') {
      console.log('User not provisioned, attempting auto-link...')
      if (token) {
        const linked = await tryLinkAccount(token)
        if (linked) {
          // Retry the original request
          return fetch(url, {
            ...options,
            headers: {
              ...options.headers,
              ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            credentials: 'include',
          })
        }
      }
    }
  }

  return response
}

/**
 * Alias for fetchWithAuth for backwards compatibility
 */
export const apiFetch = fetchWithAuth

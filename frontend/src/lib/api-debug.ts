import { getJwtToken } from './auth'

/**
 * Debug version of getAccessToken with detailed logging
 */
export async function getAccessTokenDebug(): Promise<string | null> {
  console.log('[DEBUG] Starting getAccessTokenDebug...')
  
  try {
    console.log('[DEBUG] Calling getJwtToken()...')
    const token = await getJwtToken()
    console.log('[DEBUG] getJwtToken result:', token ? 'EXISTS' : 'NULL')
    
    if (token) {
      console.log('[DEBUG] Using JWT token for authentication')
      return token
    }
  } catch (err) {
    console.error('[DEBUG] Failed to get JWT token:', err)
  }

  console.log('[DEBUG] No token available')
  return null
}

/**
 * Debug version of apiFetch with detailed logging
 */
export async function apiFetchDebug(input: string, init: RequestInit = {}): Promise<Response> {
  console.log('[DEBUG] Starting apiFetchDebug for:', input)
  
  const token = await getAccessTokenDebug()
  console.log('[DEBUG] Token for request:', token ? 'EXISTS' : 'NULL')
  
  const headers = new Headers(init.headers || {})

  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
    console.log('[DEBUG] Authorization header set')
  } else {
    console.log('[DEBUG] No token available, Authorization header NOT set')
  }

  console.log('[DEBUG] Request headers:', Object.fromEntries(headers.entries()))
  console.log('[DEBUG] Fetching with credentials:', init.credentials ?? 'include')

  const response = await fetch(input, {
    ...init,
    headers,
    credentials: init.credentials ?? 'include',
  })

  console.log('[DEBUG] Response status:', response.status)
  console.log('[DEBUG] Response ok:', response.ok)

  return response
}
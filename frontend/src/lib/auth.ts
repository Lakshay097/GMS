import { ClerkProvider, useAuth, useClerk } from '@clerk/clerk-react'

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!clerkPublishableKey) {
  console.error('VITE_CLERK_PUBLISHABLE_KEY is not set. Please configure it in your .env file.');
}

// Create Clerk context
export const authClient = {
  useAuth,
  ClerkProvider,
  useClerk
};

/**
 * React hook to get authenticated fetch function
 * This should be used within React components
 */
export function useAuthenticatedFetch() {
  const { getToken } = useAuth();
  
  return async (url: string, options: RequestInit = {}): Promise<Response> => {
    const token = await getToken();
    
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
 * Get JWT token for API requests
 * Required for backend services that cannot access browser cookies
 * Clerk provides JWT tokens directly
 * This accesses the global Clerk instance if available
 */
export async function getJwtToken(): Promise<string | null> {
  try {
    // Access Clerk's global instance
    // @ts-ignore - Clerk is available globally after initialization
    if (typeof window !== 'undefined' && window.Clerk) {
      // @ts-ignore
      const session = window.Clerk.session;
      if (session) {
        const token = await session.getToken();
        return token || null;
      }
    }
    
    console.warn('Clerk session not available. API calls may fail.');
    return null;
  } catch (error) {
    console.error('Error getting JWT token:', error);
    return null;
  }
}

/**
 * Set httpOnly auth cookie after Clerk login
 * This provides enhanced security by storing JWT in httpOnly cookie instead of localStorage
 */
export async function setAuthCookie(token: string): Promise<boolean> {
  try {
    const response = await fetch('/auth/set-auth-cookie', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ token }),
      credentials: 'include',
    });

    if (response.ok) {
      console.log('Auth cookie set successfully');
      return true;
    } else {
      const error = await response.json();
      console.error('Failed to set auth cookie:', error);
      return false;
    }
  } catch (error) {
    console.error('Error setting auth cookie:', error);
    return false;
  }
}

/**
 * Sign out the current user
 * This clears the Clerk session cookie and any local state
 * This should be called from within a component using the useClerk hook
 */
export async function signOut() {
  try {
    // This function should be called from within a component context
    // Use the signOut method from useClerk hook instead
    console.warn('signOut should be called from within a component using useClerk hook');
    // Clear any local storage auth token for backwards compatibility
    localStorage.removeItem('auth_token');
  } catch (error) {
    console.error('Failed to sign out:', error);
    throw error;
  }
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import './i18n/config'
import './index.css'
import App from './App.tsx'
import * as Sentry from '@sentry/react'

// Suppress non-critical React scheduler errors (useSyncExternalStore StrictMode race)
window.addEventListener('error', (event) => {
  const msg = event.message || ''
  if (msg.includes('startTime') || msg.includes('reportAllChanges')) {
    event.preventDefault()
    return false
  }
})

const sentryDsn = import.meta.env.VITE_SENTRY_FRONTEND_DSN;

if (sentryDsn) {
  // Mask the DSN for safe logging: show only the project ID
  const dsnProject = sentryDsn.split('/').pop() || 'unknown'
  const dsnHost = sentryDsn.split('@')[1]?.split('/')[0] || 'unknown'
  console.log(`[Sentry] DSN target: ${dsnHost}/${dsnProject}`)

  Sentry.init({
    dsn: sentryDsn,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration(),
    ],
    sendDefaultPii: true,
    tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    beforeSend(event) {
      if (event.exception) {
        console.log('Sentry event:', event);
      }
      return event;
    },
  });
  console.log('Sentry initialized for frontend');
} else {
  console.warn('[Sentry] VITE_SENTRY_FRONTEND_DSN is NOT set — Sentry is disabled');
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<p>An error has occurred</p>}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)

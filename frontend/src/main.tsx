import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ClerkProvider } from '@clerk/clerk-react'
import { AuthProvider } from './contexts/AuthContext'
import './i18n/config'
import './index.css'
import App from './App.tsx'
import * as Sentry from '@sentry/react'

const sentryDsn = import.meta.env.VITE_SENTRY_FRONTEND_DSN;

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration(),
    ],
    // Set tracesSampleRate to 1.0 to capture 100%
    // of transactions for tracing.
    tracesSampleRate: 1.0,
    // Capture Replay for 10% of all sessions,
    // plus for 100% of sessions with an error
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    beforeSend(event) {
      // Check if the event is an exception
      if (event.exception) {
        // You can modify the event here
        console.log('Sentry event:', event);
      }
      return event;
    },
  });
  console.log('Sentry initialized for frontend');
} else {
  console.log('Sentry frontend DSN not configured - skipping Sentry initialization');
}

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!clerkPublishableKey) {
  console.error('VITE_CLERK_PUBLISHABLE_KEY is not set. Please configure it in your .env file.');
  throw new Error('VITE_CLERK_PUBLISHABLE_KEY is not set');
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* @ts-expect-error Sentry ErrorBoundary type mismatch with React 19 */}
    <Sentry.ErrorBoundary fallback={<p>An error has occurred</p>}>
      <ClerkProvider
        publishableKey={clerkPublishableKey}
      >
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ClerkProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)

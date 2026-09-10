import { Link, useRouteError, isRouteErrorResponse } from 'react-router-dom'

/* ─── 404 Not Found ────────────────────────────────────────────────── */

export function NotFoundPage() {
  return (
    <div className="error-page">
      <div className="error-page__card">
        <div className="error-page__icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
        <h1 className="error-page__title">404</h1>
        <p className="error-page__subtitle">Page not found</p>
        <p className="error-page__message">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="error-page__actions">
          <Link to="/dashboard" className="error-page__btn error-page__btn--primary">
            Go to Dashboard
          </Link>
          <Link to="/" className="error-page__btn error-page__btn--secondary">
            Go Home
          </Link>
        </div>
      </div>
    </div>
  )
}

/* ─── 403 Forbidden ────────────────────────────────────────────────── */

export function ForbiddenPage() {
  return (
    <div className="error-page">
      <div className="error-page__card">
        <div className="error-page__icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>
        <h1 className="error-page__title">403</h1>
        <p className="error-page__subtitle">Access denied</p>
        <p className="error-page__message">
          You don't have permission to access this page.
          Contact your administrator if you believe this is a mistake.
        </p>
        <div className="error-page__actions">
          <Link to="/dashboard" className="error-page__btn error-page__btn--primary">
            Go to Dashboard
          </Link>
          <button onClick={() => window.history.back()} className="error-page__btn error-page__btn--secondary">
            Go Back
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── 500 Server Error ─────────────────────────────────────────────── */

export function ServerErrorPage() {
  return (
    <div className="error-page">
      <div className="error-page__card">
        <div className="error-page__icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>
        <h1 className="error-page__title">500</h1>
        <p className="error-page__subtitle">Server error</p>
        <p className="error-page__message">
          Something went wrong on our end. Please try again later.
        </p>
        <div className="error-page__actions">
          <button onClick={() => window.location.reload()} className="error-page__btn error-page__btn--primary">
            Retry
          </button>
          <Link to="/dashboard" className="error-page__btn error-page__btn--secondary">
            Go to Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}

/* ─── Generic Route Error (catches thrown responses) ────────────────── */

export function RouteErrorPage() {
  const error = useRouteError()

  if (isRouteErrorResponse(error)) {
    const status = error.status
    if (status === 404) return <NotFoundPage />
    if (status === 403) return <ForbiddenPage />
    if (status >= 500) return <ServerErrorPage />

    return (
      <div className="error-page">
        <div className="error-page__card">
          <div className="error-page__icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>
          <h1 className="error-page__title">{status}</h1>
          <p className="error-page__message">
            {error.statusText || 'An error occurred'}
          </p>
          <div className="error-page__actions">
            <Link to="/dashboard" className="error-page__btn error-page__btn--primary">
              Go to Dashboard
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return <ServerErrorPage />
}

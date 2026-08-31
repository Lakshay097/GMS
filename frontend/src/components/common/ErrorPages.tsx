import { Link, useRouteError, isRouteErrorResponse } from 'react-router-dom'

/* ─── 404 Not Found ────────────────────────────────────────────────── */

export function NotFoundPage() {
  return (
    <div className="error-page">
      <div className="error-page__card">
        <div className="error-page__icon">🔍</div>
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
        <div className="error-page__icon">🔒</div>
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
        <div className="error-page__icon">⚠️</div>
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
          <div className="error-page__icon">⚠️</div>
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

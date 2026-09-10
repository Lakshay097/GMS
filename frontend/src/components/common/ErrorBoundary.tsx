import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo })
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      const isAuthError = this.state.error?.message?.includes('session') ||
        this.state.error?.message?.includes('401')

      if (isAuthError) {
        return (
          <div className="error-page">
            <div className="error-page__card">
              <div className="error-page__icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>
              <h1 className="error-page__title">Authentication Error</h1>
              <p className="error-page__message">
                Your session may have expired.
                Please sign in again.
              </p>
              <div className="error-page__actions">
                <Link to="/" className="error-page__btn error-page__btn--primary">
                  Go Home
                </Link>
                <button onClick={this.handleReset} className="error-page__btn error-page__btn--secondary">
                  Try Again
                </button>
              </div>
            </div>
          </div>
        )
      }

      return (
        <div className="error-page">
          <div className="error-page__card">
            <div className="error-page__icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></div>
            <h1 className="error-page__title">Something went wrong</h1>
            <p className="error-page__message">
              An unexpected error occurred. Our team has been notified.
            </p>
            {this.state.error && (
              <details className="error-page__details">
                <summary>Error details</summary>
                <pre>{this.state.error.message}</pre>
                {this.state.errorInfo && (
                  <pre className="error-page__stack">
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </details>
            )}
            <div className="error-page__actions">
              <button onClick={this.handleReset} className="error-page__btn error-page__btn--primary">
                Try Again
              </button>
              <Link to="/dashboard" className="error-page__btn error-page__btn--secondary">
                Go to Dashboard
              </Link>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

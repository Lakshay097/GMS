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

      const isAuthError = this.state.error?.message?.includes('Clerk') ||
        this.state.error?.message?.includes('publishableKey')

      if (isAuthError) {
        return (
          <div className="error-page">
            <div className="error-page__card">
              <div className="error-page__icon">🔐</div>
              <h1 className="error-page__title">Authentication Error</h1>
              <p className="error-page__message">
                There's a problem with the authentication configuration.
                Please check that Clerk is properly set up.
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
            <div className="error-page__icon">💥</div>
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

import { Routes, Route, Link, useParams, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import React, { useState, useEffect } from 'react'
import { KpiProvider } from './contexts/KpiContext'
import { useAuthContext } from './contexts/AuthContext'
import { SchoolProvider, useSchoolContext } from './contexts/SchoolContext'

import SchoolList from './components/schools/SchoolList'
import SchoolForm from './components/schools/SchoolForm'
import Login from './components/auth/Login'
import Signup from './components/auth/Signup'
import ForgotPassword from './components/auth/ForgotPassword'
import ResetPassword from './components/auth/ResetPassword'
import CompleteSignup from './components/auth/CompleteSignup'
import Chrome from './components/chrome/Chrome'

import DepartmentList from './components/departments/DepartmentList'
import DepartmentForm from './components/departments/DepartmentForm'
import UserList from './components/users/UserList'
import UserForm from './components/users/UserForm'
import KraList from './components/kra-kpi/KraList'
import KraForm from './components/kra-kpi/KraForm'
import KpiForm from './components/kra-kpi/KpiForm'
import DailyKpiInput from './components/kra-kpi/DailyKpiInput'
import CheckerKpiView from './components/kra-kpi/CheckerKpiView'
// Task Management
import TaskList from './components/tasks/TaskList'
import TaskForm from './components/tasks/TaskForm'
import TaskDetail from './components/tasks/TaskDetail'
import EscalationRules from './components/tasks/EscalationRules'
// Dashboards & Reports
import Dashboard from './components/dashboards/Dashboard'
import ReportCatalogue from './components/reports/ReportCatalogue'
import ReportRunner from './components/reports/ReportRunner'
// Search
import GlobalSearch from './components/search/GlobalSearch'
import CommandPalette from './components/search/CommandPalette'
// Audit Discrepancy
import DiscrepancyList from './components/audit/DiscrepancyList'
import DiscrepancyDetail from './components/audit/DiscrepancyDetail'
import DiscrepancyNew from './components/audit/DiscrepancyNew'
import ApprovalChains from './components/audit/ApprovalChains'
// Settings
import SettingsMasterData from './components/settings/SettingsMasterData'
// Observations
import ObservationList from './components/observations/ObservationList'
// Expiration Reminders
import ExpirationRecords from './components/expiration/ExpirationRecords'
import ExpirationRecordDetail from './components/expiration/ExpirationRecordDetail'
import './App.css'
import './components/module-components.css'
import './components/common/error-pages.css'
import ErrorBoundary from './components/common/ErrorBoundary'
import { NotFoundPage } from './components/common/ErrorPages'

/* ─── SVG Icon Components ─────────────────────────── */

const ChevronRightIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

/* ─── Placeholder Pages ──────────────────────────── */

function AdministrationPage() {
  return (
    <div className="page-shell" style={{ padding: '2rem' }}>
      <div className="header">
        <h1>Administration</h1>
      </div>
      <div className="floating-cards-grid">
        <Link to="/departments" className="floating-card" style={{ textDecoration: 'none' }}>
          <div className="floating-card__header">
            <div className="floating-card__main">
              <div className="floating-card__title-section">
                <div className="floating-card__title">Departments</div>
                <div className="floating-card__meta">
                  <span className="dept-tag">Manage departments</span>
                </div>
              </div>
            </div>
            <span className="floating-card__indicators"><ChevronRightIcon /></span>
          </div>
        </Link>
        <Link to="/users" className="floating-card" style={{ textDecoration: 'none' }}>
          <div className="floating-card__header">
            <div className="floating-card__main">
              <div className="floating-card__title-section">
                <div className="floating-card__title">Users</div>
                <div className="floating-card__meta">
                  <span className="dept-tag">Manage users &amp; roles</span>
                </div>
              </div>
            </div>
            <span className="floating-card__indicators"><ChevronRightIcon /></span>
          </div>
        </Link>
      </div>
    </div>
  )
}


function Home() {
  const { t } = useTranslation()
  const { isAuthenticated, loading } = useAuthContext()

  return (
    <div className="home">
      <div className="home-background" aria-hidden="true" />
      
      <div className="home-card">
        <div className="home-wordmark">
          <img src="/assets/logo.png" alt="SchoolOps" style={{ maxWidth: 520, width: '100%', height: 'auto', objectFit: 'contain' }} />
        </div>
        <p className="home-subtitle">{t('home.subtitle')}</p>
        <div className="home-features">
          <div className="home-feature"><span className="home-feature__icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M3 9h18"/></svg></span><span>KPI Tracking</span></div>
          <div className="home-feature"><span className="home-feature__icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></span><span>Observations</span></div>
          <div className="home-feature"><span className="home-feature__icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg></span><span>Audit & Tasks</span></div>
        </div>
        
        <div className="home-actions">
          {!loading && !isAuthenticated && (
            <Link to="/auth/sign-in" style={{ display: 'contents' }}>
              <button className="btn btn-primary btn-full">
                {t('home.signIn')}
              </button>
            </Link>
          )}
        </div>
      </div>
      
      <div className="home-footer">
        <span className="home-footer-text">SchoolOps v1.0.0</span>
      </div>
    </div>
  )
}

function Auth() {
  const { '*': pathname } = useParams()
  const { isAuthenticated, loading } = useAuthContext()

  if (loading) {
    return <div className="loading-state">Loading…</div>
  }

  if (pathname === 'complete-signup') {
    return <CompleteSignup />
  }

  if (pathname === 'forgot-password') {
    return <ForgotPassword />
  }

  if (pathname === 'reset-password') {
    return <ResetPassword />
  }

  if (pathname === 'sign-up') {
    return <Signup />
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <Login />
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user: dbUser, schoolId, roles, loading: authLoading, error: authError } = useAuthContext()

  if (authLoading) return <div className="loading-state">Loading…</div>
  if (!dbUser) return <Navigate to="/auth/sign-in" replace />

  const isSuperAdmin = roles.some((r: string) => r.toLowerCase() === 'superadmin')

  // If session fetch failed (network error), let the user through —
  // fetchWithAuth surfaces errors per request (matches original behaviour).
  if (authError) {
    return <>{children}</>
  }

  // SuperAdmin/Admin don't need a school — they manage all schools.
  const isAdmin = isSuperAdmin || roles.some((r: string) => r.toLowerCase() === 'admin')
  if (!schoolId && !isAdmin) {
    return <Navigate to="/auth/complete-signup" replace />
  }

  return <>{children}</>
}

function Account() {
  const { user, roles: dbRoles, schoolId, departmentId, logout } = useAuthContext()
  const primaryRole = dbRoles[0] || 'Viewer'
  // Resolve school/department names from context
  let schoolName = ''
  let departmentName = ''
  try {
    const { activeSchool } = useSchoolContext()
    schoolName = activeSchool?.name || ''
  } catch {
    // Account may render outside SchoolProvider
  }

  return (
    <div className="account-page">
      <div className="account-page__header">
        <div className="account-page__identity">            <div className="account-page__avatar">
              {(user?.full_name || 'U').charAt(0).toUpperCase()}
            </div>
            <div className="account-page__identity-text">
              <div className="account-page__name-row">
                <span className="account-page__name">{user?.full_name || 'Account'}</span>
                <span className="account-page__role-badge">{primaryRole}</span>
              </div>
              <span className="account-page__email">{user?.email}</span>
            </div>
        </div>
        <div className="account-page__user-button">
          <button className="btn btn-ghost" onClick={() => logout().then(() => { window.location.href = '/' })}>
            Sign Out
          </button>
        </div>
      </div>
      
      <div className="account-page__body">
        <div className="account-card">
          <div className="account-info">
            <div className="account-info-row">
              <span className="account-info-label">Full Name</span>
              <span className="account-info-value">{user?.full_name || 'Not set'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Email</span>
              <span className="account-info-value">{user?.email || 'Not set'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Role(s)</span>
              <span className="account-info-value">{dbRoles.join(', ') || 'Not assigned'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">School</span>
              <span className="account-info-value">{schoolName || (schoolId ? 'School assigned' : 'Not assigned')}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Department</span>
              <span className="account-info-value">{departmentName || (departmentId ? 'Department assigned' : 'Not assigned')}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/** The topbar/chrome is hidden on the landing and auth pages. */
function isAuthOrHomePath() {
  const p = window.location.pathname
  return p === '/' || p.startsWith('/auth')
}

function App() {
  const { user, roles: dbRoles } = useAuthContext()
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)

  // Open command palette from keyboard shortcut
  useEffect(() => {
    const handler = () => setCmdPaletteOpen(true)
    window.addEventListener('open-command-palette', handler)
    return () => window.removeEventListener('open-command-palette', handler)
  }, [])

  const getDefaultRoute = () => {
    if (!user) return '/dashboard'
    const isAdmin = dbRoles.some(role => 
      role.toLowerCase() === 'admin' || role.toLowerCase() === 'superadmin'
    )
    return isAdmin ? '/dashboard' : '/kpi-entry'
  }

  return (
    <div className="app">
      <div className="bg-texture"></div>

      {/* ─── Sticky top bar + nav + notifications (hidden on auth pages) ──── */}
      {!isAuthOrHomePath() && <Chrome onOpenCommandPalette={() => setCmdPaletteOpen(true)} />}
<main className="main">
        <ErrorBoundary>
        <SchoolProvider>
        <KpiProvider>
          <Routes>
            <Route path="/" element={user ? <Navigate to={getDefaultRoute()} replace /> : <Home />} />
            {/* Single splat so Auth's useParams('*') sees the sub-path
                (explicit sibling routes shadow the param and break dispatch) */}
            <Route path="/auth/*" element={<Auth />} />
            <Route path="/account/*" element={<RequireAuth><Account /></RequireAuth>} />
            {/* Schools */}
            <Route path="/schools" element={<RequireAuth><SchoolList /></RequireAuth>} />
            <Route path="/schools/new" element={<RequireAuth><SchoolForm /></RequireAuth>} />
            <Route path="/schools/:id/edit" element={<RequireAuth><SchoolForm /></RequireAuth>} />
            {/* Departments */}
            <Route path="/departments" element={<RequireAuth><DepartmentList /></RequireAuth>} />
            <Route path="/departments/new" element={<RequireAuth><DepartmentForm /></RequireAuth>} />
            <Route path="/departments/:id/edit" element={<RequireAuth><DepartmentForm /></RequireAuth>} />
            {/* Users */}
            <Route path="/users" element={<RequireAuth><UserList /></RequireAuth>} />
            <Route path="/users/new" element={<RequireAuth><UserForm /></RequireAuth>} />
            <Route path="/users/:id/edit" element={<RequireAuth><UserForm /></RequireAuth>} />
            {/* KRA/KPI */}
            <Route path="/kra" element={<RequireAuth><KraList /></RequireAuth>} />
            <Route path="/kra/new" element={<RequireAuth><KraForm /></RequireAuth>} />
            <Route path="/kra/:id/edit" element={<RequireAuth><KraForm /></RequireAuth>} />
            <Route path="/kra/:kraId/kpi/new" element={<RequireAuth><KpiForm /></RequireAuth>} />
            <Route path="/kpi/:id/edit" element={<RequireAuth><KpiForm /></RequireAuth>} />
            <Route path="/kpi-entry" element={<RequireAuth><DailyKpiInput /></RequireAuth>} />
            <Route path="/kpi-verification" element={<RequireAuth><CheckerKpiView /></RequireAuth>} />
            {/* Task Management */}
            <Route path="/tasks" element={<RequireAuth><TaskList /></RequireAuth>} />
            <Route path="/tasks/new" element={<RequireAuth><TaskForm /></RequireAuth>} />
            <Route path="/tasks/:id" element={<RequireAuth><TaskDetail /></RequireAuth>} />
            <Route path="/tasks/:id/edit" element={<RequireAuth><TaskForm /></RequireAuth>} />
            <Route path="/escalation-rules" element={<RequireAuth><EscalationRules /></RequireAuth>} />
            {/* Dashboards & Reports */}
            <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
            <Route path="/reports" element={<RequireAuth><ReportCatalogue /></RequireAuth>} />
            <Route path="/reports/:reportType" element={<RequireAuth><ReportRunner /></RequireAuth>} />
            {/* Search */}
            <Route path="/search" element={<RequireAuth><GlobalSearch /></RequireAuth>} />
            {/* Audit Discrepancy */}
            <Route path="/discrepancies" element={<RequireAuth><DiscrepancyList /></RequireAuth>} />
            <Route path="/discrepancies/new" element={<RequireAuth><DiscrepancyNew /></RequireAuth>} />
            <Route path="/discrepancies/:id" element={<RequireAuth><DiscrepancyDetail /></RequireAuth>} />
            <Route path="/approval-chains" element={<RequireAuth><ApprovalChains /></RequireAuth>} />
            {/* Settings */}
            <Route path="/settings" element={<RequireAuth><SettingsMasterData /></RequireAuth>} />
            {/* Observations — read/manage view; creation lives in KPI Entry */}
            <Route path="/observations" element={<RequireAuth><ObservationList /></RequireAuth>} />
            {/* Expiration Reminders — full list behind the dashboard widget */}
            <Route path="/expiration-records" element={<RequireAuth><ExpirationRecords /></RequireAuth>} />
            <Route path="/expiration-records/:id" element={<RequireAuth><ExpirationRecordDetail /></RequireAuth>} />
            {/* Administration & App Settings */}
            <Route path="/admin" element={<RequireAuth><AdministrationPage /></RequireAuth>} />
            {/* Catch-all 404 */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </KpiProvider>
        </SchoolProvider>
        </ErrorBoundary>
      </main>

      {/* Command Palette (Cmd+K / Ctrl+K) */}
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
      />
    </div>
  )
}

export default App

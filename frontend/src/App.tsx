import { Routes, Route, Link, useParams, NavLink, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { SignedIn, SignedOut, UserButton, SignInButton, SignUpButton, useUser, useClerk } from '@clerk/clerk-react'
import { authClient } from './lib/auth'
import React, { useState, useEffect, useRef } from 'react'
import { KpiProvider } from './contexts/KpiContext'
import { useAuthContext } from './contexts/AuthContext'
import { SchoolProvider, useSchoolContext } from './contexts/SchoolContext'

import SchoolList from './components/schools/SchoolList'
import SchoolForm from './components/schools/SchoolForm'
import CompleteSignup from './components/auth/CompleteSignup'

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
import ApprovalChains from './components/audit/ApprovalChains'
// Settings
import SettingsMasterData from './components/settings/SettingsMasterData'
// Observations
import ObservationList from './components/observations/ObservationList'
import ObservationForm from './components/observations/ObservationForm'
import './App.css'
import './components/module-components.css'

/* ─── SVG Icon Components ─────────────────────────── */

const LogoIcon = () => (
  <img src="/assets/logo.png" alt="SchoolOps" style={{ height: 48, width: 'auto', objectFit: 'contain' }} />
)

const SearchIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/>
    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
)

const HelpIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
    <line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
)

const BurgerIcon = ({ open }: { open: boolean }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {open ? (
      <>
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </>
    ) : (
      <>
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </>
    )}
  </svg>
)

const ChevronRightIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

const ChevronDownIcon = ({ open }: { open: boolean }) => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
)

const LogOutIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
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

function AppSettingsPage() {
  return (
    <div className="page-shell" style={{ padding: '2rem' }}>
      <div className="header">
        <h1>App Settings</h1>
      </div>
      <div className="config-form">
        <p style={{ color: 'var(--ink-300)' }}>Application settings will appear here.</p>
      </div>
    </div>
  )
}

function Home() {
  const { t } = useTranslation()

  return (
    <div className="home">
      <div className="home-background" aria-hidden="true" />
      
      <div className="home-card">
        <div className="home-wordmark">
          <img src="/assets/logo.png" alt="SchoolOps" style={{ maxWidth: 520, width: '100%', height: 'auto', objectFit: 'contain' }} />
        </div>
        <p className="home-subtitle">{t('home.subtitle')}</p>
        
        <div className="home-actions">
          <SignedOut>
            <SignInButton mode="modal">
              <button className="btn btn-primary btn-full">
                {t('home.signIn')}
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="btn btn-secondary btn-full">
                Sign Up
              </button>
            </SignUpButton>
          </SignedOut>
        </div>
      </div>
      
      <div className="home-footer">
        <span className="home-footer-text">SchoolOps v1.0.0</span>
      </div>
    </div>
  )
}

function Auth() {
  const { t } = useTranslation()
  const { '*': pathname } = useParams()
  const { isSignedIn } = authClient.useAuth()

  if (pathname === 'complete-signup') {
    return (
      <div className="auth">
        <CompleteSignup />
      </div>
    )
  }

  if (isSignedIn) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="auth">
      <Link to="/" className="auth-back-link">
        ← {t('common.back')}
      </Link>
      <h1>{t('auth.title')}</h1>
      <SignInButton mode="modal">
        <button className="btn btn-primary btn-full">{t('auth.signIn')}</button>
      </SignInButton>
      <div className="auth-switch">
        <span className="auth-switch-text">Don't have an account?</span>
        <SignUpButton mode="modal">
          <button className="auth-switch-link">Sign Up</button>
        </SignUpButton>
      </div>
    </div>
  )
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isSignedIn, isLoaded, getToken } = authClient.useAuth()
  const [provisioned, setProvisioned] = useState<boolean | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      setChecking(false)
      return
    }

    const checkProvisioning = async () => {
      try {
        const token = await getToken()
        const res = await fetch('/auth/get-session', {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (res.ok) {
          const data = await res.json()
          // User is provisioned if valid AND either has a school or is an admin.
          // SuperAdmin/Admin don't need a school — they manage all schools.
          // Viewer/Checker/Auditor without a school need to complete signup.
          const hasUser = data.valid === true && data.user != null
          const hasSchool = !!data.user?.school_id
          const isSuperAdmin = (data.user?.roles || []).some(
            (r: string) => r.toLowerCase() === 'superadmin',
          )
          // SuperAdmin/Admin don't need a school — they manage all schools.
          // Viewer/Checker/Auditor without a school need to complete signup.
          setProvisioned(hasUser && (hasSchool || isSuperAdmin))
        } else if (res.status === 403) {
          // Only redirect to complete-signup on explicit 403 (USER_NOT_PROVISIONED)
          const data = await res.json().catch(() => ({}))
          if (data?.error?.code === 'USER_NOT_PROVISIONED') {
            setProvisioned(false)
          } else {
            // Other 403 errors (e.g., insufficient permissions) — let the page load
            setProvisioned(true)
          }
        } else {
          // 401 or other errors — token issue, not provisioning. Let page load.
          setProvisioned(true)
        }
      } catch {
        // Network error — let page load, fetchWithAuth will handle
        setProvisioned(true)
      } finally {
        setChecking(false)
      }
    }
    checkProvisioning()
  }, [isLoaded, isSignedIn, getToken])

  if (!isLoaded || checking) return <div className="loading-state">Loading…</div>
  if (!isSignedIn) return <Navigate to="/auth/sign-in" replace />
  if (provisioned === false) return <Navigate to="/auth/complete-signup" replace />
  return <>{children}</>
}

function Account() {
  const { user: clerkUser } = useUser()
  const { roles: dbRoles, schoolId, departmentId } = useAuthContext()
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
              {clerkUser?.fullName?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="account-page__identity-text">
              <div className="account-page__name-row">
                <span className="account-page__name">{clerkUser?.fullName || 'Account'}</span>
                <span className="account-page__role-badge">{primaryRole}</span>
              </div>
              <span className="account-page__email">{clerkUser?.emailAddresses[0]?.emailAddress}</span>
            </div>
        </div>
        <div className="account-page__user-button">
          <UserButton />
        </div>
      </div>
      
      <div className="account-page__body">
        <div className="account-card">
          <div className="account-info">
            <div className="account-info-row">
              <span className="account-info-label">Full Name</span>
              <span className="account-info-value">{clerkUser?.fullName || 'Not set'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Email</span>
              <span className="account-info-value">{clerkUser?.emailAddresses[0]?.emailAddress || 'Not set'}</span>
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
          
          <div className="account-actions">
            <UserButton>
              <button className="btn btn-ghost btn-full">
                Manage Profile & Security →
              </button>
            </UserButton>
          </div>
        </div>
      </div>
    </div>
  )
}

function SchoolSwitcher() {
  const { activeSchool, schools, canSwitch, setActiveSchool } = useSchoolContext()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click (hooks must be before any return)
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!canSwitch || !activeSchool) return null

  return (
    <div className="school-switcher" ref={ref} style={{ position: 'relative', marginRight: 'var(--space-3)' }}>
      <button
        className="school-switcher__trigger"
        onClick={() => setOpen(!open)}
        title="Switch school context"
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'var(--ink-800)', border: '1px solid var(--ink-600)',
          borderRadius: '8px', padding: '5px 10px', color: 'var(--gold-400)',
          fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ opacity: 0.6 }}>🏫</span>
        <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {activeSchool.name}
        </span>
        <ChevronDownIcon open={open} />
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 4,
          background: 'var(--ink-900)', border: '1px solid var(--ink-600)',
          borderRadius: 8, padding: '4px', minWidth: 200, zIndex: 100,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          <div style={{ padding: '6px 10px', fontSize: 'var(--text-xs)', color: 'var(--ink-400)', fontWeight: 600 }}>
            Active School
          </div>
          {schools.map(s => (
            <button
              key={s.id}
              onClick={() => { setActiveSchool(s.id); setOpen(false) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px',
                background: s.id === activeSchool.id ? 'var(--ink-700)' : 'transparent',
                border: 'none', borderRadius: 6, cursor: 'pointer',
                color: s.id === activeSchool.id ? 'var(--gold-400)' : 'var(--ink-200)',
                fontSize: 'var(--text-sm)', fontWeight: s.id === activeSchool.id ? 600 : 400,
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function App() {
  const { user: clerkUser } = useUser()
  const { signOut } = useClerk()
  const { roles: dbRoles, perms, user: dbUser } = useAuthContext()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const [kpiOpen, setKpiOpen] = useState(false)
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  // Sentry debug function
  const triggerSentryError = () => {
    throw new Error('Sentry Test Error from Frontend')
  }

  // Open command palette from keyboard shortcut
  useEffect(() => {
    const handler = () => setCmdPaletteOpen(true)
    window.addEventListener('open-command-palette', handler)
    return () => window.removeEventListener('open-command-palette', handler)
  }, [])

  useEffect(() => {
    if (!profileOpen) return
    const handleClick = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [profileOpen])

  const handleSignOut = async () => {
    try {
      setProfileOpen(false)
      await signOut()
      window.location.href = '/auth/sign-in'
    } catch (error) {
      console.error('Sign out failed:', error)
    }
  }

  const getDefaultRoute = () => {
    if (!dbUser) return '/dashboard'
    const isAdmin = dbRoles.some(role => 
      role.toLowerCase() === 'admin' || role.toLowerCase() === 'superadmin'
    )
    return isAdmin ? '/dashboard' : '/kpi-entry'
  }

  const closeMobile = () => setMobileNavOpen(false)

  // Detect if we're on auth or home pages to hide topbar
  const location = window.location.pathname
  const isAuthPage = location === '/' || location.startsWith('/auth')

  return (
    <div className="app">
      <div className="bg-texture"></div>

      {/* ─── Top Bar (hidden on auth/home pages) ──── */}
      {(!isAuthPage) && (
      <div className="topbar">
        <div className="brand">
          <Link to="/dashboard" className="brand-link">
            <LogoIcon />
          </Link>
        </div>

        <SignedIn>
          {/* Desktop nav (hidden ≤900px) */}
          <nav className="topbar-nav-desktop">
            {perms.modules.dashboard && <NavLink to="/dashboard" end>Dashboard</NavLink>}

            {/* KPI dropdown */}
            {(perms.modules.kpiEntry || perms.modules.kpiVerification || perms.modules.kra) && (
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                KPI <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                {perms.modules.kpiEntry && <NavLink to="/kpi-entry">KPI Entry</NavLink>}
                {perms.modules.kpiVerification && <NavLink to="/kpi-verification">KPI Verification</NavLink>}
                {perms.modules.kra && <NavLink to="/kra">KRA / KPI Management</NavLink>}
              </div>
            </div>
            )}

            {/* Operations dropdown */}
            {(perms.modules.schools || perms.modules.observations || perms.modules.tasks || perms.modules.reports) && (
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                Operations <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                {perms.modules.schools && <NavLink to="/schools">Schools</NavLink>}
                {perms.modules.observations && <NavLink to="/observations">Observations</NavLink>}
                {perms.modules.tasks && <NavLink to="/tasks">Tasks</NavLink>}
                {perms.modules.reports && <NavLink to="/reports">Reports</NavLink>}
              </div>
            </div>
            )}

            {/* Audit dropdown */}
            {(perms.modules.audit || perms.modules.approvalChains || perms.modules.escalationRules) && (
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                Audit <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                {perms.modules.audit && <NavLink to="/discrepancies">Discrepancies</NavLink>}
                {perms.modules.approvalChains && <NavLink to="/approval-chains">Approval Chains</NavLink>}
                {perms.modules.escalationRules && <NavLink to="/escalation-rules">Escalation Rules</NavLink>}
              </div>
            </div>
            )}

            {/* Administration dropdown */}
            {(perms.modules.departments || perms.modules.users || perms.modules.settings) && (
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                Administration <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                {perms.modules.departments && <NavLink to="/departments">Departments</NavLink>}
                {perms.modules.users && <NavLink to="/users">Users</NavLink>}
                {perms.modules.settings && <NavLink to="/settings">Settings</NavLink>}
                {perms.modules.settings && <NavLink to="/app-settings">App Settings</NavLink>}
                <NavLink to="/account">Account</NavLink>
              </div>
            </div>
            )}
          </nav>
        </SignedIn>

        <div className="top-right">
          <SignedIn>
            <SchoolSwitcher />
            <button
              className="top-right__icon"
              title="Search (Ctrl+K)"
              onClick={() => setCmdPaletteOpen(true)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
            >
              <SearchIcon />
            </button>
            <Link to="/account" className="top-right__icon" title="Help">
              <HelpIcon />
            </Link>

            {/* Hamburger (mobile only) */}
            <button
              className="top-right__burger"
              onClick={() => setMobileNavOpen(!mobileNavOpen)}
              aria-label="Toggle navigation"
            >
              <BurgerIcon open={mobileNavOpen} />
            </button>

            {/* Profile avatar */}
            <div className="profile-wrapper" ref={profileRef}>
              <button
                className="profile-avatar"
                onClick={() => setProfileOpen(!profileOpen)}
                aria-label="Profile menu"
              >
                {clerkUser?.imageUrl ? (
                  <img src={clerkUser.imageUrl} alt="" className="profile-avatar__img" />
                ) : (
                  <span className="profile-avatar__initial">
                    {clerkUser?.fullName?.charAt(0).toUpperCase() || 'U'}
                  </span>
                )}
              </button>
              {profileOpen && (
                <div className="profile-dropdown">
                  <div className="profile-dropdown__header">
                    <div className="profile-dropdown__name">{clerkUser?.fullName || 'User'}</div>
                    <div className="profile-dropdown__email">{clerkUser?.emailAddresses[0]?.emailAddress || ''}</div>
                  </div>
                  <div className="profile-dropdown__divider" />
                  <Link to="/account" className="profile-dropdown__item" onClick={() => setProfileOpen(false)}>Account Settings</Link>
                  <button className="profile-dropdown__item" onClick={triggerSentryError} style={{ color: '#f59e0b' }}>Test Sentry Error</button>
                  <button className="profile-dropdown__item profile-dropdown__item--danger" onClick={handleSignOut}>Sign Out</button>
                </div>
              )}
            </div>
          </SignedIn>

          <SignedOut>
            <SignInButton mode="modal">
              <button className="btn-primary">Sign In</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="btn">Sign Up</button>
            </SignUpButton>
          </SignedOut>
        </div>

      {/* ─── Mobile Nav (slides from top) ────────── */}          <SignedIn>
          <div className={`mobile-nav ${mobileNavOpen ? 'mobile-nav--open' : ''}`}>
          <nav className="mobile-nav__inner">
            {perms.modules.dashboard && <NavLink to="/dashboard" onClick={closeMobile}>Dashboard</NavLink>}

            {/* KPI collapsible */}
            {(perms.modules.kpiEntry || perms.modules.kpiVerification || perms.modules.kra) && (
            <>
              <button className="mobile-nav__collapsible" onClick={() => setKpiOpen(!kpiOpen)}>
                <span>KPI</span>
                <ChevronDownIcon open={kpiOpen} />
              </button>
              {kpiOpen && (
                <div className="mobile-nav__sub">
                  {perms.modules.kpiEntry && <NavLink to="/kpi-entry" onClick={closeMobile}>KPI Entry</NavLink>}
                  {perms.modules.kpiVerification && <NavLink to="/kpi-verification" onClick={closeMobile}>KPI Verification</NavLink>}
                  {perms.modules.kra && <NavLink to="/kra" onClick={closeMobile}>KRA / KPI Management</NavLink>}
                </div>
              )}
            </>
            )}

            {perms.modules.schools && <NavLink to="/schools" onClick={closeMobile}>Schools</NavLink>}
            {perms.modules.observations && <NavLink to="/observations" onClick={closeMobile}>Observations</NavLink>}
            {perms.modules.tasks && <NavLink to="/tasks" onClick={closeMobile}>Tasks</NavLink>}
            {perms.modules.reports && <NavLink to="/reports" onClick={closeMobile}>Reports</NavLink>}

            {/* Administration collapsible */}
            {(perms.modules.departments || perms.modules.users || perms.modules.settings) && (
            <>
              <button className="mobile-nav__collapsible" onClick={() => setAdminOpen(!adminOpen)}>
                <span>Administration</span>
                <ChevronDownIcon open={adminOpen} />
              </button>
              {adminOpen && (
                <div className="mobile-nav__sub">
                  {perms.modules.departments && <NavLink to="/departments" onClick={closeMobile}>Departments</NavLink>}
                  {perms.modules.users && <NavLink to="/users" onClick={closeMobile}>Users</NavLink>}
                  {perms.modules.settings && <NavLink to="/settings" onClick={closeMobile}>Settings</NavLink>}
                  {perms.modules.settings && <NavLink to="/app-settings" onClick={closeMobile}>App Settings</NavLink>}
                </div>
              )}
            </>
            )}

            <NavLink to="/account" onClick={closeMobile}>Account</NavLink>

            <div className="mobile-nav__divider" />
            <button className="mobile-nav__logout" onClick={handleSignOut}>
              <LogOutIcon /> Logout
            </button>
          </nav>
        </div>
      </SignedIn>
      </div>
      )}
      <main className="main">
        <SchoolProvider>
        <KpiProvider>
          <Routes>
            <Route path="/" element={<><SignedIn><Navigate to={getDefaultRoute()} replace /></SignedIn><SignedOut><Home /></SignedOut></>} />
            <Route path="/auth/*" element={<Auth />} />
            <Route path="/account/*" element={<Account />} />
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
            <Route path="/configuration" element={<Navigate to="/settings" replace />} />
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
            <Route path="/discrepancies/:id" element={<RequireAuth><DiscrepancyDetail /></RequireAuth>} />
            <Route path="/approval-chains" element={<RequireAuth><ApprovalChains /></RequireAuth>} />
            {/* Settings */}
            <Route path="/settings" element={<RequireAuth><SettingsMasterData /></RequireAuth>} />
            {/* Observations */}
            <Route path="/observations" element={<RequireAuth><ObservationList /></RequireAuth>} />
            <Route path="/observations/new" element={<RequireAuth><ObservationForm /></RequireAuth>} />
            <Route path="/observations/:id" element={<RequireAuth><ObservationForm /></RequireAuth>} />
            {/* Administration & App Settings */}
            <Route path="/admin" element={<RequireAuth><AdministrationPage /></RequireAuth>} />
            <Route path="/app-settings" element={<RequireAuth><AppSettingsPage /></RequireAuth>} />
          </Routes>
        </KpiProvider>
        </SchoolProvider>
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

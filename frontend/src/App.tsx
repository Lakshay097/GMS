import { Routes, Route, Link, useParams, NavLink, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { SignedIn, SignedOut, UserButton, SignInButton, SignUpButton, useUser, useClerk } from '@clerk/clerk-react'
import { authClient } from './lib/auth'
import React, { useState, useEffect, useRef } from 'react'
import { KpiProvider } from './contexts/KpiContext'

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
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="28" height="28" rx="8" fill="#0A2420"/>
    <path d="M8 14L12 10L16 14L12 18Z" fill="#D4A843"/>
    <path d="M12 10L16 14L20 10" stroke="#D4A843" strokeWidth="1.5" fill="none"/>
  </svg>
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

const Settings2Icon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
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
          <span className="home-wordmark-text">GMS</span>
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
        <span className="home-footer-text">GMS v1.0.0</span>
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
          setProvisioned(data.valid === true && data.user != null)
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
  const { user } = useUser()
  const userRoles = user?.publicMetadata?.roles as string[] || []
  const primaryRole = userRoles[0] || 'Viewer'
  const userSchool = user?.publicMetadata?.school as string || 'Not assigned'
  const userDepartment = user?.publicMetadata?.department as string || 'Not assigned'

  return (
    <div className="account-page">
      <div className="account-page__header">
        <div className="account-page__identity">
          <div className="account-page__avatar">
            {user?.fullName?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="account-page__identity-text">
            <div className="account-page__name-row">
              <span className="account-page__name">{user?.fullName || 'Account'}</span>
              <span className="account-page__role-badge">{primaryRole}</span>
            </div>
            <span className="account-page__email">{user?.emailAddresses[0]?.emailAddress}</span>
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
              <span className="account-info-value">{user?.fullName || 'Not set'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Email</span>
              <span className="account-info-value">{user?.emailAddresses[0]?.emailAddress || 'Not set'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Role(s)</span>
              <span className="account-info-value">{userRoles.join(', ') || 'Not assigned'}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">School</span>
              <span className="account-info-value">{userSchool}</span>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Department</span>
              <span className="account-info-value">{userDepartment}</span>
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

function App() {
  const { t } = useTranslation()
  const { user } = useUser()
  const { signOut } = useClerk()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const [kpiOpen, setKpiOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

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
    if (!user) return '/dashboard'
    const userRoles = user.publicMetadata?.roles as string[] || []
    const isAdmin = userRoles.some(role => 
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
            <span className="brand-name">GMS</span>
          </Link>
        </div>

        <SignedIn>
          {/* Desktop nav (hidden ≤900px) */}
          <nav className="topbar-nav-desktop">
            <NavLink to="/dashboard" end>Dashboard</NavLink>

            {/* KPI dropdown */}
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                KPI <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                <NavLink to="/kpi-entry">KPI Entry</NavLink>
                <NavLink to="/kpi-verification">KPI Verification</NavLink>
                <NavLink to="/kra">KRA / KPI Management</NavLink>
              </div>
            </div>

            {/* Operations dropdown */}
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                Operations <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                <NavLink to="/schools">Schools</NavLink>
                <NavLink to="/observations">Observations</NavLink>
                <NavLink to="/tasks">Tasks</NavLink>
                <NavLink to="/reports">Reports</NavLink>
              </div>
            </div>

            {/* Audit dropdown */}
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                Audit <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                <NavLink to="/discrepancies">Discrepancies</NavLink>
                <NavLink to="/approval-chains">Approval Chains</NavLink>
                <NavLink to="/escalation-rules">Escalation Rules</NavLink>
              </div>
            </div>

            {/* Administration dropdown */}
            <div className="nav-dropdown-hover">
              <button className="nav-dropdown-hover__trigger">
                Administration <ChevronDownIcon open={false} />
              </button>
              <div className="nav-dropdown-hover__menu">
                <NavLink to="/departments">Departments</NavLink>
                <NavLink to="/users">Users</NavLink>
                <NavLink to="/settings">Settings</NavLink>
                <NavLink to="/app-settings">App Settings</NavLink>
                <NavLink to="/account">Account</NavLink>
              </div>
            </div>
          </nav>
        </SignedIn>

        <div className="top-right">
          <SignedIn>
            <Link to="/search" className="top-right__icon" title="Search">
              <SearchIcon />
            </Link>
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
                {user?.imageUrl ? (
                  <img src={user.imageUrl} alt="" className="profile-avatar__img" />
                ) : (
                  <span className="profile-avatar__initial">
                    {user?.fullName?.charAt(0).toUpperCase() || 'U'}
                  </span>
                )}
              </button>
              {profileOpen && (
                <div className="profile-dropdown">
                  <div className="profile-dropdown__header">
                    <div className="profile-dropdown__name">{user?.fullName || 'User'}</div>
                    <div className="profile-dropdown__email">{user?.emailAddresses[0]?.emailAddress || ''}</div>
                  </div>
                  <div className="profile-dropdown__divider" />
                  <Link to="/account" className="profile-dropdown__item" onClick={() => setProfileOpen(false)}>Account Settings</Link>
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
            <NavLink to="/dashboard" onClick={closeMobile}>Dashboard</NavLink>

            {/* KPI collapsible */}
            <button className="mobile-nav__collapsible" onClick={() => setKpiOpen(!kpiOpen)}>
              <span>KPI</span>
              <ChevronDownIcon open={kpiOpen} />
            </button>
            {kpiOpen && (
              <div className="mobile-nav__sub">
                <NavLink to="/kpi-entry" onClick={closeMobile}>KPI Entry</NavLink>
                <NavLink to="/kpi-verification" onClick={closeMobile}>KPI Verification</NavLink>
                <NavLink to="/kra" onClick={closeMobile}>KRA / KPI Management</NavLink>
              </div>
            )}

            <NavLink to="/schools" onClick={closeMobile}>Schools</NavLink>
            <NavLink to="/observations" onClick={closeMobile}>Observations</NavLink>
            <NavLink to="/tasks" onClick={closeMobile}>Tasks</NavLink>
            <NavLink to="/reports" onClick={closeMobile}>Reports</NavLink>

            {/* Administration collapsible */}
            <button className="mobile-nav__collapsible" onClick={() => setAdminOpen(!adminOpen)}>
              <span>Administration</span>
              <ChevronDownIcon open={adminOpen} />
            </button>
            {adminOpen && (
              <div className="mobile-nav__sub">
                <NavLink to="/departments" onClick={closeMobile}>Departments</NavLink>
                <NavLink to="/users" onClick={closeMobile}>Users</NavLink>
                <NavLink to="/settings" onClick={closeMobile}>Settings</NavLink>
                <NavLink to="/app-settings" onClick={closeMobile}>App Settings</NavLink>
              </div>
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
      </main>
    </div>
  )
}

export default App

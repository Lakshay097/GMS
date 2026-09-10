import { useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useAuthContext } from '../../contexts/AuthContext'
import { useSchoolContext } from '../../contexts/SchoolContext'
import NotificationBell from '../notifications/NotificationBell'
import { useCloseOnRouteChange, useDismiss } from '../../hooks/useCloseOnRouteChange'

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

/** Switch the active school scope (superadmin/admin only). */
function SchoolSwitcher() {
  const { activeSchool, schools, canSwitch, setActiveSchool } = useSchoolContext()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const dismissHandlers = useDismiss(ref, open, () => setOpen(false))

  // Close on route change too (hooks before any return)
  useCloseOnRouteChange(open, () => setOpen(false))

  if (!canSwitch || !activeSchool) return null

  return (
    <div className="school-switcher" ref={ref} style={{ position: 'relative', marginRight: 'var(--space-3)' }}>
      <button
        className="school-switcher__trigger"
        onClick={() => setOpen(!open)}
        title="Switch school context"
        aria-expanded={open}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'var(--ink-800)', border: '1px solid var(--ink-600)',
          borderRadius: '8px', padding: '5px 10px', color: 'var(--gold-400)',
          fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ opacity: 0.6, fontSize: 'var(--text-xs)' }}>School</span>
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
        }} {...dismissHandlers}>
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

/**
 * The application chrome: sticky topbar with brand, desktop nav, school
 * switcher, search, notifications, mobile nav, and the profile menu.
 *
 * Owns ALL chrome open/close state in one place with menu exclusivity —
 * opening one surface closes the others — and closes everything on Escape,
 * outside click, focus-out, and route change.
 */
export default function Chrome({ onOpenCommandPalette }: { onOpenCommandPalette: () => void }) {
  const { user, perms, logout } = useAuthContext()

  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [kpiOpen, setKpiOpen] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  // ── Menu exclusivity: opening one chrome surface closes the others ──
  const openMobileNav = (next: boolean) => {
    setMobileNavOpen(next)
    if (next) { setProfileOpen(false); setKpiOpen(false); setAdminOpen(false) }
  }
  const openProfile = (next: boolean) => {
    setProfileOpen(next)
    if (next) setMobileNavOpen(false)
  }

  // ── Global dismissal: Escape closes every chrome surface ──
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setMobileNavOpen(false)
      setProfileOpen(false)
      setKpiOpen(false)
      setAdminOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // ── Auto-close nav (and submenus) on route change ──
  useCloseOnRouteChange(mobileNavOpen, () => { setMobileNavOpen(false); setKpiOpen(false); setAdminOpen(false) })

  // Auto-close nav when viewport crosses the desktop breakpoint
  useEffect(() => {
    const mql = window.matchMedia('(min-width: 1024px)')
    const handler = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) setMobileNavOpen(false)
    }
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  // Profile menu: outside click + focus-out dismissal
  const profileDismiss = useDismiss(profileRef, profileOpen, () => setProfileOpen(false), true)

  const handleSignOut = async () => {
    try {
      setProfileOpen(false)
      await logout()
      // Navigate to home; the session cookie is invalidated server-side
      window.location.href = '/'
    } catch (error) {
      console.error('Sign out failed:', error)
    }
  }

  const closeMobile = () => setMobileNavOpen(false)

  // Sentry debug function — only available in debug mode
  const triggerSentryError = () => {
    throw new Error('Sentry Test Error from Frontend')
  }
  const isDebug = import.meta.env.VITE_DEBUG === 'true'

  return (
    <div className="topbar">
      <div className="brand">
        <Link to="/dashboard" className="brand-link">
          <LogoIcon />
        </Link>
      </div>

      {user && (
        <>
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
              <NavLink to="/account">Account</NavLink>
            </div>
          </div>
          )}
        </nav>
        </>
      )}

      <div className="top-right">
        {user && (
          <>
          <SchoolSwitcher />
          <button
            className="top-right__icon"
            title="Search (Ctrl+K)"
            onClick={onOpenCommandPalette}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
          >
            <SearchIcon />
          </button>
          <Link to="/account" className="top-right__icon" title="Help">
            <HelpIcon />
          </Link>

          {/* In-app notifications — its dropdown closing the profile menu and
              mobile nav is the exclusivity rule in the other direction */}
          <NotificationBell onOpen={() => { setProfileOpen(false); setMobileNavOpen(false) }} />

          {/* Hamburger (mobile only) */}
          <button
            className="top-right__burger"
            onClick={() => openMobileNav(!mobileNavOpen)}
            aria-label="Toggle navigation"
            aria-expanded={mobileNavOpen}
          >
            <BurgerIcon open={mobileNavOpen} />
          </button>

          {/* Profile avatar */}
          <div className="profile-wrapper" ref={profileRef} {...profileDismiss}>
            <button
              className="profile-avatar"
              onClick={() => openProfile(!profileOpen)}
              aria-label="Profile menu"
              aria-expanded={profileOpen}
            >
              <span className="profile-avatar__initial">
                {(user?.full_name || 'U').charAt(0).toUpperCase()}
              </span>
            </button>
            {profileOpen && (
              <div className="profile-dropdown">
                <div className="profile-dropdown__header">
                  <div className="profile-dropdown__name">{user?.full_name || 'User'}</div>
                  <div className="profile-dropdown__email">{user?.email || ''}</div>
                </div>
                <div className="profile-dropdown__divider" />
                <Link to="/account" className="profile-dropdown__item" onClick={() => setProfileOpen(false)}>Account Settings</Link>
                {isDebug && <button className="profile-dropdown__item" onClick={triggerSentryError} style={{ color: '#f59e0b' }}>Test Sentry Error</button>}
                <button className="profile-dropdown__item profile-dropdown__item--danger" onClick={handleSignOut}>Sign Out</button>
              </div>
            )}
          </div>
        </>
        )}

        {!user && (
          <Link to="/auth/sign-in">
            <button className="btn btn-primary">Sign In</button>
          </Link>
        )}
      </div>

      {/* ─── Mobile Nav (slides from top) ────────── */}
      {user && (
        <div className={`mobile-nav ${mobileNavOpen ? 'mobile-nav--open' : ''}`}>
        <nav className="mobile-nav__inner">
          {perms.modules.dashboard && <NavLink to="/dashboard" onClick={closeMobile}>Dashboard</NavLink>}

          {/* KPI collapsible */}
          {(perms.modules.kpiEntry || perms.modules.kpiVerification || perms.modules.kra) && (
          <>
            <button className="mobile-nav__collapsible" onClick={() => { setKpiOpen(!kpiOpen); setAdminOpen(false) }} aria-expanded={kpiOpen}>
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
            <button className="mobile-nav__collapsible" onClick={() => { setAdminOpen(!adminOpen); setKpiOpen(false) }} aria-expanded={adminOpen}>
              <span>Administration</span>
              <ChevronDownIcon open={adminOpen} />
            </button>
            {adminOpen && (
              <div className="mobile-nav__sub">
                {perms.modules.departments && <NavLink to="/departments" onClick={closeMobile}>Departments</NavLink>}
                {perms.modules.users && <NavLink to="/users" onClick={closeMobile}>Users</NavLink>}
                {perms.modules.settings && <NavLink to="/settings" onClick={closeMobile}>Settings</NavLink>}
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
      )}
    </div>
  )
}

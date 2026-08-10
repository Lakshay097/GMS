import { Routes, Route, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthView, AccountView, SignedIn, SignedOut, UserButton } from '@neondatabase/auth/react'
import SchoolList from './components/schools/SchoolList'
import SchoolForm from './components/schools/SchoolForm'
import DepartmentList from './components/departments/DepartmentList'
import DepartmentForm from './components/departments/DepartmentForm'
import UserList from './components/users/UserList'
import UserForm from './components/users/UserForm'
import ConfigurationPanel from './components/configuration/ConfigurationPanel'
import LanguageSwitcher from './components/LanguageSwitcher'
import './App.css'
import './components/module-components.css'

function Home() {
  const { t } = useTranslation()
  return (
    <div className="home">
      <h1>{t('home.title')}</h1>
      <p>{t('home.welcome')}</p>
      <SignedOut>
        <Link to="/auth" className="btn">{t('home.signIn')}</Link>
      </SignedOut>
      <SignedIn>
        <div className="dashboard-links">
          <Link to="/schools" className="btn">{t('nav.schools')}</Link>
          <Link to="/departments" className="btn">{t('nav.departments')}</Link>
          <Link to="/users" className="btn">{t('nav.users')}</Link>
          <Link to="/configuration" className="btn">{t('nav.configuration')}</Link>
        </div>
      </SignedIn>
    </div>
  )
}

function Auth() {
  const { t } = useTranslation()
  return (
    <div className="auth">
      <h1>{t('auth.title')}</h1>
      <AuthView />
    </div>
  )
}

function Account() {
  return (
    <div className="account">
      <div className="account-header">
        <h1>Account</h1>
        <UserButton />
      </div>
      <AccountView />
    </div>
  )
}

function App() {
  const { t } = useTranslation()
  return (
    <div className="app">
      <nav className="navbar">
        <Link to="/" className="nav-link">{t('nav.home')}</Link>
        <SignedIn>
          <Link to="/schools" className="nav-link">{t('nav.schools')}</Link>
          <Link to="/departments" className="nav-link">{t('nav.departments')}</Link>
          <Link to="/users" className="nav-link">{t('nav.users')}</Link>
          <Link to="/configuration" className="nav-link">{t('nav.configuration')}</Link>
          <Link to="/account" className="nav-link">{t('nav.account')}</Link>
        </SignedIn>
        <SignedOut>
          <Link to="/auth" className="nav-link">{t('nav.signIn')}</Link>
        </SignedOut>
        <LanguageSwitcher />
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/account" element={<Account />} />
          <Route path="/schools" element={<SchoolList />} />
          <Route path="/schools/new" element={<SchoolForm />} />
          <Route path="/schools/:id/edit" element={<SchoolForm />} />
          <Route path="/departments" element={<DepartmentList />} />
          <Route path="/departments/new" element={<DepartmentForm />} />
          <Route path="/departments/:id/edit" element={<DepartmentForm />} />
          <Route path="/users" element={<UserList />} />
          <Route path="/users/new" element={<UserForm />} />
          <Route path="/users/:id/edit" element={<UserForm />} />
          <Route path="/configuration" element={<ConfigurationPanel />} />
        </Routes>
      </main>
    </div>
  )
}

export default App

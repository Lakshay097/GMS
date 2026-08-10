import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { NeonAuthUIProvider } from '@neondatabase/auth/react'
import { authClient } from './lib/auth'
import './i18n/config'
import './index.css'
import '@neondatabase/auth/ui/css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <NeonAuthUIProvider authClient={authClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </NeonAuthUIProvider>
  </StrictMode>,
)

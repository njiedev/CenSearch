import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Contact from './Contact'
import LegalPage from './LegalPage'
import { privacy, terms } from './legal'
import SoundEffects from './SoundEffects'

const path = window.location.pathname.replace(/\/(?:index\.html)?$/, '')
const page = path === '/contact'
  ? <Contact />
  : path === '/legal/privacy-policy'
    ? <LegalPage document={privacy} />
    : path === '/legal/terms-of-service'
      ? <LegalPage document={terms} />
      : <App />

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {page}
    <SoundEffects />
  </StrictMode>,
)

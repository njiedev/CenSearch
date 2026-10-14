import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Contact from './Contact'
import { DemoLogIn, DemoSignUp } from './DemoAuth'
import { DEMO } from './demo'
import LegalPage from './LegalPage'
import { privacy, terms } from './legal'
import SignUp from './SignUp'
import SignUpPage from './SignUpPage'
import SoundEffects from './SoundEffects'

// Every page except the dashboard (/app/) is rendered from this entry.
function page(path: string) {
  switch (path) {
    case '/signup':
      return <SignUpPage>{DEMO ? <DemoSignUp /> : <SignUp />}</SignUpPage>
    case '/login':
      return <SignUpPage>{DEMO ? <DemoLogIn /> : <SignUp />}</SignUpPage>
    case '/contact':
      return <Contact />
    case '/legal/privacy-policy':
      return <LegalPage document={privacy} />
    case '/legal/terms-of-service':
      return <LegalPage document={terms} />
    default:
      return <App />
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {page(window.location.pathname.replace(/\/(?:index\.html)?$/, ''))}
    <SoundEffects />
  </StrictMode>,
)

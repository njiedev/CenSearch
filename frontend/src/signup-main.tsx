import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import SignUpPage from './SignUpPage.tsx'
import SoundEffects from './SoundEffects'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SignUpPage />
    <SoundEffects />
  </StrictMode>,
)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './app/theme.css'
import MatchesApp from './matches/MatchesApp.tsx'

document.documentElement.classList.add('dark')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MatchesApp />
  </StrictMode>,
)

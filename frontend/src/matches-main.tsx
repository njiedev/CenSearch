import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './matches/matches.css'
import MatchesApp from './matches/MatchesApp.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MatchesApp />
  </StrictMode>,
)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import SignUpPage from './SignUpPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SignUpPage />
  </StrictMode>,
)

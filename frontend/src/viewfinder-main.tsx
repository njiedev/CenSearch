import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './variants/viewfinder/index.css'
import App from './variants/viewfinder/App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

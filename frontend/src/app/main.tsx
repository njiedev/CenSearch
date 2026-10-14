import { createRoot } from 'react-dom/client'
import App from './App'
import './theme.css'
import './app.css'
import './shell.css'

document.documentElement.classList.add('dark')

createRoot(document.getElementById('root')!).render(<App />)

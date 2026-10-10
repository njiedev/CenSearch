import { useEffect, useState } from 'react'
import { PIXEL_ICONS, pixelPath, type PixelIconName } from './pixelIcons'
import SnakeEye from './SnakeEye'

const MENU = ['File', 'Edit', 'View', 'Watch', 'Special']

// The product loop, plus the pieces around it.
const APPS: { icon: PixelIconName; label: string }[] = [
  { icon: 'enrol', label: 'Enrol' },
  { icon: 'find', label: 'Find' },
  { icon: 'decide', label: 'Decide' },
  { icon: 'send', label: 'Send' },
  { icon: 'verify', label: 'Verify' },
  { icon: 'evidence', label: 'Evidence' },
  { icon: 'agent', label: 'Agent' },
  { icon: 'docs', label: 'Docs' },
]

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 15_000)
    return () => window.clearInterval(id)
  }, [])
  return <time dateTime={now.toISOString()}>{formatTime(now)}</time>
}

export default function Monitor() {
  return (
    <div className="monitor">
      <div className="monitor-bezel">
        <div className="screen">
          <div className="menubar">
            <SnakeEye className="menubar-eye" />
            {MENU.map((item) => (
              <span key={item}>{item}</span>
            ))}
            <span className="menubar-clock">
              <Clock />
            </span>
          </div>
          <ul className="desktop">
            {APPS.map((app) => (
              <li key={app.icon} className="desktop-app">
                <svg className="desktop-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path d={pixelPath(PIXEL_ICONS[app.icon])} />
                </svg>
                <span>{app.label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

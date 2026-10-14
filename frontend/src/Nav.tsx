import { useEffect, useState } from 'react'
import Logo from './Logo'
import { readSession } from './app/session'
import { DEMO } from './demo'

export default function Nav({ onLanding = true }: { onLanding?: boolean }) {
  const home = onLanding ? '' : '/'
  const [scrolled, setScrolled] = useState(() => window.scrollY > 24)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className={`site-header${scrolled ? ' is-scrolled' : ''}`}>
      <nav className="site-nav" aria-label="Main navigation">
        <a className="brand-link" href={`${home}#top`} aria-label="CenSearch">
          <Logo compact />
        </a>
        <div className="nav-links">
          <a href={`${home}#mission`}>Mission</a>
          <a href={`${home}#features`}>Features</a>
          <a href={`${home}#faq`}>FAQ</a>
        </div>
        {readSession() ? (
          <a className="landing-button" href="/app/">Open app</a>
        ) : (
          <div className="nav-actions">
            {DEMO && <a className="landing-link" href="/login/">Log in</a>}
            <a className="landing-button" href="/signup/">Sign up</a>
          </div>
        )}
      </nav>
    </header>
  )
}

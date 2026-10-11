import Logo from './Logo'

export default function Nav() {
  return (
    <header className="site-header">
      <nav className="site-nav" aria-label="Main navigation">
        <a className="brand-link" href="#top" aria-label="CenSearch">
          <Logo />
        </a>
        <div className="nav-links">
          <a href="#mission">Mission</a>
          <a href="#features">Features</a>
          <a href="#faq">FAQ</a>
        </div>
        <a className="landing-button" href="/signup.html">Sign up</a>
      </nav>
    </header>
  )
}

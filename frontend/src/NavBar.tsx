import SnakeEye from './SnakeEye'

// Only "How it works" has a section so far; the rest are placeholders.
const LINKS = [
  { label: 'Product', href: '#' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Agent', href: '#' },
  { label: 'Privacy', href: '#' },
  { label: 'Docs', href: '#' },
]

export default function NavBar() {
  return (
    <header className="nav">
      <nav className="nav-links" aria-label="Main">
        {LINKS.map((link) => (
          <a key={link.label} className="nav-link" href={link.href}>
            {link.label}
          </a>
        ))}
      </nav>
      <a className="nav-home" href="#top" aria-label="CenSearch home">
        <SnakeEye className="nav-eye" track />
      </a>
      <div className="nav-actions">
        <a className="nav-link nav-talk" href="#">
          Talk to the team
        </a>
        <a className="nav-cta" href="#how-it-works">
          Get started
        </a>
      </div>
    </header>
  )
}

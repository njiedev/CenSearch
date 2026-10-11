import './VariantSwitch.css'

// Switches between the landing designs. Each design is its own page with its
// own stylesheet, so they can't leak styles into each other.
const VARIANTS = [
  { id: 'hero', label: 'Hero', href: '/' },
  { id: 'viewfinder', label: 'Viewfinder', href: '/viewfinder.html' },
] as const

type VariantId = (typeof VARIANTS)[number]['id']

export default function VariantSwitch({ current }: { current: VariantId }) {
  return (
    <nav className="variant-switch" aria-label="Landing design">
      <span className="variant-switch-title">Design</span>
      {VARIANTS.map((variant) => (
        <a
          key={variant.id}
          className="variant-switch-option"
          href={variant.href}
          aria-current={variant.id === current ? 'page' : undefined}
        >
          {variant.label}
        </a>
      ))}
    </nav>
  )
}

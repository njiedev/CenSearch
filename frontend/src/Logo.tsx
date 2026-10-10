// The wordmark: CENSOR with the O drawn as an eye. Futura Bold comes from the
// system (it ships with macOS); see the fallback stack in index.css.
export default function Logo() {
  return (
    <h1 className="logo" aria-label="CENSOR">
      <span aria-hidden="true">CENS</span>
      <svg className="logo-eye" viewBox="0 0 120 72" aria-hidden="true">
        <path d="M9 36 Q60 -14 111 36 Q60 86 9 36 Z" />
        <circle cx="60" cy="36" r="11" />
      </svg>
      <span aria-hidden="true">R</span>
    </h1>
  )
}

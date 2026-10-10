// The wordmark: CENSEARCH with the A drawn as an eye. Futura Bold comes from
// the system (it ships with macOS); see the fallback stack in index.css.
export default function Logo() {
  return (
    <h1 className="logo" aria-label="CenSearch">
      <span aria-hidden="true">CENSE</span>
      <svg className="logo-eye" viewBox="0 0 120 72" aria-hidden="true">
        <path d="M9 36 Q60 -14 111 36 Q60 86 9 36 Z" />
        <circle cx="60" cy="36" r="11" />
      </svg>
      <span aria-hidden="true">RCH</span>
    </h1>
  )
}

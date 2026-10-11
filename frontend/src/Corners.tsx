// The four camera-viewfinder brackets. The parent sets --vf-line, --vf-inset
// and --vf-stroke and must be positioned.
export default function Corners() {
  return (
    <>
      <span className="vf-corner vf-tl" aria-hidden="true" />
      <span className="vf-corner vf-tr" aria-hidden="true" />
      <span className="vf-corner vf-bl" aria-hidden="true" />
      <span className="vf-corner vf-br" aria-hidden="true" />
    </>
  )
}

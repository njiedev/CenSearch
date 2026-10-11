import { useEffect, useRef, useState } from 'react'
import Corners from './Corners'
import { Battery, Clock, Timecode } from './Hud'
import SnakeEye from './SnakeEye'

const HEADING = 'About Us'
const BODY = "We search the web for your face and send deletion requests wherever they're needed."
const TYPE_MS = 35 // per character
const PAUSE_MS = 400 // between heading and body

// Types the heading, then the body, once `start` turns true. With reduced
// motion the text appears in full right away.
function useTypewriter(start: boolean) {
  const total = HEADING.length + BODY.length
  const [count, setCount] = useState(0)
  const [instant] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)

  useEffect(() => {
    if (!start || instant) {
      return
    }
    let typed = 0
    let id = 0
    function step() {
      typed++
      setCount(typed)
      if (typed < total) {
        id = window.setTimeout(step, typed === HEADING.length ? PAUSE_MS : TYPE_MS)
      }
    }
    id = window.setTimeout(step, PAUSE_MS)
    return () => window.clearTimeout(id)
  }, [start, instant, total])

  const shown = start && instant ? total : count
  return {
    heading: HEADING.slice(0, shown),
    body: BODY.slice(0, Math.max(0, shown - HEADING.length)),
    onHeading: shown < HEADING.length,
  }
}

export default function Viewfinder() {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)
  const typed = useTypewriter(inView)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.5 },
    )
    observer.observe(ref.current!)
    return () => observer.disconnect()
  }, [])

  const caret = <span className="vf-caret" aria-hidden="true" />

  return (
    <div className="viewfinder" ref={ref}>
      <Corners />

      <div className="vf-hud vf-top" aria-hidden="true">
        <span className="vf-rec">
          <span className="vf-rec-dot" />
          Recording without your permission
        </span>
        <Clock />
        <Battery />
      </div>

      <div className="vf-main">
        <div className="vf-copy">
          {/* Screen readers get the full text; the typed copy is visual only. */}
          <h2 className="visually-hidden">{HEADING}</h2>
          <p className="visually-hidden">{BODY}</p>
          <p className="vf-heading" aria-hidden="true">
            {typed.heading}
            {typed.onHeading && caret}
          </p>
          <p className="vf-body" aria-hidden="true">
            {typed.body}
            {!typed.onHeading && caret}
          </p>
        </div>
        <SnakeEye className="vf-eye" track />
      </div>

      <div className="vf-hud vf-bottom" aria-hidden="true">
        <Timecode />
      </div>
    </div>
  )
}

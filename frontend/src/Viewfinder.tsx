import { useEffect, useRef, useState } from 'react'
import Corners from './Corners'
import SnakeEye from './SnakeEye'

const HEADING = 'About Us'
const BODY = "We search the web for your face and send deletion requests wherever they're needed."
const TYPE_MS = 35 // per character
const PAUSE_MS = 400 // between heading and body
const FPS = 24 // timecode frames

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  return <time dateTime={now.toISOString()}>{time}</time>
}

// Recording length as HH:MM:SS:FF, written straight to the DOM every frame.
function Timecode() {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const start = performance.now()
    let frame = 0
    function tick(now: number) {
      const frames = Math.floor(((now - start) / 1000) * FPS)
      const seconds = Math.floor(frames / FPS)
      ref.current!.textContent = [
        pad(Math.floor(seconds / 3600)),
        pad(Math.floor(seconds / 60) % 60),
        pad(seconds % 60),
        pad(frames % FPS),
      ].join(':')
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [])
  return <span ref={ref}>00:00:00:00</span>
}

function Battery() {
  return (
    <svg className="vf-battery" viewBox="0 0 40 20" aria-hidden="true">
      <rect x="1" y="1" width="34" height="18" rx="2" />
      <rect className="vf-battery-tip" x="36" y="6" width="3" height="8" rx="1" />
      <rect className="vf-battery-cell" x="5" y="5" width="7" height="10" />
      <rect className="vf-battery-cell" x="14" y="5" width="7" height="10" />
      <rect className="vf-battery-cell" x="23" y="5" width="7" height="10" />
    </svg>
  )
}

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

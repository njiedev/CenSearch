import { useEffect, useRef, useState } from 'react'

// Camera HUD readouts shared by the viewfinder screens.

const FPS = 24 // timecode frames

function pad(value: number) {
  return String(value).padStart(2, '0')
}

export function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  return <time dateTime={now.toISOString()}>{time}</time>
}

// Recording length as HH:MM:SS:FF, written straight to the DOM every frame.
export function Timecode() {
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

export function Battery() {
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

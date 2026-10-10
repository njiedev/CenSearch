import { useId, useState } from 'react'

// The eye's top edge is the upper lid: a curve from corner to corner whose
// control point sets how open it is. The bottom edge never moves.
const OPEN = 30 // half open: a flat lid over the top of the pupil
const SHUT = 86 // same as the bottom curve, so the eye becomes one line

function eye(lid: number) {
  return `M9 36 Q60 ${lid} 111 36 Q60 86 9 36 Z`
}

// A slow close and reopen, then a quick blink later on. 8s per loop.
const FRAMES = [OPEN, OPEN, SHUT, SHUT, OPEN, OPEN, SHUT, OPEN, OPEN]
const TIMES = [0, 0.38, 0.46, 0.5, 0.58, 0.84, 0.87, 0.9, 1]
const VALUES = FRAMES.map(eye).join(';')
const KEY_TIMES = TIMES.join(';')
const SPLINES = Array(FRAMES.length - 1).fill('0.42 0 0.58 1').join(';')

function Lid() {
  return (
    <animate
      attributeName="d"
      dur="8s"
      repeatCount="indefinite"
      calcMode="spline"
      values={VALUES}
      keyTimes={KEY_TIMES}
      keySplines={SPLINES}
    />
  )
}

// The wordmark: CENSEARCH with the A drawn as a half-open eye whose lid
// closes and reopens. Futura Bold comes from the system (it ships with
// macOS); see the fallback stack in index.css.
export default function Logo() {
  const clipId = `${useId()}-eye`
  const [still] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)

  return (
    <h1 className="logo" aria-label="CenSearch">
      <span aria-hidden="true">CENSE</span>
      <svg className="logo-eye" viewBox="0 0 120 72" aria-hidden="true">
        <clipPath id={clipId}>
          <path d={eye(OPEN)}>{!still && <Lid />}</path>
        </clipPath>
        <circle className="logo-pupil" cx="60" cy="40" r="12" clipPath={`url(#${clipId})`} />
        <path className="logo-outline" d={eye(OPEN)}>
          {!still && <Lid />}
        </path>
      </svg>
      <span aria-hidden="true">RCH</span>
    </h1>
  )
}

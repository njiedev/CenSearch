import { useEffect, useId, useState } from 'react'

// The eye outline never changes. Inside it, the upper lid is a filled shape
// whose lower edge curves from corner to corner; that curve's control point
// sets how open the eye is. The pupil is clipped to the area below the lid.
const OUTLINE = 'M9 36 Q60 -14 111 36 Q60 86 9 36 Z'

const WIDE = -14 // lid tucked into the top of the outline
const OPEN = 4
const HALF = 30
const SQUINT = 50
const SHUT = 86 // lid lies on the bottom curve

function lidLine(lid: number) {
  return `M9 36 Q60 ${lid} 111 36`
}

// The lid itself: the area between the top of the outline and the lid line.
function lidFill(lid: number) {
  return `M9 36 Q60 -14 111 36 Q60 ${lid} 9 36 Z`
}

function visible(lid: number) {
  return `M9 36 Q60 ${lid} 111 36 Q60 86 9 36 Z`
}

// Lid and pupil loop at different lengths, so together they rarely repeat.
const LID_SECONDS = 13
const LID: [number, number][] = [
  [0, HALF],
  [0.15, HALF],
  [0.21, OPEN],
  [0.38, OPEN],
  [0.44, HALF],
  [0.54, HALF],
  [0.57, SHUT],
  [0.6, HALF],
  [0.68, SQUINT],
  [0.8, SQUINT],
  [0.84, WIDE],
  [0.88, WIDE],
  [0.93, HALF],
  [1, HALF],
]

const PUPIL_SECONDS = 11
const CENTER = 60
const PUPIL: [number, number][] = [
  [0, CENTER],
  [0.2, CENTER],
  [0.24, 44], // look left
  [0.4, 44],
  [0.44, CENTER],
  [0.6, CENTER],
  [0.64, 76], // look right
  [0.8, 76],
  [0.84, CENTER],
  [1, CENTER],
]

function Animate({
  attribute,
  seconds,
  frames,
  format,
}: {
  attribute: string
  seconds: number
  frames: [number, number][]
  format: (value: number) => string
}) {
  return (
    <animate
      attributeName={attribute}
      dur={`${seconds}s`}
      repeatCount="indefinite"
      calcMode="spline"
      keyTimes={frames.map(([time]) => time).join(';')}
      values={frames.map(([, value]) => format(value)).join(';')}
      keySplines={Array(frames.length - 1).fill('0.42 0 0.58 1').join(';')}
    />
  )
}

// Shared eye animation for the compact navigation and footer marks.
export function Eye({ gaze }: { gaze?: { x: number; y: number; lid: number } }) {
  const clipId = `${useId()}-eye`
  const [still, setStill] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setStill(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  return (
    <svg className="logo-eye" viewBox="0 0 120 72" aria-hidden="true">
      <clipPath id={clipId}>
        <path d={visible(gaze && !still ? gaze.lid : HALF)}>
          {!still && !gaze && <Animate attribute="d" seconds={LID_SECONDS} frames={LID} format={visible} />}
        </path>
      </clipPath>
      <circle className="logo-pupil" cx={gaze && !still ? gaze.x : CENTER} cy={gaze && !still ? gaze.y : 40} r="12" clipPath={`url(#${clipId})`}>
        {!still && !gaze && <Animate attribute="cx" seconds={PUPIL_SECONDS} frames={PUPIL} format={String} />}
      </circle>
      <path className="logo-lid-fill" d={lidFill(gaze && !still ? gaze.lid : HALF)}>
        {!still && !gaze && <Animate attribute="d" seconds={LID_SECONDS} frames={LID} format={lidFill} />}
      </path>
      <path className="logo-lid" d={lidLine(gaze && !still ? gaze.lid : HALF)}>
        {!still && !gaze && <Animate attribute="d" seconds={LID_SECONDS} frames={LID} format={lidLine} />}
      </path>
      <path className="logo-outline" d={OUTLINE} />
    </svg>
  )
}

export default function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="logo" role="img" aria-label="CenSearch">
      <Eye />
      <span aria-hidden="true">{compact ? 'CS' : 'CenSearch'}</span>
    </span>
  )
}

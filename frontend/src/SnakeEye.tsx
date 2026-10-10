import { useEffect, useId, useRef } from 'react'

const REACH_PX = 240 // cursor distance at which the pupil reaches its limit
const MAX_X = 6 // pupil travel in viewBox units
const MAX_Y = 4

type Props = {
  className?: string
  track?: boolean
}

// A purple snake eye. With `track`, the slit pupil follows the cursor.
export default function SnakeEye({ className, track = false }: Props) {
  const pupilRef = useRef<SVGGElement>(null)
  const id = useId()

  useEffect(() => {
    if (!track) {
      return
    }
    const pupil = pupilRef.current!
    const svg = pupil.ownerSVGElement!
    let frame = 0
    let pointerX = 0
    let pointerY = 0

    function update() {
      frame = 0
      const box = svg.getBoundingClientRect()
      const dx = pointerX - (box.left + box.width / 2)
      const dy = pointerY - (box.top + box.height / 2)
      const distance = Math.hypot(dx, dy) || 1
      const reach = Math.min(1, distance / REACH_PX)
      const x = (dx / distance) * reach * MAX_X
      const y = (dy / distance) * reach * MAX_Y
      pupil.style.transform = `translate(${x}px, ${y}px)`
    }

    function onMove(event: PointerEvent) {
      pointerX = event.clientX
      pointerY = event.clientY
      if (!frame) {
        frame = requestAnimationFrame(update)
      }
    }

    window.addEventListener('pointermove', onMove)
    return () => {
      window.removeEventListener('pointermove', onMove)
      cancelAnimationFrame(frame)
    }
  }, [track])

  return (
    <svg className={className} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <radialGradient id={`${id}-iris`} cx="50%" cy="45%" r="55%">
          <stop offset="0%" stopColor="#f3e8ff" />
          <stop offset="30%" stopColor="#c084fc" />
          <stop offset="65%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#2e1065" />
        </radialGradient>
        <clipPath id={`${id}-clip`}>
          <circle cx="20" cy="20" r="15" />
        </clipPath>
      </defs>
      <circle cx="20" cy="20" r="19" fill="#0d0716" stroke="#3b2566" strokeWidth="1.5" />
      <circle cx="20" cy="20" r="15" fill={`url(#${id}-iris)`} />
      <g clipPath={`url(#${id}-clip)`}>
        <g className="eye-pupil" ref={pupilRef}>
          <ellipse cx="20" cy="20" rx="2.6" ry="11.5" fill="#07030d" />
        </g>
      </g>
      <circle cx="15.5" cy="13.5" r="1.8" fill="#fff" opacity="0.85" />
    </svg>
  )
}

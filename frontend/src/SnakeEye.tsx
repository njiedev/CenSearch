import { useEffect, useRef } from 'react'
import irisUrl from './assets/eye/iris.png'
import pupilUrl from './assets/eye/pupil.png'
import rimUrl from './assets/eye/rim.png'

// The pixel-art snake eye is 29×26 art pixels, split into three layers: the
// iris, the slit pupil with its highlights, and the outline with its glint.
// Only the pupil moves.
const ART_WIDTH = 29
const ART_HEIGHT = 26
const REACH_PX = 240 // cursor distance at which the pupil reaches its limit
const MAX_X = 4 // pupil travel in art pixels
const MAX_Y = 2

type Props = {
  className?: string
  track?: boolean
  lookAt?: { x: number; y: number } | null
}

export default function SnakeEye({ className, track = false, lookAt = null }: Props) {
  const pupilRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    if (!track && !lookAt) {
      if (pupilRef.current) pupilRef.current.style.transform = 'none'
      return
    }
    const pupil = pupilRef.current!
    const eye = pupil.parentElement!.parentElement!
    let frame = 0
    let pointerX = lookAt?.x ?? 0
    let pointerY = lookAt?.y ?? 0

    function update() {
      frame = 0
      const box = eye.getBoundingClientRect()
      const dx = pointerX - (box.left + box.width / 2)
      const dy = pointerY - (box.top + box.height / 2)
      const distance = Math.hypot(dx, dy) || 1
      const reach = Math.min(1, distance / REACH_PX)
      // Whole art pixels only, so the pupil moves like a sprite.
      const x = Math.round((dx / distance) * reach * MAX_X)
      const y = Math.round((dy / distance) * reach * MAX_Y)
      pupil.style.transform = `translate(${(x / ART_WIDTH) * 100}%, ${(y / ART_HEIGHT) * 100}%)`
    }

    function onMove(event: PointerEvent) {
      pointerX = event.clientX
      pointerY = event.clientY
      if (!frame) {
        frame = requestAnimationFrame(update)
      }
    }

    if (lookAt) frame = requestAnimationFrame(update)
    else window.addEventListener('pointermove', onMove)
    return () => {
      window.removeEventListener('pointermove', onMove)
      cancelAnimationFrame(frame)
    }
  }, [track, lookAt])

  return (
    <span className={`pixel-eye ${className ?? ''}`} aria-hidden="true">
      <img src={irisUrl} alt="" draggable={false} />
      <span className="pixel-eye-clip" style={{ maskImage: `url(${irisUrl})` }}>
        <img src={pupilUrl} alt="" draggable={false} ref={pupilRef} />
      </span>
      <img src={rimUrl} alt="" draggable={false} />
    </span>
  )
}

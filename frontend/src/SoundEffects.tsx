import { useEffect } from 'react'
import { play, setEnabled } from 'cuelume'

function interactiveTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return null
  const element = target.closest('a[href], button, summary')
  if (!element || element.closest('[data-sound="off"], [inert], [aria-disabled="true"]') || element.matches(':disabled')) {
    return null
  }
  return element
}

// Same Cuelume palette used by gholtz.app: tick / page / toggle / bloom.
// Delegation covers new React content without observing or rewriting the DOM.
export default function SoundEffects() {
  useEffect(() => {
    setEnabled(typeof window.AudioContext === 'function')
    let lastHover = -Infinity
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)')
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

    function onHover(event: PointerEvent) {
      if (document.hidden || event.pointerType !== 'mouse' || !finePointer.matches || reducedMotion.matches) return
      const element = interactiveTarget(event.target)
      if (!element?.matches('a[href]')) return
      if (event.relatedTarget instanceof Node && element.contains(event.relatedTarget)) return
      const now = performance.now()
      if (now - lastHover < 150) return
      lastHover = now
      play('tick')
    }

    function onClick(event: MouseEvent) {
      if (document.hidden || event.button !== 0) return
      const element = interactiveTarget(event.target)
      if (!element) return
      play(element.matches('summary') ? 'bloom' : element.matches('a[href]') ? 'page' : 'toggle')
    }

    document.addEventListener('pointerover', onHover)
    // Capture before React changes the target; native click includes keyboard activation.
    document.addEventListener('click', onClick, true)
    return () => {
      document.removeEventListener('pointerover', onHover)
      document.removeEventListener('click', onClick, true)
      setEnabled(false)
    }
  }, [])

  return null
}

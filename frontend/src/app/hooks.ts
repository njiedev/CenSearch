import { useEffect, useRef, useState } from 'react'
export function usePoll<T>(
  load: () => Promise<T>,
  dependencies: unknown[],
  interval = 0,
  identity = JSON.stringify(dependencies),
) {
  const loader = useRef(load)
  loader.current = load
  const [snapshot, setSnapshot] = useState<{ identity: string; value: T } | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    let timer = 0
    setError('')
    async function tick() {
      try {
        const result = await loader.current()
        if (active) {
          setSnapshot({ identity, value: result })
          setError('')
        }
      } catch (failure) {
        if (active) setError(String(failure instanceof Error ? failure.message : failure))
      }
      if (active && interval)
        timer = window.setTimeout(tick, document.hidden ? Math.max(interval, 5000) : interval)
    }
    void tick()
    return () => {
      active = false
      clearTimeout(timer)
    }
    // Callers supply their resource identity, as for an effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, interval, revision])
  return {
    value: snapshot?.identity === identity ? snapshot.value : null,
    error,
    retry: () => setRevision((n) => n + 1),
  }
}
export function duration(start: string | null, end: string | null) {
  if (!start || !end) return '-'
  const seconds = Math.max(0, Math.round((Date.parse(end) - Date.parse(start)) / 1000))
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m ${seconds % 60}s` : `${seconds}s`
}
export function date(value: string | null) {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '-'
}
export function relative(value: string | null) {
  if (!value) return '-'
  const days = Math.floor((Date.now() - Date.parse(value)) / 86400000)
  return days < 1 ? 'Today' : days === 1 ? 'Yesterday' : `${days} days ago`
}

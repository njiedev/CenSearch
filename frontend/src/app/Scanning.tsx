import { useEffect, useRef, useState } from 'react'
import SnakeEye from '../SnakeEye'
import { api } from './api'
import { ErrorBox, Loading } from './ui'
import { usePoll } from './hooks'
import type { Run } from './types'

function ScanAnimation() {
  const stage = useRef<HTMLDivElement>(null)
  const tiles = useRef<(HTMLDivElement | null)[]>([])
  const [lookAt, setLookAt] = useState<{ x: number; y: number } | null>(null)
  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    let frame = 0
    let last = 0
    let elapsed = 0
    let lastGaze = 0
    let box = stage.current!.getBoundingClientRect()
    const resize = new ResizeObserver(() => {
      box = stage.current!.getBoundingClientRect()
    })
    resize.observe(stage.current!)
    function draw(now: number) {
      elapsed += last ? Math.min(now - last, 50) : 0
      last = now
      tiles.current.forEach((tile, i) => {
        if (!tile) return
        const t = ((elapsed - i * 1500 + 9000) % 9000) / 9000
        const side = i % 2 ? 1 : -1
        const x = side * Math.min(box.width * 0.4, 340) * t
        const y = 80 - 240 * t + 90 * t * t
        tile.style.transform = `translate(${x}px, ${y}px) rotate(${side * t * 8}deg)`
        tile.style.opacity = String(Math.min(t * 8, (1 - t) * (i === 0 ? 8 : 5), 0.75))
        const watching = t >= 0.2 && t < 0.367
        tile.dataset.watching = String(watching)
        tile.dataset.resolved = String(t >= 0.367)
        if (watching && elapsed - lastGaze > 180)
          setLookAt({ x: box.left + box.width / 2 + x, y: box.top + box.height / 2 + y })
      })
      if (elapsed - lastGaze > 180) lastGaze = elapsed
      frame = requestAnimationFrame(draw)
    }
    function resume() {
      cancelAnimationFrame(frame)
      last = 0
      if (document.hidden || media.matches) {
        setLookAt(null)
        return
      }
      frame = requestAnimationFrame(draw)
    }
    resume()
    document.addEventListener('visibilitychange', resume)
    media.addEventListener('change', resume)
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      document.removeEventListener('visibilitychange', resume)
      media.removeEventListener('change', resume)
    }
  }, [])
  return (
    <div className="scan-art" ref={stage} aria-hidden="true">
      {[63, 77, 88, 49, 60, 74].map((photo, i) => (
        <div
          className={`scan-tile ${i === 0 ? 'match' : ''}`}
          ref={(node) => {
            tiles.current[i] = node
          }}
          key={photo}
        >
          <img src={`/photos/${photo}.jpg`} alt="" />
          <span>{i === 0 ? '✓ Match' : '– No match'}</span>
        </div>
      ))}
      <SnakeEye className="scan-eye" lookAt={lookAt} />
    </div>
  )
}
export default function Scanning({
  id,
  onDone,
  onResults,
  onRetry,
}: {
  id: number
  onDone: () => void
  onResults: () => void
  onRetry: () => void
}) {
  const announced = useRef<{ at: number; run: Run } | null>(null)
  const [finished, setFinished] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const {
    value: run,
    error,
    retry,
  } = usePoll<Run>(
    async () => {
      const result = await api.run(id)
      const timestamp = Date.now()
      if (
        ['running', 'queued'].includes(result.status) &&
        announced.current &&
        timestamp - announced.current.at < 2900
      )
        return announced.current.run
      announced.current = { at: timestamp, run: result }
      setNow(timestamp)
      setFinished(!['running', 'queued'].includes(result.status))
      return result
    },
    [id],
    finished ? 0 : 1500,
  )
  const [cancelError, setCancelError] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const doneCallback = useRef(onDone)
  useEffect(() => {
    doneCallback.current = onDone
  }, [onDone])
  useEffect(() => {
    if (!run || ['running', 'queued'].includes(run.status)) return
    if (run.status.startsWith('completed')) {
      const timer = setTimeout(() => doneCallback.current(), 400)
      return () => clearTimeout(timer)
    }
  }, [run])
  async function cancel() {
    setCancelling(true)
    try {
      await api.cancel(id)
      retry()
    } catch (failure) {
      setCancelError((failure as Error).message)
    } finally {
      setCancelling(false)
    }
  }
  if (!run) return error ? <ErrorBox error={error} retry={retry} /> : <Loading />
  const pagesFetched = run.pages ? run.pages.filter((page) => page.fetched_at).length : run.metrics.pages
  const stopped = ['failed', 'cancelled', 'interrupted'].includes(run.status)
  const elapsed = Math.max(
    0,
    Math.floor(((run.finished_at ? Date.parse(run.finished_at) : now) - Date.parse(run.started_at)) / 1000),
  )
  return (
    <section className="scan-view">
      {!stopped && <ScanAnimation />}
      <div className="scan-status" aria-live="polite" aria-atomic="true">
        <h1>
          {stopped
            ? `Scan ${run.status}`
            : run.metrics.analysed
              ? 'Checking images…'
              : pagesFetched
                ? 'Reading public pages…'
                : 'Searching for pages…'}
        </h1>
        <p>
          {stopped
            ? 'Start a new scan, or inspect any matches already found.'
            : 'Matching runs locally. The tiles above are decorative, not search results.'}
        </p>
        <div className="summary">
          <span>
            <strong>{pagesFetched ?? '-'}</strong>pages fetched
          </span>
          <span>
            <strong>{run.metrics.analysed ?? '-'}</strong>images checked
          </span>
          <span>
            <strong>{run.results?.length ?? run.metrics.matches ?? '-'}</strong>matches so far
          </span>
          <span>
            <strong>{elapsed}s</strong>elapsed
          </span>
        </div>
        {run.errors?.length > 0 && (
          <p className="field-error">
            {run.errors.map((item) => item.message || item.error || 'A page could not be checked.').join(' ')}
          </p>
        )}
      </div>
      {error && <ErrorBox error={error} retry={retry} />}
      {cancelError && <ErrorBox error={cancelError} retry={() => void cancel()} />}
      {stopped ? (
        <div className="actions">
          <button className="primary" onClick={onRetry}>
            Start a new scan
          </button>
          {run.results.length > 0 && <button onClick={onResults}>Open partial results</button>}
        </div>
      ) : (
        <button disabled={cancelling || finished} onClick={cancel}>
          {cancelling ? 'Cancelling…' : 'Cancel scan'}
        </button>
      )}
    </section>
  )
}

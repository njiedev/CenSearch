import { MATCH_PHOTOS } from '../demoPhotos'
import { Eye } from '../Logo'
import { DustLayer } from '../dust'
import { Button } from "@/components/ui/button"
import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { ErrorBox, Loading } from './ui'
import { usePoll } from './hooks'
import type { Run } from './types'
import FaceSearchResults from './FaceSearchResults'

export function ScanAnimation() {
  const stage = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const tiles = useRef<(HTMLDivElement | null)[]>([])
  const [gaze, setGaze] = useState({ x: 60, y: 40, lid: 30 })
  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    const dust = new DustLayer(canvas.current!, 0.7)
    let frame = 0
    let last = 0
    let elapsed = 0
    let lastPhase = ''
    const dissolved = new Set<number>()
    function draw(now: number) {
      elapsed += last ? Math.min(now - last, 50) : 0
      last = now
      const turn = Math.floor(elapsed / 2400)
      const watching = elapsed % 2400 > 300
      const deciding = elapsed % 2400 > 1200
      const phase = `${turn}/${watching}/${deciding}`
      if (phase !== lastPhase) {
        lastPhase = phase
        setGaze({
          x: watching ? [43, 60, 77][turn % 3] : 60,
          y: watching ? 30 : 40,
          lid: deciding ? 24 : 4,
        })
      }
      tiles.current.forEach((tile, i) => {
        if (!tile) return
        const age = (elapsed - i * 2400 + 14400) % 14400
        const visible = elapsed >= i * 2400 && age < 4700
        const cycle = Math.floor(elapsed / 14400) * 6 + i
        tile.style.opacity = visible ? String(Math.min(age / 300, (4700 - age) / 800, 1)) : '0'
        tile.style.transform = `translateY(${visible ? Math.max(0, 12 - age / 25) : 12}px)`
        tile.dataset.watching = String(visible && age >= 300 && age < 1200)
        tile.dataset.resolved = String(visible && age >= 1200)
        if (visible && age < 300) tile.querySelector('img')!.style.opacity = '1'
        if (visible && age >= 2200 && i % 2 && !dissolved.has(cycle)) {
          dissolved.add(cycle)
          const img = tile.querySelector('img')!
          void dust.disintegrate(img, () => { img.style.opacity = '0' })
        }
      })
      frame = requestAnimationFrame(draw)
    }
    function resume() {
      cancelAnimationFrame(frame)
      dust.clear()
      last = 0
      if (document.hidden || media.matches) {
        setGaze({ x: 60, y: 40, lid: 30 })
        return
      }
      frame = requestAnimationFrame(draw)
    }
    const resize = () => dust.resize()
    resume()
    window.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', resume)
    media.addEventListener('change', resume)
    return () => {
      cancelAnimationFrame(frame)
      dust.clear()
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', resume)
      media.removeEventListener('change', resume)
    }
  }, [])
  return (
    <div className="scan-art" ref={stage} aria-hidden="true">
      {MATCH_PHOTOS.slice(0, 6).map((photo, i) => (
        <div
          className={`scan-tile ${i % 2 ? 'dismiss' : 'match'} scan-slot-${i % 3}`}
          ref={(node) => { tiles.current[i] = node }}
          key={photo}
        >
          <img src={photo} alt="" />
          <span>{i % 2 ? '×' : '✓'}</span>
        </div>
      ))}
      <canvas className="scan-dust" ref={canvas} />
      <div className="scan-eye"><Eye gaze={gaze} /></div>
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
  const searching = !!run.facecheck && ['uploading', 'submitting', 'searching'].includes(run.facecheck.status)
  const stage = finished ? 3 : run.metrics.analysed ? 2 : searching ? 0 : 1
  const steps = [
    run.facecheck && {
      at: 0,
      label: 'Searching the web for your face',
      detail: run.facecheck.status === 'completed'
        ? `${run.facecheck.items.length} candidates scored 88 or higher`
        : `${run.facecheck.progress ?? 0}% · keeping scores of 88 or higher`,
    },
    { at: 1, label: 'Reading the public pages', detail: `${pagesFetched ?? 0} pages fetched` },
    { at: 2, label: 'Comparing faces and photos', detail: `${run.metrics.analysed ?? 0} images checked` },
    { at: 3, label: 'Matches ready', detail: `${run.results?.length ?? run.metrics.matches ?? 0} found` },
  ].filter((step): step is { at: number; label: string; detail: string } => !!step && step.at <= stage)
  return (
    <section className="scan-view">
      {!stopped && !finished && <ScanAnimation />}
      <div className="scan-status" aria-live="polite" aria-atomic="true">
        <h1>
          {stopped
            ? `Scan ${run.status}`
            : run.facecheck && ['uploading', 'submitting', 'searching'].includes(run.facecheck.status)
              ? 'Searching FaceCheck'
              : run.metrics.analysed
              ? 'Checking images'
              : pagesFetched
                ? 'Reading public pages'
                : 'Searching for pages'}
          {!stopped && !finished && (
            <span className="loading-dots" aria-hidden="true">
              <span>.</span><span>.</span><span>.</span>
            </span>
          )}
        </h1>
        {stopped && <p>Start a new scan, or inspect any matches already found.</p>}
        {!stopped && <ol className="scan-steps">
          {steps.map((step) => {
            const state = step.at < stage || finished ? 'done' : 'active'
            return (
              <li key={step.at} data-state={state}>
                <span className="scan-step-mark" aria-hidden="true" />
                <span className="scan-step-text">
                  <span>{step.label}</span>
                  <small>{step.detail}</small>
                </span>
                <span className="visually-hidden">{state === 'done' ? 'Done' : 'In progress'}</span>
              </li>
            )
          })}
        </ol>}
        <details className="scan-details">
          <summary>Scan details · {elapsed}s</summary>
          <p className="muted">Animation only · results appear when the scan finishes.</p>
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
        </details>
      </div>
      {error && <ErrorBox error={error} retry={retry} />}
      {stopped && run.facecheck && <FaceSearchResults run={run} onResumed={() => {
        announced.current = null
        setFinished(false)
        retry()
      }} />}
      {cancelError && <ErrorBox error={cancelError} retry={() => void cancel()} />}
      {stopped ? (
        <div className="actions">
          <Button variant="default" onClick={onRetry}>
            Start a new scan
          </Button>
          {run.results.length > 0 && <Button variant="outline" onClick={onResults}>Open partial results</Button>}
        </div>
      ) : (
        <Button variant="outline" disabled={cancelling || finished} onClick={cancel}>
          {cancelling ? 'Cancelling…' : 'Cancel scan'}
        </Button>
      )}
    </section>
  )
}

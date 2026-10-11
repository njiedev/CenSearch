import { useEffect, useMemo, useState } from 'react'
import { Clock } from '../Hud'
import PhotoGrid from '../PhotoGrid'
import Logo from '../Logo'
import AuthorizeBatch from './AuthorizeBatch'
import BatchProgress from './BatchProgress'
import { STAGE_REASON, pathFor, withBatch } from './logic'
import MatchGrid from './MatchGrid'
import MatchZoom from './MatchZoom'
import { CASES, PLANS } from './mockData'
import type { Batch, Contact, ViewState } from './types'
import { TERMINAL } from './types'

type Section = 'matches' | 'authorize' | 'progress'

const TICK_MS = 700

const VIEW_STATES: { id: ViewState; label: string }[] = [
  { id: 'data', label: 'Data' },
  { id: 'loading', label: 'Loading' },
  { id: 'empty', label: 'Empty' },
  { id: 'error', label: 'Error' },
]

export default function MatchesApp() {
  const [section, setSection] = useState<Section>('matches')
  const [selected, setSelected] = useState<number[]>([])
  const [zoom, setZoom] = useState<{ id: number; origin: HTMLElement } | null>(null)
  const [batch, setBatch] = useState<Batch | null>(null)
  const [viewState, setViewState] = useState<ViewState>('data')
  const [contact, setContact] = useState<Contact | null>(null)
  const cases = useMemo(() => CASES.map((row) => withBatch(row, batch, contact)), [batch, contact])

  const running = batch?.status === 'running'

  // Mock batch: every tick, each item moves one step along its path. Items
  // start one tick apart, like a queue.
  useEffect(() => {
    if (!running) {
      return
    }
    let tick = 0
    const timer = window.setInterval(() => {
      tick++
      setBatch((current) => {
        if (!current) {
          return current
        }
        const items = current.items.map((item, index) => {
          const path = pathFor(item.case_id)
          const step = Math.min(tick - index, path.length) - 1
          if (step < 0) {
            return item
          }
          const status = path[step]
          const reason = TERMINAL.includes(status) ? PLANS[item.case_id].reason : STAGE_REASON[status] ?? ''
          return { ...item, status, reason }
        })
        const completed = items.filter((item) => TERMINAL.includes(item.status)).length
        return { ...current, items, completed, status: completed === items.length ? 'completed' : 'running' }
      })
    }, TICK_MS)
    return () => window.clearInterval(timer)
  }, [running])

  function go(next: Section) {
    setSection(next)
    window.scrollTo(0, 0)
  }

  function toggle(id: number) {
    setSelected((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]))
  }

  function open(id: number, origin: HTMLElement) {
    setZoom({ id, origin })
  }

  function run(contact: Contact) {
    setContact(contact)
    setBatch({
      id: 1,
      status: 'running',
      total: selected.length,
      completed: 0,
      items: selected.map((id) => ({ case_id: id, status: 'queued', reason: STAGE_REASON.queued! })),
    })
    setSelected([])
    go('progress')
  }

  function reset() {
    setSelected([])
    setBatch(null)
    setContact(null)
    setZoom(null)
    go('matches')
  }

  const nav: { id: Section; label: string; badge?: string }[] = [
    { id: 'matches', label: 'Matches', badge: String(viewState === 'data' ? cases.length : 0) },
    { id: 'authorize', label: 'Authorize', badge: selected.length ? String(selected.length) : undefined },
    { id: 'progress', label: 'Batch progress', badge: batch ? `${batch.completed}/${batch.total}` : undefined },
  ]

  return (
    <>
      <PhotoGrid />
      <div className="rec-blur" aria-hidden="true" />
      <div className="mx-shell">
        <aside className="mx-sidebar">
          <a className="mx-brand" href="/" aria-label="CenSearch home">
            <Logo />
          </a>

          <nav aria-label="Sections">
            <ul className="mx-nav">
              {nav.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="mx-nav-item"
                    aria-current={section === item.id ? 'page' : undefined}
                    onClick={() => go(item.id)}
                  >
                    <span>{item.label}</span>
                    {item.badge && <span className="mx-nav-badge">{item.badge}</span>}
                  </button>
                </li>
              ))}
            </ul>
            <p className="mx-nav-group">Coming next</p>
            <ul className="mx-nav">
              {['Scan', 'Follow-up'].map((label) => (
                <li key={label}>
                  <span className="mx-nav-item is-soon" aria-disabled="true">
                    <span>{label}</span>
                    <span className="mx-nav-badge">Soon</span>
                  </span>
                </li>
              ))}
            </ul>
          </nav>

          <div className="mx-mock">
            <p className="mx-nav-group">Mock controls</p>
            <div className="mx-segment" role="radiogroup" aria-label="Matches page state">
              {VIEW_STATES.map((state) => (
                <button
                  key={state.id}
                  type="button"
                  role="radio"
                  aria-checked={viewState === state.id}
                  onClick={() => setViewState(state.id)}
                >
                  {state.label}
                </button>
              ))}
            </div>
            <button type="button" className="mx-btn ghost small" onClick={reset}>
              Reset mock
            </button>
            <p className="mx-mock-note">Sample data, not connected to the backend.</p>
          </div>
        </aside>

        <div className="mx-main">
          <div className="mx-hud" aria-hidden="true">
            <span className="vf-rec">
              <span className="vf-rec-dot" />
              Surveillance in progress
            </span>
            <Clock />
          </div>

          {section === 'matches' && (
            <MatchGrid
              cases={cases}
              selected={selected}
              batch={batch}
              viewState={viewState}
              onToggle={toggle}
              onToggleAll={() => setSelected(selected.length === cases.length ? [] : cases.map((row) => row.id))}
              onOpen={open}
              onAuthorize={() => go('authorize')}
              onShowProgress={() => go('progress')}
            />
          )}
          {section === 'authorize' && (
            <AuthorizeBatch
              cases={cases.filter((row) => selected.includes(row.id))}
              onRun={run}
              onCancel={() => go('matches')}
            />
          )}
          {section === 'progress' && (
            <BatchProgress
              batch={batch}
              cases={cases}
              onOpen={open}
              onBack={() => go('matches')}
            />
          )}
        </div>
      </div>
      <MatchZoom
        item={zoom ? cases.find((row) => row.id === zoom.id) : undefined}
        origin={zoom?.origin ?? null}
        onClose={() => setZoom(null)}
      />
    </>
  )
}

import { actionOf, statusOf } from './logic'
import { StatusPill } from './Status'
import type { Batch, Case, ViewState } from './types'
import { hostname } from './types'


type Props = {
  embedded?: boolean
  cases: Case[]
  selected: number[]
  batch: Batch | null
  viewState: ViewState
  onToggle: (id: number) => void
  onToggleAll: () => void
  onOpen: (id: number, origin: HTMLElement) => void
  onAuthorize: () => void
  onShowProgress: () => void
}

function MatchCard({ item, checked, locked, onToggle, onOpen }: {
  item: Case
  checked: boolean
  locked: boolean
  onToggle: () => void
  onOpen: (origin: HTMLElement) => void
}) {
  const action = actionOf(item)
  return (
    <article className={`mx-card${checked ? ' is-selected' : ''}${item.whitelisted ? ' is-whitelisted' : ''}`}>
      <button
        type="button"
        className="mx-card-open"
        onClick={(event) => onOpen(event.currentTarget)}
        aria-label={`Open match ${item.id}: ${hostname(item.page_url)}`}
      >
        <img src={item.matched_image_url} alt="" />
        <span className="mx-site">{hostname(item.page_url)}</span>
        <span className="mx-action">
          {action.possible && <span className="mx-possible">Possible: </span>}
          {action.label}
        </span>
        {item.whitelisted ? <span className="mx-status tone-neutral">– Whitelisted</span> : <StatusPill status={statusOf(item)} />}
      </button>
      {/* Overlaid on the image corners, outside the open button. */}
      <label className="mx-check" title={`Select match ${item.id}`}>
        <input type="checkbox" checked={checked} disabled={locked} onChange={onToggle} />
        <span className="visually-hidden">Select match {item.id}</span>
      </label>
      <span className={`mx-band band-${item.band}`}>{item.band === 'possible' ? 'Possible' : 'Match'}</span>
    </article>
  )
}

function Skeletons() {
  return (
    <div className="mx-grid" aria-busy="true" aria-label="Loading matches">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="mx-card mx-skeleton">
          <div className="sk sk-line" />
          <div className="sk sk-image" />
          <div className="sk sk-line" />
          <div className="sk sk-line short" />
        </div>
      ))}
    </div>
  )
}

export default function MatchGrid(props: Props) {
  const { cases, selected, batch, viewState } = props
  const running = batch?.status === 'running' || batch?.status === 'queued'
  const allSelected = cases.length > 0 && selected.length === cases.length
  const showData = viewState === 'data'

  return (
    <section className="mx-view" aria-labelledby="mx-matches-title">
      {!props.embedded && <header className="mx-header">
        <div>
          <h1 id="mx-matches-title">
            Matches <span className="mx-count">({showData ? cases.length : 0})</span>
          </h1>
          <p className="mx-sub">Everywhere we found your face. Click one to see the details.</p>
        </div>
        <div className="mx-toolbar">
          <button
            type="button"
            className="mx-btn ghost"
            disabled={!showData || running}
            onClick={props.onToggleAll}
          >
            {allSelected ? 'Clear selection' : 'Select all'}
          </button>
          <span className="mx-selected" aria-live="polite">
            {selected.length} selected
          </span>
          <button
            type="button"
            className="mx-btn primary"
            disabled={!showData || selected.length === 0 || running}
            onClick={props.onAuthorize}
          >
            Auto review / send
          </button>
        </div>
      </header>}

      {batch && showData && (
        <div className="mx-banner" role="status">
          <span>
            {running ? 'Batch running' : 'Batch finished'}: {batch.completed} of {batch.total} done.
          </span>
          <button type="button" className="mx-link" onClick={props.onShowProgress}>
            View progress
          </button>
        </div>
      )}

      {viewState === 'loading' && <Skeletons />}

      {viewState === 'error' && (
        <div className="mx-alert" role="alert">
          <strong>Couldn’t load your matches.</strong>
          <span>The CenSearch server didn’t answer. Check it’s running, then try again.</span>
          <button type="button" className="mx-btn ghost">
            Try again
          </button>
        </div>
      )}

      {viewState === 'empty' && (
        <div className="mx-empty">
          <h2>No matches yet</h2>
          <p>Run a scan and anything we find will show up here.</p>
          <button type="button" className="mx-btn primary">
            Start a scan
          </button>
        </div>
      )}

      {showData && (
        <div className="mx-grid">
          {cases.map((item) => (
            <MatchCard
              key={item.id}
              item={item}
              checked={selected.includes(item.id)}
              locked={Boolean(running || item.whitelisted)}
              onToggle={() => props.onToggle(item.id)}
              onOpen={(origin) => props.onOpen(item.id, origin)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

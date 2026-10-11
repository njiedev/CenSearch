import { useId } from 'react'
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
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
  const checkboxId = useId()
  const action = actionOf(item)
  const status = statusOf(item)
  const showAction = item.whitelisted || action.route !== 'leave_alone' || status !== 'left_alone'
  return (
    <Card role="article" className={`mx-card gap-0 p-0${checked ? ' is-selected' : ''}${item.whitelisted ? ' is-whitelisted' : ''}`}>
      <Button variant="outline"
        type="button"
        className="mx-card-open grid h-auto w-full gap-1.5 whitespace-normal p-2 pb-3 text-left"
        onClick={(event) => onOpen(event.currentTarget)}
        aria-label={`Open match ${item.id}: ${hostname(item.page_url)}`}
      >
        {item.thumbnail_available === false
          ? <span className="mx-thumbnail-missing">Thumbnail unavailable</span>
          : <img src={item.matched_image_url} alt="Candidate image" />}
        <span className="mx-site">{hostname(item.page_url)}</span>
        {item.match_type === 'facecheck' && <span className="mx-muted">
          FaceCheck · Score {item.provider_score} · Not locally verified
        </span>}
        {showAction && <span className="mx-action">
          {action.possible && <span className="mx-possible">Possible: </span>}
          {action.label}
        </span>}
        {item.whitelisted ? <span className="mx-status tone-neutral">– Whitelisted</span> : <StatusPill status={status} />}
      </Button>
      {/* Overlaid on the image corners, outside the open button. */}
      <Label className="mx-check" htmlFor={checkboxId} title={`Select match ${item.id}`}>
        <Checkbox
          id={checkboxId}
          className="size-6 border-white/60 bg-background shadow-sm enabled:hover:border-white enabled:active:brightness-90"
          checked={checked}
          disabled={locked}
          onCheckedChange={onToggle}
        />
        <span className="visually-hidden">Select match {item.id}</span>
      </Label>
      <span className={`mx-band band-${item.band}`}>{item.band === 'possible' ? 'Possible' : 'Match'}</span>
    </Card>
  )
}

function Skeletons() {
  return (
    <div className="mx-grid" aria-busy="true" aria-label="Loading matches">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="mx-card mx-skeleton">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
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
          <Button
            type="button"
            variant="outline"
            disabled={!showData || running}
            onClick={props.onToggleAll}
          >
            {allSelected ? 'Clear selection' : 'Select all'}
          </Button>
          <span className="mx-selected" aria-live="polite">
            {selected.length} selected
          </span>
          <Button
            type="button"
            variant="default"
            disabled={!showData || selected.length === 0 || running}
            onClick={props.onAuthorize}
          >
            Auto review / send
          </Button>
        </div>
      </header>}

      {batch && showData && (
        <div className="mx-banner" role="status">
          <span>
            {running ? 'Batch running' : 'Batch finished'}: {batch.completed} of {batch.total} done.
          </span>
          <Button variant="outline" type="button" className="mx-link" onClick={props.onShowProgress}>
            View progress
          </Button>
        </div>
      )}

      {viewState === 'loading' && <Skeletons />}

      {viewState === 'error' && (
        <div className="mx-alert" role="alert">
          <strong>Couldn’t load your matches.</strong>
          <span>The CenSearch server didn’t answer. Check it’s running, then try again.</span>
          <Button type="button" variant="outline">
            Try again
          </Button>
        </div>
      )}

      {viewState === 'empty' && (
        <div className="mx-empty">
          <h2>No matches yet</h2>
          <p>Run a scan and anything we find will show up here.</p>
          <Button type="button" variant="default">
            Start a scan
          </Button>
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

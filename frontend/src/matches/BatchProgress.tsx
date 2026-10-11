import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { reachedStep } from './logic'
import { StatusPill } from './Status'
import type { Batch, Case, ItemStatus } from './types'
import { TERMINAL, hostname } from './types'

const STEPS: { status: ItemStatus; label: string }[] = [
  { status: 'reviewing', label: 'Review' },
  { status: 'capturing', label: 'Evidence' },
  { status: 'researching', label: 'Recipient' },
  { status: 'drafting', label: 'Draft' },
  { status: 'sending', label: 'Send' },
]
const ORDER: ItemStatus[] = ['queued', 'reviewing', 'capturing', 'researching', 'drafting', 'sending']

// Which steps an item has passed, given the furthest step it reached.
function stepState(item: { status: ItemStatus; reached: ItemStatus }, step: ItemStatus) {
  const reached = ORDER.indexOf(item.reached)
  const index = ORDER.indexOf(step)
  if (index < reached || (index === reached && TERMINAL.includes(item.status))) {
    return 'done'
  }
  if (index === reached) {
    return 'current'
  }
  return 'todo'
}

type Props = {
  batch: Batch | null
  cases: Case[]
  onOpen: (id: number, origin: HTMLElement) => void
  onBack: () => void
}

export default function BatchProgress({ batch, cases, onOpen, onBack }: Props) {
  if (!batch) {
    return (
      <section className="mx-view">
        <div className="mx-empty">
          <h2>No batch yet</h2>
          <p>Select matches and run Auto review / send. You’ll watch each one here.</p>
          <Button type="button" variant="default" onClick={onBack}>
            Go to matches
          </Button>
        </div>
      </section>
    )
  }

  const percent = batch.total ? Math.round((batch.completed / batch.total) * 100) : 0
  const done = batch.status === 'completed'

  return (
    <section className="mx-view" aria-labelledby="mx-progress-title">
      <header className="mx-header">
        <div>
          <h1 id="mx-progress-title">{done ? 'Batch finished' : 'Batch running'}</h1>
          <p className="mx-sub">
            {done
              ? 'Every match has a result. Open one to see exactly what was sent.'
              : 'The agent is working through each match. You can leave this page; it keeps going.'}
          </p>
        </div>
      </header>

      <Card className="gap-4 p-6">
        <div className="mx-progress-head" aria-live="polite">
          <span>
            {batch.completed} of {batch.total} done
          </span>
          <span className="mx-mono">{percent}%</span>
        </div>
        <Progress value={percent} aria-label="Batch progress" className="mt-3" />
      </Card>

      <ol className="mx-items">
        {batch.items.map((item) => {
          const match = cases.find((row) => row.id === item.case_id)
          const finished = TERMINAL.includes(item.status)
          const reached = batch.mode
            ? item.status === 'ready_to_send' ? 'drafting' : item.status === 'sent' ? 'sending' : item.status
            : reachedStep(item.case_id, item.status)
          return (
            <li key={item.case_id} className="mx-item">
              {match && (match.thumbnail_available === false
                ? <span className="mx-muted">Thumbnail unavailable</span>
                : <img src={match.matched_image_url} alt="Candidate image" />)}
              <div className="mx-item-main">
                <div className="mx-item-head">
                  <span className="mx-mono">Match {item.case_id}</span>
                  {match && <span>{hostname(match.page_url)}</span>}
                  <StatusPill status={item.status} />
                </div>
                <ol className="mx-steps" aria-label="Steps">
                  {STEPS.map((step) => {
                    const state = stepState(
                      { status: item.status, reached },
                      step.status,
                    )
                    return (
                      <li key={step.status} className={`mx-step ${state}`}>
                        <span aria-hidden="true">{state === 'done' ? '✓' : state === 'current' ? '●' : '○'}</span>
                        {step.label}
                        <span className="visually-hidden">
                          {state === 'done' ? ' done' : state === 'current' ? ' in progress' : ' not started'}
                        </span>
                      </li>
                    )
                  })}
                </ol>
                <p className="mx-reason">{item.reason}</p>
              </div>
              {finished && (
                <Button variant="outline" type="button" className="mx-btn ghost small" onClick={(event) => onOpen(item.case_id, event.currentTarget)}>
                  Open
                </Button>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

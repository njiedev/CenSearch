import { useState } from 'react'
import { actionOf, statusOf } from './logic'
import { StatusPill } from './Status'
import type { Case } from './types'
import { hostname, isManual } from './types'

const CHANNELS = {
  email: 'Email',
  web_form: 'Web form',
  manual_email: 'Email, sent by you',
  manual_web: 'Web form, sent by you',
}

export default function MatchDetail({ item, onBack }: { item: Case | undefined; onBack: () => void }) {
  const [copied, setCopied] = useState(false)

  if (!item) {
    return (
      <section className="mx-view">
        <div className="mx-empty">
          <h2>No match open</h2>
          <p>Open a match from the grid to see its details.</p>
          <button type="button" className="mx-btn primary" onClick={onBack}>
            Go to matches
          </button>
        </div>
      </section>
    )
  }

  const action = actionOf(item)
  const notice = item.drafted_request
  const sent = notice ? item.deliveries.some((row) => row.notice_id === notice.id) : false

  async function copy() {
    if (!notice) {
      return
    }
    await navigator.clipboard.writeText(notice.payload.body)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section className="mx-view" aria-labelledby="mx-detail-title">
      <button type="button" className="mx-link mx-back" onClick={onBack}>
        ← All matches
      </button>
      <div className="mx-detail">
        <figure className="mx-detail-image">
          <img src={item.matched_image_url} alt={`Full matched image for match ${item.id}`} />
        </figure>

        <div className="mx-detail-body">
          <div>
            <p className="mx-eyebrow">Match {item.id} · {item.band === 'possible' ? 'Possible match' : 'Match'}</p>
            <h1 id="mx-detail-title">{hostname(item.page_url)}</h1>
            <a className="mx-link" href={item.page_url} target="_blank" rel="noreferrer">
              Open source page ↗
            </a>
          </div>

          <div className="mx-panel">
            <h2>{action.possible ? 'Suggested action' : 'Action taken'}</h2>
            <p className="mx-action-lg">
              {action.possible && <span className="mx-possible">Possible: </span>}
              {action.label}
            </p>
            <p>{action.reason}</p>
            <p className="mx-muted">
              Picked by {action.source === 'agent' ? 'the agent' : 'rule fallback'}
              {action.model_status === 'model_not_configured' && ' (no AI model set up yet)'}
            </p>
          </div>

          {item.batch_outcome && (
            <div className="mx-panel">
              <h2>Outcome</h2>
              <StatusPill status={statusOf(item)} />
              <p>{item.batch_outcome.reason}</p>
            </div>
          )}

          {notice && (
            <div className="mx-panel">
              <h2>Recipient</h2>
              <p className="mx-mono">{notice.recipient.address}</p>
              <p className="mx-muted">
                {CHANNELS[notice.recipient.channel]} · <span className="mx-mono">{notice.recipient.endpoint}</span>
              </p>
              {isManual(notice.recipient) && (
                <p className="mx-callout">
                  This is a real website, so we don’t send it for you. Copy the notice below and send it to the
                  recipient yourself.
                </p>
              )}
            </div>
          )}

          {notice && (
            <div className="mx-panel">
              <div className="mx-panel-head">
                <h2>{sent ? 'Sent notice' : 'Drafted notice'}</h2>
                <button type="button" className="mx-btn ghost small" onClick={copy}>
                  {copied ? 'Copied ✓' : 'Copy notice'}
                </button>
              </div>
              <pre className="mx-notice">{notice.payload.body}</pre>
            </div>
          )}

          {!item.batch_outcome && (
            <p className="mx-muted">
              Nothing has been sent for this match. Select it in the grid and run Auto review / send.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

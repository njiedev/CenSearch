import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { actionOf, statusOf } from './logic'
import { StatusPill } from './Status'
import type { Case } from './types'
import { hostname, isManual } from './types'

const CHANNELS = {
  smtp: 'Email to test site',
  http_form: 'Form on test site',
  email: 'Email',
  web_form: 'Web form',
  manual_email: 'Email, sent by you',
  manual_web: 'Web form, sent by you',
}

type Props = {
  item: Case | undefined
  // The element the zoom grows out of, usually the clicked card.
  origin: HTMLElement | null
  onWhitelist?: (item: Case) => void
  whitelistBusy?: boolean
  whitelistError?: string
  followUp?: ReactNode
  onClose: () => void
}

export default function MatchZoom({ item, origin, onClose, onWhitelist, whitelistBusy, whitelistError, followUp }: Props) {
  const [copied, setCopied] = useState(false)
  const returnFocus = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (origin) returnFocus.current = origin
  }, [origin])

  async function copy(text: string) {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const action = item ? actionOf(item) : null
  const notice = item?.drafted_request ?? null
  const sent = notice && item ? item.batch_outcome?.status === 'sent' : false

  return (
    <Dialog open={Boolean(item)} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="app-shell max-h-[90svh] overflow-y-auto p-0 sm:max-w-4xl" aria-describedby={undefined}
        onCloseAutoFocus={(event) => { event.preventDefault(); returnFocus.current?.focus() }}>
      {item && action && (
        <div className="mx-zoom-panel">
          <figure className="mx-zoom-image">
            {item.thumbnail_available === false
              ? <p className="mx-thumbnail-missing">Thumbnail unavailable for this saved candidate.</p>
              : <img src={item.matched_image_url} alt={`Candidate image for match ${item.id}`} />}
          </figure>

          <div className="mx-zoom-body">
            <div className="mx-zoom-head">
              <div>
                <p className="mx-eyebrow">
                  Match {item.id} · {item.band === 'possible' ? 'Possible match' : 'Match'}
                </p>
                <DialogTitle>{hostname(item.page_url)}</DialogTitle>
                <a className="mx-link" href={item.page_url} target="_blank" rel="noreferrer">
                  Open source page ↗
                </a>
              </div>
            </div>

            <section className="mx-zoom-section">
              {item.match_type === 'facecheck' && <p className="mx-callout">
                Found by FaceCheck · Score {item.provider_score}. The agent reviews the page
                context to recommend an action. A face match alone does not establish photo ownership
                or misuse.
              </p>}
              {onWhitelist && <Button variant="outline"  disabled={whitelistBusy} onClick={() => onWhitelist(item)}>{item.whitelisted ? 'Remove from whitelist' : 'Add site to whitelist'}</Button>}
              {whitelistError && <p role="alert" className="field-error">{whitelistError}</p>}
              <h3>{action.possible ? 'Suggested action' : 'Action taken'}</h3>
              <p className="mx-action-lg">
                {action.possible && <span className="mx-possible">Possible: </span>}
                {action.label}
              </p>
              <p>{action.reason}</p>
              <p className="mx-muted">
                Picked by {action.source === 'agent' ? 'the agent' : 'rule fallback'}
                {action.model_status === 'model_not_configured' && ' (no AI model set up yet)'}
              </p>
            </section>

            <section className="mx-zoom-section">
              <h3>Outcome</h3>
              <StatusPill status={statusOf(item)} />
              <p>
                {item.batch_outcome?.reason ??
                  'Nothing has been sent for this match. Select it in the grid and run Auto review / send.'}
              </p>
            </section>

            {notice && (
              <section className="mx-zoom-section">
                <h3>Recipient</h3>
                <p className="mx-mono">{notice.recipient.address}</p>
                <p className="mx-muted">
                  {CHANNELS[notice.recipient.channel]} · <span className="mx-mono">{notice.recipient.endpoint}</span>
                </p>
                {isManual(notice.recipient) && (
                  <p className="mx-callout">
                    Check the recorded outcome for this request. If it remains unsent, you can copy the notice
                    and submit it yourself.
                  </p>
                )}
              </section>
            )}

            {notice && (
              <section className="mx-zoom-section">
                <div className="mx-section-head">
                  <h3>{sent ? 'Sent notice' : 'Drafted notice'}</h3>
                  <Button variant="outline" type="button" size="sm" onClick={() => copy(notice.payload.body)}>
                    {copied ? 'Copied ✓' : 'Copy notice'}
                  </Button>
                </div>
                <pre className="mx-notice">{notice.payload.body}</pre>
              </section>
            )}
            {followUp}
          </div>
        </div>
      )}
      </DialogContent>
    </Dialog>
  )
}

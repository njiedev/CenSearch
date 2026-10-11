import { useEffect, useLayoutEffect, useRef, useState } from 'react'
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
  onClose: () => void
}

// The match, zoomed in over a blurred page: image on the left, everything we
// know about it on the right. A native <dialog> gives focus trapping, Esc to
// close and a ::backdrop to blur.
export default function MatchZoom({ item, origin, onClose, onWhitelist, whitelistBusy, whitelistError }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = useState(false)

  useLayoutEffect(() => {
    const dialog = dialogRef.current!
    if (!item) {
      if (dialog.open) {
        dialog.close()
      }
      return
    }
    if (!dialog.open) {
      dialog.showModal()
    }
    // Grow from the card: start at its size and spot, end at the centre.
    const panel = panelRef.current!
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!origin || still) {
      return
    }
    const from = origin.getBoundingClientRect()
    const to = panel.getBoundingClientRect()
    const dx = from.left + from.width / 2 - (to.left + to.width / 2)
    const dy = from.top + from.height / 2 - (to.top + to.height / 2)
    const scale = Math.max(from.width / to.width, 0.2)
    panel.animate(
      [
        { transform: `translate(${dx}px, ${dy}px) scale(${scale})`, opacity: 0.4 },
        { transform: 'none', opacity: 1 },
      ],
      { duration: 280, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)' },
    )
  }, [item, origin])

  // Hand focus back to the card that opened the zoom.
  useEffect(() => {
    const dialog = dialogRef.current!
    function restore() {
      origin?.focus()
    }
    dialog.addEventListener('close', restore)
    return () => dialog.removeEventListener('close', restore)
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
    <dialog
      ref={dialogRef}
      className="mx-zoom"
      aria-labelledby="mx-zoom-title"
      onClose={onClose}
      onClick={(event) => {
        // A click on the blurred backdrop (the dialog itself) closes it.
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      {item && action && (
        <div className="mx-zoom-panel" ref={panelRef}>
          <figure className="mx-zoom-image">
            <img src={item.matched_image_url} alt={`Matched image for match ${item.id}`} />
          </figure>

          <div className="mx-zoom-body">
            <div className="mx-zoom-head">
              <div>
                <p className="mx-eyebrow">
                  Match {item.id} · {item.band === 'possible' ? 'Possible match' : 'Match'}
                </p>
                <h2 id="mx-zoom-title">{hostname(item.page_url)}</h2>
                <a className="mx-link" href={item.page_url} target="_blank" rel="noreferrer">
                  Open source page ↗
                </a>
              </div>
              <button type="button" className="mx-close" onClick={onClose} aria-label="Close">
                ✕
              </button>
            </div>

            <section className="mx-zoom-section">
              {onWhitelist && <button className="mx-btn ghost" disabled={whitelistBusy} onClick={() => onWhitelist(item)}>{item.whitelisted ? 'Remove from whitelist' : 'Add site to whitelist'}</button>}
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
                    This is a real website, so we don’t send it for you. Copy the notice and send it to the recipient
                    yourself.
                  </p>
                )}
              </section>
            )}

            {notice && (
              <section className="mx-zoom-section">
                <div className="mx-section-head">
                  <h3>{sent ? 'Sent notice' : 'Drafted notice'}</h3>
                  <button type="button" className="mx-btn ghost small" onClick={() => copy(notice.payload.body)}>
                    {copied ? 'Copied ✓' : 'Copy notice'}
                  </button>
                </div>
                <pre className="mx-notice">{notice.payload.body}</pre>
              </section>
            )}
          </div>
        </div>
      )}
    </dialog>
  )
}

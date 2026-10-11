import { Card } from "@/components/ui/card"
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useState } from 'react'
import BatchProgress from '../matches/BatchProgress'
import MatchZoom from '../matches/MatchZoom'
import { StatusPill } from '../matches/Status'
import { actionOf } from '../matches/logic'
import { hostname } from '../matches/types'
import { api } from './api'
import { ErrorBox, Loading } from './ui'
import { usePoll } from './hooks'
import type { Case } from './types'

const groups = [
  ['ready_to_send', 'Ready to send'],
  ['drafted_not_sent', 'Drafted for you to send yourself'],
  ['left_alone', 'Left alone'],
  ['held_for_review', 'Held for review'],
  ['failed', 'Failed'],
  ['sent', 'Sent'],
] as const
function Evidence({ value }: { value: unknown }) {
  if (value === undefined || value === null)
    return <p className="muted">No recipient evidence was returned.</p>
  return <p className="evidence-text">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</p>
}
function NoticeItem({
  row,
  decision,
  reason,
}: {
  row: Case
  decision?: Case['possible_action']
  reason: string
}) {
  const [copyStatus, setCopyStatus] = useState('')
  const action = decision ?? actionOf(row)
  const notice = row.drafted_request
  const recipient = notice?.recipient
  const evidence =
    recipient?.evidence ??
    row.recipients?.find((candidate) => candidate.address === recipient?.address)?.evidence
  async function copy() {
    try {
      await navigator.clipboard.writeText(notice!.payload.body)
      setCopyStatus('Copied')
      setTimeout(() => setCopyStatus(''), 2500)
    } catch {
      setCopyStatus('Could not copy. Select and copy the notice text below.')
    }
  }
  return (
    <div className="review-details">
      <section>
        <h3>Decision</h3>
        <p>
          <strong>{action.label}</strong>
        </p>
        <p>{action.reason}</p>
        <p className="source-label">
          {action.source === 'agent' ? 'Source: agent' : 'Source: rule-based fallback'}
        </p>
        <p>{reason}</p>
      </section>
      <section>
        <h3>Recipient</h3>
        {recipient ? (
          <>
            <p className="recipient-address">{recipient.address}</p>
            <p>Channel: {recipient.channel.replaceAll('_', ' ')}</p>
            <p>
              {recipient.channel === 'email' || recipient.channel === 'manual_email'
                ? 'Delivery destination: website email contact'
                : recipient.channel === 'smtp' ||
              recipient.channel === 'http_form' ||
              recipient.endpoint.includes('127.0.0.1')
                ? 'Delivery destination: test site'
                : 'Delivery destination: manual submission'}
            </p>
            <h4>Evidence for this recipient</h4>
            <Evidence value={evidence} />
          </>
        ) : (
          <p>No recipient selected.</p>
        )}
      </section>
      <section>
        <h3>Exact notice text</h3>
        {notice ? (
          <>
            <pre className="mx-notice">{notice.payload.body}</pre>
            <Button variant="outline" onClick={copy}>Copy notice</Button>
            <span role="status">{copyStatus}</span>
          </>
        ) : (
          <p>No notice was drafted.</p>
        )}
      </section>
    </div>
  )
}
export default function BatchReview({
  id,
  personId,
  runId,
  onBack,
  onUpdated,
}: {
  id: string
  personId: string
  runId: number
  onBack: () => void
  onUpdated: () => void
}) {
  const [zoom, setZoom] = useState<{ id: number; origin: HTMLElement } | null>(null)
  const [stopped, setStopped] = useState(false)
  const result = usePoll(
    async () => {
      const batch = await api.batch(id)
      setStopped(batch.phase === 'awaiting_review' || batch.phase === 'done')
      const cases = await api.cases(personId, runId)
      return { batch, cases }
    },
    [id, personId, runId],
    stopped ? 0 : 1000,
  )
  const [excluded, setExcluded] = useState<number[]>([])
  const [confirm, setConfirm] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const batch = result.value?.batch
  const cases = result.value?.cases ?? []
  const ready =
    batch?.items.filter(
      (item) =>
        item.status === 'ready_to_send' &&
        !excluded.includes(item.case_id) &&
        !cases.find((row) => row.id === item.case_id)?.whitelisted,
    ) ?? []
  async function send() {
    setSending(true)
    setError('')
    try {
      await api.send(
        id,
        ready.map((item) => item.case_id),
      )
      setConfirm(false)
      setStopped(false)
      result.retry()
      onUpdated()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setSending(false)
    }
  }
  if (!batch) return result.error ? <ErrorBox error={result.error} retry={result.retry} /> : <Loading />
  const working = batch.phase === 'preparing' || batch.phase === 'sending'
  if (working)
    return (
      <>
        <BatchProgress
          batch={batch}
          cases={cases}
          onOpen={(caseId, origin) => setZoom({ id: caseId, origin })}
          onBack={onBack}
        />
        <MatchZoom
          item={cases.find((row) => row.id === zoom?.id)}
          origin={zoom?.origin ?? null}
          onClose={() => setZoom(null)}
        />
        <p className="muted">You can return to the scan while the batch continues.</p>
        <Button variant="outline" onClick={onBack}>Back to scan</Button>
        {result.error && <ErrorBox error={result.error} retry={result.retry} />}
      </>
    )
  const done = batch.phase === 'done'
  const count = (status: string) => batch.items.filter((item) => item.status === status).length
  return (
    <section>
      <header className="page-head">
        <h1>{done ? 'Batch complete' : 'Review every request'}</h1>
        <p>
          {done
            ? 'These are the recorded outcomes for this batch.'
            : 'Read each decision, recipient and exact notice before confirming delivery.'}
        </p>
        {done && (
          <div className="summary" role="status">
            <span>
              <strong>{count('sent')}</strong>sent
            </span>
            <span>
              <strong>{count('drafted_not_sent')}</strong>drafted, not sent
            </span>
            <span>
              <strong>{count('failed')}</strong>failed
            </span>
          </div>
        )}
      </header>
      {(result.error || error) && <ErrorBox error={error || result.error} retry={result.retry} />}
      {groups.map(([status, label]) => {
        const items = batch.items.filter((item) => item.status === status)
        if (!items.length) return null
        return (
          <section className="review-group" key={status}>
            <h2>
              {label} ({items.length})
            </h2>
            {status === 'drafted_not_sent' && (
              <p>
                These requests were not sent. Open each request to see why and copy the notice if needed.
              </p>
            )}
            {items.map((item) => {
              const row = cases.find((candidate) => candidate.id === item.case_id)
              return (
                <Card className="review-item gap-0 py-0" key={item.case_id}>
                  {status === 'ready_to_send' && (
                    <Label className="check-row">
                      <Checkbox

                        checked={!excluded.includes(item.case_id) && !row?.whitelisted}
                        disabled={row?.whitelisted || sending}
                        onCheckedChange={(checked) =>
                          setExcluded(
                            checked === true
                              ? excluded.filter((value) => value !== item.case_id)
                              : [...excluded, item.case_id],
                          )
                        }
                      />
                      Include request {item.case_id}
                      {row?.whitelisted && ' · Whitelisted; cannot send'}
                    </Label>
                  )}
                  <Accordion type="single" collapsible><AccordionItem value="notice" className="border-0">
                    <AccordionTrigger className="px-4">
                      <span>{row ? hostname(row.page_url) : `Match ${item.case_id}`}</span>
                      <StatusPill status={item.status} />
                      <span>Read request ↓</span>
                    </AccordionTrigger><AccordionContent className="px-0">
                    {row ? (
                      <NoticeItem row={row} decision={item.decision} reason={item.reason} />
                    ) : (
                      <p>Case details are unavailable. Refresh before sending.</p>
                    )}
                  </AccordionContent></AccordionItem></Accordion>
                </Card>
              )
            })}
          </section>
        )
      })}
      <footer className="sticky-actions review-footer">
        {done ? (
          <Button
            variant="default"
            onClick={() => {
              onUpdated()
              onBack()
            }}
          >
            Back to scan
          </Button>
        ) : (
          <>
            <Button variant="outline" onClick={onBack}>Back to scan</Button>
            <Button
              variant="default"
              disabled={
                !ready.length ||
                sending ||
                !!result.error ||
                ready.some((item) => !cases.find((row) => row.id === item.case_id)?.drafted_request)
              }
              onClick={() => setConfirm(true)}
            >
              Send {ready.length} requests
            </Button>
            {!ready.length && <p>No requests selected. Select a ready request to send it.</p>}
            {confirm && (
              <div className="confirmation" role="region" aria-label="Confirm sending">
                <h2>Send {ready.length} requests?</h2>
                <p>
                  {ready.length} removal requests will be sent to these recipients. This cannot be undone.
                </p>
                <ul>
                  {ready.map((item) => (
                    <li key={item.case_id}>
                      {cases.find((row) => row.id === item.case_id)?.drafted_request?.recipient.address}
                    </li>
                  ))}
                </ul>
                <div className="actions">
                  <Button variant="default" disabled={sending} onClick={send}>
                    {sending ? 'Sending…' : `Send ${ready.length} requests`}
                  </Button>
                  <Button variant="outline" disabled={sending} onClick={() => setConfirm(false)}>
                    Go back
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </footer>
    </section>
  )
}

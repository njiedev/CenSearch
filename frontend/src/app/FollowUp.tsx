import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { api } from './api'
import { date, usePoll } from './hooks'
import { ErrorBox, Loading } from './ui'

const readable = (value: string) => value.replaceAll('_', ' ')

export default function FollowUp({ caseId }: { caseId: number }) {
  const result = usePoll(() => api.workflow(caseId), [caseId], 0)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [approvedBy, setApprovedBy] = useState('')
  const [recipientId, setRecipientId] = useState('')
  const [accepted, setAccepted] = useState(false)
  const workflow = result.value
  async function act(label: string, operation: () => Promise<unknown>) {
    setBusy(label)
    setError('')
    try {
      await operation()
      setAccepted(false)
      result.retry()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy('')
    }
  }
  if (!workflow) return result.error ? <ErrorBox error={result.error} retry={result.retry} /> : <Loading />
  const lastCheck = workflow.checks.at(-1)
  const lastNotice = workflow.notices.at(-1)
  const latestDelivery = workflow.deliveries.at(-1)
  const recipients = workflow.lookup?.recipients?.filter((row) => row.rung === workflow.next_rung) ?? []
  const selectedRecipient = recipientId || recipients[0]?.id
  const needsEscalation = workflow.state === 'escalation_approval_required'
  const escalationDraft = lastNotice && lastNotice.rung !== 'site' &&
    !workflow.deliveries.some((delivery) => delivery.notice_id === lastNotice.id)
  const canSend = escalationDraft && ['email', 'manual_email', 'smtp', 'http_form'].includes(lastNotice.recipient.channel)
  return (
    <section className="mx-zoom-section grid gap-3" aria-label="Verification and follow-up">
      <h3>Verification and follow-up</h3>
      <Badge variant="outline" className="whitespace-normal">{readable(workflow.state)}</Badge>
      {lastCheck ? (
        <p role="status">Last check: {readable(lastCheck.outcome)} · {date(lastCheck.checked_at)}</p>
      ) : <p>No removal check yet.</p>}
      {latestDelivery && <p>Latest delivery: {latestDelivery.rung} · {readable(latestDelivery.status)}</p>}
      {latestDelivery?.response?.provider_id && (
        <p className="break-all">Resend email ID: {latestDelivery.response.provider_id}</p>
      )}
      {latestDelivery?.status === 'awaiting_response' && (
        <p>Follow-up due: {date(latestDelivery.deadline)}. A reasoned refusal requires your review.</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={Boolean(busy)} onClick={() => act('Checking page…', () => api.verify(caseId))}>
          Check removal now
        </Button>
        {workflow.demo_clock && workflow.deliveries.length > 0 && (
          <Button variant="outline" disabled={Boolean(busy)} onClick={() => act('Checking overdue requests…', api.advanceClock)}>
            Advance demo clock by 2 days
          </Button>
        )}
      </div>
      {workflow.demo_clock && <p className="text-xs">Demo clock changes the deadline for all requests in this local demo.</p>}
      {needsEscalation && (
        <div className="grid gap-3 rounded-md border p-3">
          <h4>Follow up with the {workflow.next_rung === 'search' ? 'search engine' : workflow.next_rung}</h4>
          <p>The image is still present after the response deadline. Review a new request before sending.</p>
          <Label>Your name for this approval<Input value={approvedBy} onChange={(event) => setApprovedBy(event.target.value)} /></Label>
          {recipients.length ? (
            <Label>Recipient<NativeSelect value={selectedRecipient} onChange={(event) => setRecipientId(event.target.value)}>
              {recipients.map((row) => <NativeSelectOption key={row.id} value={row.id}>{row.address}</NativeSelectOption>)}
            </NativeSelect></Label>
          ) : <Button variant="outline" disabled={Boolean(busy)} onClick={() => act('Finding recipients…', () => api.recipients(caseId))}>Find follow-up recipients</Button>}
          <Button disabled={Boolean(busy) || !approvedBy.trim() || !selectedRecipient} onClick={() => act('Preparing follow-up…', async () => {
            await api.approveDraft(caseId, workflow.revision, workflow.next_rung, approvedBy.trim())
            await api.draft(caseId, selectedRecipient!, workflow.next_rung)
          })}>Prepare follow-up request</Button>
        </div>
      )}
      {escalationDraft && (
        <div className="grid gap-3 rounded-md border p-3">
          <h4>Follow-up request · {lastNotice.rung}</h4>
          <p>Recipient: {lastNotice.recipient.address}</p>
          <pre className="mx-notice">{lastNotice.payload.body}</pre>
          {canSend ? <>
            <Label>Your name for this approval<Input value={approvedBy} onChange={(event) => setApprovedBy(event.target.value)} /></Label>
            <Label className="flex items-start gap-3 whitespace-normal">
              <Checkbox checked={accepted} onCheckedChange={(value) => setAccepted(value === true)} />
              I reviewed this exact follow-up request and recipient, accept legal responsibility, and authorize delivery.
            </Label>
            <Button disabled={Boolean(busy) || !accepted || !approvedBy.trim()} onClick={() => act('Sending follow-up…', async () => {
              await api.approveNotice(caseId, lastNotice, approvedBy.trim())
              await api.sendNotice(caseId)
            })}>Send approved follow-up</Button>
          </> : <p>This recipient requires manual submission. Copy the request and send it yourself.</p>}
        </div>
      )}
      {busy && <p role="status">{busy}</p>}
      {(error || result.error) && <ErrorBox error={error || result.error} retry={result.retry} />}
    </section>
  )
}

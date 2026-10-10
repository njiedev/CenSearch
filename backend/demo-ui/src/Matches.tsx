import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type RecordData = Record<string, any>
const contactFields = ['name', 'email', 'address', 'phone', 'signature'] as const
const outcomes: Record<string, string> = {
  sent: 'Sent', drafted_not_sent: 'Drafted, not sent', left_alone: 'Left alone',
  held_for_review: 'Held for review', failed: 'Failed', queued: 'Queued',
  reviewing: 'Reviewing', capturing: 'Capturing evidence', researching: 'Finding recipient',
  drafting: 'Drafting', sending: 'Sending',
}
const site = (item: RecordData) => new URL(item.page_url).hostname
const action = (item: RecordData) => item.batch_outcome?.decision?.route
  ? item.batch_outcome.decision : item.possible_action
const source = (value: string) => value === 'agent' ? 'Agent' : 'Rule fallback'

async function api(path: string, options?: RequestInit) {
  const response = await fetch(path, options)
  const value = await response.json()
  if (!response.ok) throw new Error(value.error?.message ?? 'Request failed')
  return value
}

export function Matches({ cases, people, busy, refresh }: {
  cases: RecordData[], people: RecordData[], busy: boolean, refresh: () => Promise<void>,
}) {
  const [selected, setSelected] = useState<number[]>([])
  const [detailId, setDetailId] = useState<number | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [warning, setWarning] = useState('')
  const [contact, setContact] = useState<Record<string, string>>({ name: '', email: '', address: '', phone: '', signature: '' })
  const [acceptedBy, setAcceptedBy] = useState('')
  const [batch, setBatch] = useState<RecordData | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const selectedCases = cases.filter(item => selected.includes(item.id))
  const detail = cases.find(item => item.id === detailId)
  const running = starting || batch?.status === 'queued' || batch?.status === 'running'
  const allSelected = cases.length > 0 && selectedCases.length === cases.length

  useEffect(() => {
    api('/api/batches/warning').then(value => setWarning(value.warning)).catch(err => setError(err.message))
  }, [])

  useEffect(() => {
    if (!batch || !['queued', 'running'].includes(batch.status)) return
    let active = true
    const timer = window.setInterval(async () => {
      try {
        const value = await api(`/api/batches/${batch.id}`)
        if (active) {
          setBatch(value)
          await refresh()
        }
      } catch (err) { if (active) setError(String(err)) }
    }, 600)
    return () => { active = false; window.clearInterval(timer) }
  }, [batch?.id, batch?.status])

  function openConfirmation() {
    const person = people.find(row => row.id === selectedCases[0]?.person_id)
    setContact(current => ({ ...current, name: current.name || person?.name || '', signature: current.signature || person?.name || '' }))
    setAcceptedBy(current => current || person?.name || '')
    setAccepted(false)
    setError('')
    setConfirm(true)
  }

  async function start(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!accepted || !warning || starting) return
    setStarting(true)
    setError('')
    try {
      const value = await api('/api/batches', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_ids: selectedCases.map(item => item.id), contact, accepted_by: acceptedBy, accepted_warning: accepted }),
      })
      setBatch(value)
      setConfirm(false)
      setSelected([])
      await refresh()
    } catch (err) { setError(String(err)) }
    finally { setStarting(false) }
  }

  return <section className="space-y-4" aria-label="Matches">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-xl font-medium">Matches <span data-testid="match-total">({cases.length})</span></h2>
        <p className="text-muted-foreground">All matches and possible matches. Open a match to inspect it.</p></div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={!cases.length || running} onClick={() => setSelected(allSelected ? [] : cases.map(item => item.id))}>{allSelected ? 'Clear selection' : 'Select all'}</Button>
        <span data-testid="selected-count">{selectedCases.length} selected</span>
        <Button disabled={!selectedCases.length || busy || running || !warning} onClick={openConfirmation}>Auto review / send</Button>
      </div>
    </div>
    {error && <p role="alert" className="rounded border border-destructive p-3">{error}</p>}
    {batch && <div role="status" data-testid="batch-progress" className="rounded border p-3">
      Batch {batch.status}: {batch.completed} of {batch.total} complete.
      {batch.items.filter((item: RecordData) => !outcomes[item.status] || !['sent', 'drafted_not_sent', 'left_alone', 'held_for_review', 'failed'].includes(item.status)).map((item: RecordData) =>
        <p key={item.case_id}>Case {item.case_id}: {item.reason}</p>)}
    </div>}
    {!cases.length && <p className="rounded border p-8 text-center">No matches yet. Enrol a person and run Find to scan for appearances.</p>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cases.map(item => <article key={item.id} data-testid="match-card" data-case-id={item.id} className="relative min-w-0 rounded-lg border bg-card p-3">
        <div className="mb-3 flex items-center gap-2">
          <Checkbox id={`select-match-${item.id}`} aria-label={`Select match ${item.id}`} checked={selected.includes(item.id)} disabled={running}
            onCheckedChange={checked => setSelected(current => checked ? [...current, item.id] : current.filter(id => id !== item.id))} />
          <Label htmlFor={`select-match-${item.id}`}>Match {item.id}</Label>
          <Badge variant="outline" className="ml-auto">{item.band === 'possible' ? 'Possible match' : 'Match'}</Badge>
        </div>
        <button type="button" aria-label={`Open match ${item.id}`} className="w-full space-y-3 rounded text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4" onClick={() => setDetailId(item.id)}>
          <img src={item.matched_image_url} alt={`Matched image ${item.id}`} className="h-48 w-full rounded bg-muted object-contain" />
          <p className="break-all font-medium">{site(item)}</p>
          <Badge variant="secondary" className="whitespace-normal text-left">{action(item).possible ? 'Possible: ' : ''}{action(item).label}</Badge>
          <p className="text-xs text-muted-foreground">{source(action(item).source)}</p>
          <Badge variant="outline" data-testid="match-status">{outcomes[item.batch_outcome?.status] ?? item.state.replaceAll('_', ' ')}</Badge>
          {item.batch_outcome && <p data-testid="match-outcome" className="break-words text-sm">{item.batch_outcome.reason}</p>}
        </button>
      </article>)}
    </div>

    <Dialog open={detailId !== null} onOpenChange={open => { if (!open) setDetailId(null) }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader><DialogTitle>{detail ? site(detail) : 'Match details'}</DialogTitle><DialogDescription>Evidence, legal action and request history for this match.</DialogDescription></DialogHeader>
        {detail && <div className="min-w-0 space-y-4" data-testid="match-detail">
          <img src={detail.matched_image_url} alt={`Full matched image ${detail.id}`} className="max-h-[50vh] w-full object-contain" />
          <p className="font-medium">{action(detail).possible ? 'Possible action: ' : ''}{action(detail).label}</p>
          <p>{action(detail).reason}</p>
          <p>Picked by: {source(action(detail).source)}{action(detail).model_status === 'model_not_configured' ? ' (model not configured)' : ''}</p>
          <a href={detail.page_url} target="_blank" rel="noreferrer" className="block break-all underline">Open source page</a>
          {detail.batch_outcome && <p>{outcomes[detail.batch_outcome.status]}: {detail.batch_outcome.reason}</p>}
          {detail.drafted_request && <>
            <p className="break-all">Recipient: {detail.drafted_request.recipient.address} · {detail.drafted_request.recipient.channel} · {detail.drafted_request.recipient.endpoint}</p>
            <h3 className="font-medium">Exact {detail.deliveries.some((row: RecordData) => row.notice_id === detail.drafted_request.id && row.status !== 'uncertain') ? 'sent' : 'drafted'} notice</h3>
            <pre data-testid="match-notice" className="whitespace-pre-wrap break-words rounded bg-muted p-3 text-xs">{detail.drafted_request.payload.body}</pre>
          </>}
        </div>}
      </DialogContent>
    </Dialog>

    <Dialog open={confirm} onOpenChange={open => { if (!starting) setConfirm(open) }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader><DialogTitle>Authorize auto review / send</DialogTitle><DialogDescription>Review every selected match and accept responsibility for this batch.</DialogDescription></DialogHeader>
        <form className="space-y-4" onSubmit={start}>
          <ul className="max-h-44 space-y-2 overflow-y-auto rounded border p-3" data-testid="batch-selection">
            {selectedCases.map(item => <li key={item.id}>Match {item.id} · {site(item)} · Intended: {item.possible_action.label}</li>)}
          </ul>
          <p>The agent reviews these possible actions and may choose another legal basis or hold a match for review.</p>
          <p className="rounded border p-3" data-testid="legal-warning">{warning}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {contactFields.map(key => <div key={key} className={key === 'address' ? 'sm:col-span-2' : ''}>
              <Label htmlFor={`batch-${key}`}>Batch contact {key}</Label>
              <Input id={`batch-${key}`} type={key === 'email' ? 'email' : 'text'} required value={contact[key]}
                onChange={event => setContact(current => ({ ...current, [key]: event.target.value }))} />
            </div>)}
            <div className="sm:col-span-2"><Label htmlFor="accepted-by">Who accepts responsibility</Label>
              <Input id="accepted-by" required value={acceptedBy} onChange={event => setAcceptedBy(event.target.value)} /></div>
          </div>
          <div className="flex items-start gap-2"><Checkbox id="warning-accepted" checked={accepted} onCheckedChange={value => setAccepted(value === true)} />
            <Label htmlFor="warning-accepted" className="leading-5">I accept the legal-responsibility warning and authorize this batch.</Label></div>
          {error && <p role="alert">{error}</p>}
          <Button type="submit" disabled={!accepted || !warning || starting || busy || !selectedCases.length || !acceptedBy.trim() || contactFields.some(key => !contact[key].trim())}>Run authorized batch</Button>
        </form>
      </DialogContent>
    </Dialog>
  </section>
}

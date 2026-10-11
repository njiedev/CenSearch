import { useEffect, useState } from 'react'
import { Readable } from './Readable'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type Json = Record<string, any>

export function Workflow({ cases, screen, initialId }: { cases: Json[], screen: string, initialId?: number }) {
  const [id, setId] = useState<number | undefined>(initialId ?? cases[0]?.id)
  const [flow, setFlow] = useState<Json | null>(null)
  const [answers, setAnswers] = useState<Json>({})
  const [contact, setContact] = useState<Json>({})
  const [actor, setActor] = useState('')
  const [recipient, setRecipient] = useState('')
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [seconds, setSeconds] = useState('172801')
  const [replyText, setReplyText] = useState('')
  const [replyAnalysis, setReplyAnalysis] = useState<Json | null>(null)

  async function api(path: string, body?: unknown, method = 'POST') {
    const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error?.message ?? `HTTP ${response.status}`)
    return data
  }
  async function refresh(reset = false) {
    if (!id) return
    const value = await api(`/api/cases/${id}/workflow`, undefined, 'GET')
    setFlow(value)
    if (reset) { setAnswers(value.answers); setContact(value.contact); setRecipient('') }
  }
  async function action(fn: () => Promise<unknown>) {
    setWorking(true); setError('')
    try { await fn(); await refresh() } catch (e) { setError(String(e)) } finally { setWorking(false) }
  }
  useEffect(() => {
    setFlow(null)
    if (id) void action(async () => {
      await refresh(true)
      if (screen === 'decide') await api(`/api/cases/${id}/description`)
    })
  }, [id, screen])

  const post = (path: string, body?: unknown) => api(`/api/cases/${id}/${path}`, body)
  const latest = flow?.notices?.at(-1)
  const selected = cases.find(item => item.id === id)
  const publicSource = Boolean(selected?.evidence.context?.discovery?.draft_only)
  const rung = flow?.next_rung ?? 'site'
  const candidates = flow?.lookup?.recipients?.filter((item: Json) => item.rung === rung) ?? []
  const chosen = recipient || candidates[0]?.id || ''

  return <Card><CardHeader><CardTitle>{screen === 'decide' ? 'Decide' : screen === 'send' ? 'Send' : 'Verify'}</CardTitle></CardHeader>
    <CardContent className="flex flex-col gap-4">
      <Label htmlFor="workflow-case">Choose workflow case</Label>
      <select id="workflow-case" className="w-full rounded border p-2" value={id ?? ''} disabled={working}
        onChange={event => setId(Number(event.target.value))}>
        <option value="">Select a case</option>
        {cases.map(item => <option key={item.id} value={item.id}>Case {item.id}: {item.page_url}</option>)}
      </select>
      {error && <p role="alert">{error}</p>}
      {working && <p role="status">Working...</p>}
      {selected?.evidence.context?.discovery && <p>{selected.evidence.context.discovery.source_label} · {selected.evidence.context.discovery.label}</p>}
      {flow && <>
        <p>State: <strong data-testid="workflow-state">{flow.state}</strong> · Next rung: {rung}</p>
        {screen === 'decide' && <>
          <p className="break-all">{selected?.page_url}</p>
          <p data-testid="page-description">Page description (advisory): {flow.description?.description ??
            (flow.description?.status === 'model_not_configured' ? 'Model not configured. Continue with your own review.' : 'Unavailable.')}</p>
          {flow.bundle?.screenshot_url && <img src={flow.bundle.screenshot_url} alt="Full page evidence screenshot" className="max-h-96 w-full object-contain" />}
          <Button disabled={working || !!latest} onClick={() => action(() => post('evidence'))}>Capture evidence</Button>
          <Label htmlFor="actor">Your name for these answers and approvals</Label><Input id="actor" value={actor} onChange={e => setActor(e.target.value)} />
          {Object.entries({ ...flow.questions, ...flow.additional_questions }).map(([key, label]) => <div key={key}>
            <Label htmlFor={`answer-${key}`}>{String(label)}</Label>
            <select id={`answer-${key}`} className="block w-full rounded border p-2" value={answers[key] === true ? 'yes' : answers[key] === false ? 'no' : ''}
              onChange={e => setAnswers({ ...answers, [key]: e.target.value === '' ? null : e.target.value === 'yes' })}>
              <option value="">Not answered</option><option value="yes">Yes</option><option value="no">No</option>
            </select>
          </div>)}
          {['work_description', 'explanation'].map(key => <div key={key}><Label htmlFor={key}>{key === 'work_description' ? 'Description of your copyrighted work' : 'Your explanation'}</Label>
            <Textarea id={key} value={answers[key] ?? ''} onChange={e => setAnswers({ ...answers, [key]: e.target.value })} /></div>)}
          {['name', 'email', 'address', 'phone', 'signature'].map(key => <div key={key}><Label htmlFor={`contact-${key}`}>Contact {key}</Label>
            <Input id={`contact-${key}`} value={contact[key] ?? ''} onChange={e => setContact({ ...contact, [key]: e.target.value })} /></div>)}
          <Button disabled={working || !actor.trim()} onClick={() => action(() => post('answers', { answered_by: actor, answers, contact }))}>Save answers and route</Button>
          <p data-testid="route-result">Route: {flow.decision?.route ?? 'Not decided'} · Rule: {flow.decision?.rule_id ?? 'None'}{flow.decision?.version && ` (${flow.decision.version})`}.</p>
          <details><summary>Stored attestations and decision inputs</summary><Readable value={{ attestations: flow.attestations, decision: flow.decision }} /></details>
          {latest && <><h3>Drafted request</h3><pre data-testid="notice-body">{latest.payload.body}</pre></>}
        </>}
        {screen === 'send' && <>
          <p>Route: {flow.decision?.route ?? 'Answer questions in Decide first'} · Rule: {flow.decision?.rule_id}</p>
          <Button disabled={working} onClick={() => action(() => post('recipients'))}>Look up recipients</Button>
          <p data-testid="lookup-source">Research source: {flow.lookup?.source ?? 'Not run'} · Model: {flow.lookup?.model_status ?? 'Not run'}</p>
          <details open><summary>Lookup trace</summary><div data-testid="lookup-trace"><Readable value={{ calls: flow.lookup?.tool_calls, requests: flow.lookup?.requests, failure: flow.lookup?.agent_attempt }} /></div></details>
          {flow.lookup?.recipients?.map((item: Json) => <div key={item.id} className="rounded border p-3"><p>Rank {item.rank} · {item.rung} · {item.channel}</p><p className="break-all">{item.address}</p><Readable value={item.evidence} /></div>)}
          <Label htmlFor="recipient">Recipient for {rung}</Label><select id="recipient" className="w-full rounded border p-2" value={chosen} onChange={e => setRecipient(e.target.value)}>
            {!candidates.length && <option value="">No recipient found on this rung</option>}
            {candidates.map((item: Json) => <option key={item.id} value={item.id}>{item.channel}: {item.address}</option>)}
          </select>
          <Label htmlFor="approver">Your name for approval</Label><Input id="approver" value={actor} onChange={e => setActor(e.target.value)} />
          <Button disabled={working || !actor.trim()} onClick={() => action(() => post('approve-draft', { approved_by: actor, revision: flow.revision, rung }))}>Approve preparation for {rung}</Button>
          <Button disabled={working || !chosen} onClick={() => action(() => post('draft', { recipient_id: chosen, rung }))}>Create draft for {rung}</Button>
          {latest && <>
            <h3>Review exact request #{latest.id}</h3><pre data-testid="notice-body">{latest.payload.body}</pre>
            <p className="break-all">Recipient: {latest.recipient.address} · SHA256: {latest.sha256}</p>
            {latest.recipient.channel.startsWith('manual') && <p>The person sends this real-site draft themselves. Automatic delivery is disabled.</p>}
            <Button disabled={working || !actor.trim()} onClick={() => action(() => post('approve', { notice_id: latest.id, sha256: latest.sha256, approved_by: actor }))}>Approve this exact request</Button>
            <Button disabled={working || publicSource || !latest.approved_by || latest.recipient.channel.startsWith('manual')} onClick={() => action(() => post('send'))}>Send approved mock request</Button>
          </>}
        </>}
        {screen === 'verify' && <>
          <Button disabled={working} onClick={() => action(() => post('verify'))}>Check source now</Button>
          {flow.state === 'decision_required' && <p role="alert" data-testid="refusal-decision">The recipient gave a reasoned refusal. Review their reason below. Automatic escalation is stopped.</p>}
          {flow.state === 'escalation_approval_required' && <p>Silence passed the deadline. Open Send and approve a new request for the {rung} rung.</p>}
          <p>Search delisting does not remove the source image.</p>
          {flow.demo_clock && <><Label htmlFor="advance-seconds">Advance demo clock by seconds</Label><Input id="advance-seconds" type="number" value={seconds} onChange={e => setSeconds(e.target.value)} />
            <Button disabled={working} onClick={() => action(() => api('/api/clock/advance', { seconds: Number(seconds) }))}>Advance clock and check deadlines</Button></>}
          <Label htmlFor="reply-text">Reply text for optional advisory reading</Label>
          <Textarea id="reply-text" value={replyText} onChange={e => setReplyText(e.target.value)} />
          <Button disabled={working || !replyText.trim()} onClick={() => action(async () => setReplyAnalysis(await post('reply-analysis', { text: replyText })))}>Read reply (advisory)</Button>
          {replyAnalysis && <p data-testid="reply-advisory">{replyAnalysis.status}: {replyAnalysis.category ?? 'No classification'} {replyAnalysis.recommendation}</p>}
          <h3>Verification checks</h3><div data-testid="verification-checks" className="space-y-3">{flow.checks.map((check: Json, index: number) =>
            <div key={index} className="rounded border p-3"><strong>{check.outcome}</strong> · {check.checked_at}
              <p>Source removed: {check.source_removed ? 'yes' : 'no'}</p>
              <details><summary>HTTP evidence</summary><Readable value={check} /></details>
            </div>)}</div>
          <h3>Case timeline</h3><ol data-testid="case-timeline" className="space-y-3">{flow.timeline.map((event: Json) => <li key={event.id} className="border-l pl-3"><strong>{event.kind}</strong> · {event.at}<details><summary>Details</summary><Readable value={event.details} /></details></li>)}</ol>
        </>}
      </>}
    </CardContent>
  </Card>
}

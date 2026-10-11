import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Readable } from './Readable'

type Data = Record<string, any>
const metrics = [
  ['queries_run', 'Queries run'], ['pages_attempted', 'Pages attempted'],
  ['pages_failed', 'Pages failed'], ['images_fetched', 'Images fetched'],
  ['usable_faces', 'Usable faces'], ['possible_matches', 'Possible matches'],
]

async function api(path: string, options?: RequestInit) {
  const response = await fetch(path, options)
  const body = await response.json()
  if (!response.ok) throw new Error(body.error?.message ?? 'Request failed')
  return body
}

function Counts({ value }: { value: Data }) {
  return <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">{metrics.map(([key, title]) =>
    <div key={key}><dt>{title}</dt><dd className="text-xl tabular-nums">{value[key] ?? 0}</dd></div>,
  )}</dl>
}

export function PublicWeb({ people, busy, openCase }: {
  people: Data[], busy: boolean, openCase: (item: Data) => void,
}) {
  const [personId, setPersonId] = useState('')
  const [name, setName] = useState('')
  const [handles, setHandles] = useState('')
  const [context, setContext] = useState('')
  const [urls, setUrls] = useState('')
  const [mode, setMode] = useState('supplied_urls')
  const [allowPublic, setAllowPublic] = useState(false)
  const [runs, setRuns] = useState<Data[]>([])
  const [runId, setRunId] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const selectedPerson = people.find(person => person.id === personId)
  const run = runs.find(item => item.id === runId) ?? runs[0]
  const active = starting || busy || ['queued', 'running'].includes(run?.status)

  useEffect(() => {
    let alive = true
    async function poll() {
      try {
        const rows = await api('/api/public-searches')
        if (alive) setRuns(rows)
      } catch (err) { if (alive) setError(String(err)) }
    }
    void poll()
    const timer = window.setInterval(poll, 1000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [])

  async function start(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setStarting(true)
    setError('')
    try {
      const result = await api('/api/public-searches', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: personId, full_name: name,
          handles: handles.split(/[\n,]/).map(value => value.trim()).filter(Boolean),
          context, supplied_urls: mode === 'name_search' ? [] : urls.split('\n').map(value => value.trim()).filter(Boolean),
          mode, allow_public_fetch: allowPublic }),
      })
      setRunId(result.id)
      setRuns(rows => [result, ...rows.filter(item => item.id !== result.id)])
    } catch (err) { setError(String(err)) }
    finally { setStarting(false) }
  }

  return <section className="space-y-4" aria-label="Public web">
    <Card><CardHeader><CardTitle>Public web</CardTitle></CardHeader><CardContent className="space-y-4">
      <p>Search public pages by name or handle, then compare images locally. This is a bounded candidate search, not an internet-wide face index. Photos stay on this machine; real sources stop at drafts. This run reads static HTML; images that require JavaScript may be missed.</p>
      <form onSubmit={start} className="space-y-3">
        <Label htmlFor="public-person">Enrolled person</Label>
        <select id="public-person" required className="w-full rounded border p-2" value={personId} onChange={event => {
          setPersonId(event.target.value)
          setName(people.find(person => person.id === event.target.value)?.name ?? '')
        }}><option value="">Select...</option>{people.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</select>
        {selectedPerson?.development_fixture && <p>Local research fixture: only supplied loopback URLs are allowed. These are excluded from public-web counts.</p>}
        <Label htmlFor="public-mode">Discovery mode</Label>
        <select id="public-mode" className="w-full rounded border p-2" value={mode} onChange={event => setMode(event.target.value)}>
          <option value="supplied_urls">Check supplied public URLs</option>
          <option value="name_search">Public web · name/handle search</option>
          <option value="combined">Name/handle search and supplied URLs</option>
        </select>
        <Label htmlFor="public-name">Full name</Label><Input id="public-name" value={name} maxLength={200} onChange={event => setName(event.target.value)} />
        <Label htmlFor="public-handles">Handles (one per line, no email addresses)</Label><Textarea id="public-handles" value={handles} onChange={event => setHandles(event.target.value)} />
        <Label htmlFor="public-context">Public context (organisation, city or event, optional)</Label><Input id="public-context" maxLength={300} value={context} onChange={event => setContext(event.target.value)} />
        {mode !== 'name_search' && <><Label htmlFor="public-urls">Source page URLs (one per line, up to 25)</Label><Textarea id="public-urls" value={urls} onChange={event => setUrls(event.target.value)} /></>}
        <div className="flex items-center gap-2"><input id="public-fetch" type="checkbox" checked={allowPublic} onChange={event => setAllowPublic(event.target.checked)} /><Label htmlFor="public-fetch">Enable public GET fetching for this run only</Label></div>
        <p>Up to 8 search requests, 25 pages and 100 image attempts; depth 0; at least 0.5 s between requests to each origin; 90 s total, returning partial results.</p>
        <Button type="submit" disabled={active || !personId}>Run public check</Button>
      </form>
      {error && <p role="alert">{error}</p>}
    </CardContent></Card>
    {run && <>
      <Label htmlFor="public-run">Run history</Label><select id="public-run" className="w-full rounded border p-2" value={run.id} onChange={event => setRunId(Number(event.target.value))}>{runs.map(item => <option key={item.id} value={item.id}>Run {item.id} · {item.status} · {item.started_at}</option>)}</select>
      <Card><CardHeader><CardTitle>Public-web results</CardTitle></CardHeader><CardContent className="space-y-3">
        <p role="status" data-testid="public-status">Run {run.id}: {run.status} · {run.started_at}</p>
        {run.provider_status === 'not_configured' && <p role="alert">Search provider not configured. Set SERPAPI_API_KEY in backend/.env and restart the backend, or choose Check supplied public URLs; that mode needs no search key.</p>}
        {['provider_error', 'query_limit'].includes(run.provider_status) && <p>Search provider: {run.provider_status}. Inspect the tool trace below; these results may be partial.</p>}
        <Counts value={run.counts ?? {}} />
        <p>Usable faces counts quality-accepted detections, not people identified. Scores are similarities, not probabilities. An unavailable source is not a verified match.</p>
        {(run.local_counts?.pages_attempted ?? 0) > 0 && <div className="space-y-2 rounded border p-3"><h3 className="font-medium">Simulated delivery · loopback mock administrator</h3><p>Local test checks, excluded from public-web counts.</p><Counts value={run.local_counts} /></div>}
        <h3 className="font-medium">Discovery agent</h3>
        <p>{run.agent?.source === 'rule_fallback' ? 'Rule-based query fallback used' : run.agent?.source === 'strands_agent' ? 'Strands discovery agent' : 'Supplied URLs · no query agent needed'} · {run.agent?.model_status}</p>
        {run.agent?.queries?.map((query: Data, index: number) => <p key={index}><strong>{query.query}</strong> ({query.kind}) — {query.reason}</p>)}
        {run.agent?.summary && <p>{run.agent.summary}</p>}
        <details><summary>Full discovery tool trace ({run.tool_calls?.length ?? 0})</summary><Readable value={{ calls: run.tool_calls, sdk_tool_calls: run.agent?.sdk_tool_calls, messages: run.agent?.messages }} /></details>
        <details><summary>Pages checked and failures ({run.pages?.length ?? 0})</summary><Readable value={run.pages} /></details>
        <details><summary>Candidate provenance and limits</summary><Readable value={{ candidates: run.candidates, limits: run.limits, errors: run.errors }} /></details>
        {!run.results?.length && !['queued', 'running'].includes(run.status) && <p>No possible matches found in the pages checked. Unfetched pages and images were not assessed.</p>}
      </CardContent></Card>
      {[false, true].map(simulated => {
        const results = (run.results ?? []).filter((item: Data) => Boolean(item.evidence.context.discovery.simulated) === simulated)
        if (!results.length) return null
        return <div key={String(simulated)} className="space-y-3"><h3 className="text-lg">{simulated ? 'Simulated delivery · loopback mock administrator' : 'Real source · draft only'}</h3>{results.map((item: Data) => {
          const discovery = item.evidence.context.discovery
          return <Card key={item.id}><CardHeader><CardTitle>Possible match · review needed</CardTitle></CardHeader><CardContent className="space-y-2">
            <p>{discovery.label}</p><a className="block break-all underline" href={item.page_url} target="_blank" rel="noreferrer">{item.page_url}</a>
            <p>Page fetched: {discovery.page_fetched_at} · Image fetched: {item.evidence.image.fetched_at}</p>
            <p>Local {item.evidence.score_basis}: {item.score.toFixed(4)} · band {item.band} · {item.photo_relation}</p>
            <Button variant="outline" onClick={() => openCase(item)}>Review case {item.id}</Button>
          </CardContent></Card>
        })}</div>
      })}
    </>}
  </section>
}

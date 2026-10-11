import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import './index.css'
import { Workflow } from './Workflow'
import { Readable } from './Readable'
import { Matches } from './Matches'
import { PublicWeb } from './PublicWeb'

type Json = Record<string, any>

async function request(path: string, options?: RequestInit) {
  const response = await fetch(path, options)
  const body = await response.json()
  if (!response.ok) throw body
  return body
}

function App() {
  const [health, setHealth] = useState<Json | null>(null)
  const [people, setPeople] = useState<Json[]>([])
  const [cases, setCases] = useState<Json[]>([])
  const [runs, setRuns] = useState<Json[]>([])
  const [scans, setScans] = useState<Json[]>([])
  const [run, setRun] = useState<Json | null>(null)
  const [selected, setSelected] = useState<Json | null>(null)
  const [result, setResult] = useState<Json | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [working, setWorking] = useState(false)
  const [tab, setTab] = useState('matches')
  const [seeds, setSeeds] = useState('')
  const [rendered, setRendered] = useState(true)
  const [camera, setCamera] = useState(false)
  const [captures, setCaptures] = useState<File[]>([])
  const [probe, setProbe] = useState<unknown>(null)
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const initializedSeeds = useRef(false)

  function stopCamera() {
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
    setCamera(false)
  }

  useEffect(() => () => stream.current?.getTracks().forEach(track => track.stop()), [])
  useEffect(() => {
    if (video.current && stream.current) video.current.srcObject = stream.current
  }, [camera])

  async function refresh() {
    const h = await request('/api/health')
    setHealth(h)
    if (!initializedSeeds.current) {
      setSeeds(h.mock_seeds.join('\n'))
      initializedSeeds.current = true
    }
    const [p, c, r, s] = await Promise.all([
      request('/api/people'), request('/api/cases'), request('/api/crawls'), request('/api/scans'),
    ])
    setPeople(p)
    setCases(c)
    const mockRuns = r.filter((item: Json) => !item.config.public_search)
    const mockIds = new Set(mockRuns.map((item: Json) => item.id))
    setRuns(mockRuns)
    setScans(s.filter((item: Json) => mockIds.has(item.run_id)))
    setRun(mockRuns[0] ?? null)
  }

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        if (active) await refresh()
      } catch (err) {
        if (active) setError(err)
      }
    }
    void poll()
    const timer = window.setInterval(poll, 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  async function perform(action: () => Promise<void>) {
    setError(null)
    setWorking(true)
    try { await action() } catch (err) { setError(err instanceof Error ? err.message : err) }
    finally { setWorking(false) }
  }

  async function enroll(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    for (const key of ['references', 'originals']) {
      const files = data.getAll(key).filter(item => item instanceof File && item.size > 0)
      data.delete(key)
      files.forEach(file => data.append(key, file))
    }
    captures.forEach(file => data.append('references', file))
    setResult(null)
    await perform(async () => {
      const enrolled = await request('/api/people', { method: 'POST', body: data })
      setResult(enrolled)
      setCaptures([])
      stopCamera()
      form.reset()
      await refresh()
    })
  }

  async function capture() {
    const source = video.current
    if (!source || !source.videoWidth) throw new Error('Camera is not ready yet.')
    const canvas = document.createElement('canvas')
    canvas.width = source.videoWidth
    canvas.height = source.videoHeight
    canvas.getContext('2d')!.drawImage(source, 0, 0)
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.95))
    if (!blob) throw new Error('Camera capture failed.')
    setCaptures(current => [...current, new File([blob], `webcam-${Date.now()}.jpg`, { type: 'image/jpeg' })])
  }

  const legacyCases = cases.filter(item => !item.evidence.context?.discovery)
  const disabled = working || Boolean(health?.busy)
  return <main className="mx-auto max-w-6xl space-y-4 p-4 text-sm">
    <h1 className="text-2xl font-medium">Likeness Guard</h1>
    <Card><CardHeader><CardTitle className="text-lg">Status</CardTitle></CardHeader><CardContent className="space-y-2">
      {!health ? <p>Loading status...</p> : <>
        <p data-testid="health-summary">Database: {health.database.status} · Face models: {health.face_models.loaded ? 'loaded' : 'unavailable'} · Model: {health.model.configured ? 'configured' : 'not configured'} · Storage: {health.object_storage.mode} · Busy: {String(health.busy)}</p>
        <details><summary>Full health record</summary><Readable value={health} /></details>
      </>}
    </CardContent></Card>
    <nav aria-label="Console screens" className="flex flex-wrap gap-2">
      {['matches', 'enroll', 'public', 'find', 'case', 'decide', 'send', 'verify', 'agent'].map(name => <Button key={name} variant={tab === name ? 'default' : 'outline'} onClick={() => setTab(name)}>{name === 'public' ? 'Public web' : name === 'enroll' ? 'Enroll' : name === 'find' ? 'Find' : name === 'case' ? 'Case' : name === 'agent' ? 'Agent probe' : name[0].toUpperCase() + name.slice(1)}</Button>)}
    </nav>
    {error !== null && <div role="alert" className="rounded border p-3"><p>Request failed</p><Readable value={error} /></div>}
    {working && <p role="status">Working...</p>}
    {tab === 'matches' && <Matches cases={cases} people={people} busy={Boolean(health?.busy)} refresh={refresh} />}
    {tab === 'public' && <PublicWeb people={people} busy={Boolean(health?.busy)} openCase={item => { setSelected(item); setTab('decide') }} />}
    {tab === 'enroll' && <>
      <Card><CardHeader><CardTitle>Enroll a person</CardTitle></CardHeader><CardContent>
        <form onSubmit={enroll} className="space-y-4">
          <div><Label htmlFor="name">Name</Label><Input id="name" name="name" required /></div>
          <div><Label htmlFor="consent">Consent statement</Label><Textarea id="consent" name="consent" required placeholder="Write your consent to store and match your face locally." /></div>
          <div><Label htmlFor="references">Reference photos</Label><Input id="references" name="references" type="file" accept="image/*" multiple /><p>At least one clear, single-face reference. Webcam captures are added below.</p></div>
          <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={() => perform(async () => {
            stopCamera()
            stream.current = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
            setCamera(true)
          })}>Start webcam</Button>{camera && <><Button type="button" variant="outline" onClick={() => perform(capture)}>Capture reference</Button><Button type="button" variant="outline" onClick={stopCamera}>Stop webcam</Button></>}</div>
          {camera && <video ref={video} autoPlay muted playsInline className="max-h-64 w-full border" aria-label="Webcam preview" />}
          {captures.map((file, index) => <div key={file.name}>{file.name} <Button type="button" variant="outline" onClick={() => setCaptures(current => current.filter((_, i) => i !== index))}>Remove capture {index + 1}</Button></div>)}
          <div><Label htmlFor="originals">Owned original photos (optional)</Label><Input id="originals" name="originals" type="file" accept="image/*" multiple /></div>
          <div><Label htmlFor="ownership">Ownership statement (required with originals)</Label><Textarea id="ownership" name="ownership" /></div>
          <div className="flex items-center gap-2"><input id="fixture" type="checkbox" name="development_fixture" value="true" /><Label htmlFor="fixture">Local development fixture, not a real consent or ownership claim</Label></div>
          <Button type="submit" disabled={disabled}>Enroll person</Button>
        </form>
      </CardContent></Card>
      {result && <Card><CardHeader><CardTitle>Enrollment saved</CardTitle></CardHeader><CardContent><Readable value={result} /></CardContent></Card>}
      <Card><CardHeader><CardTitle>Enrolled people ({people.length})</CardTitle></CardHeader><CardContent className="space-y-3">
        {!people.length && <p>No people enrolled yet.</p>}
        {people.map(person => <div key={person.id} className="space-y-2 border-b pb-3"><p>{person.name} · {person.references.length} references ({person.active_reference_count} active) · {person.originals.length} originals</p>
          <details><summary>Person, photo results and stored metadata</summary><Readable value={person} /></details>
          <Button variant="outline" disabled={disabled} onClick={() => perform(async () => { await request(`/api/people/${person.id}`, { method: 'DELETE' }); setSelected(null); setResult(null); await refresh() })}>Delete {person.name}</Button>
        </div>)}
      </CardContent></Card>
    </>}
    {tab === 'find' && <>
      <Card><CardHeader><CardTitle>Find appearances · simulated web</CardTitle></CardHeader><CardContent className="space-y-3">
        <Label htmlFor="seeds">Starting URLs (one per line)</Label><Textarea id="seeds" value={seeds} onChange={event => setSeeds(event.target.value)} />
        <div className="flex items-center gap-2"><input id="rendered" type="checkbox" checked={rendered} onChange={event => setRendered(event.target.checked)} /><Label htmlFor="rendered">Render JavaScript pages</Label></div>
        <Button disabled={disabled || !people.length} onClick={() => perform(async () => {
          const item = await request('/api/crawls', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seeds: seeds.split('\n').map(s => s.trim()).filter(Boolean), rendered }) })
          setRun(item)
          await refresh()
        })}>Start crawl</Button>
        {run && <div role="status"><p data-testid="crawl-status">Crawl {run.id}: {run.status}</p><Readable value={run} /></div>}
        <details><summary>All crawl runs ({runs.length})</summary><Readable value={runs} /></details>
        <details><summary>Scan metadata ({scans.length}), including nonmatches</summary><Readable value={scans} /></details>
      </CardContent></Card>
      <h2 className="text-lg">Simulated delivery · loopback mock administrator ({legacyCases.length})</h2>
      {!legacyCases.length && <p>No cases found yet.</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{legacyCases.map(item => <Card key={item.id} data-testid="case-card"><CardHeader><CardTitle>Case {item.id}</CardTitle></CardHeader><CardContent className="space-y-2">
        <img src={item.matched_image_url} alt={`Matched evidence for case ${item.id}`} className="h-48 w-full object-contain" />
        <p className="break-all">Page: {item.page_url}</p>
        <p>{item.match_type} · {item.band} · score {item.score.toFixed(4)}</p>
        <p>{item.photo_relation} · copy: {item.copy_relation}</p>
        <p>Score basis: {item.evidence.score_basis}. Scores are not probabilities.</p>
        <Button variant="outline" onClick={() => perform(async () => { setSelected(await request(`/api/cases/${item.id}`)); setTab('case') })}>Open case {item.id}</Button>
      </CardContent></Card>)}</div>
    </>}
    {tab === 'case' && <Card><CardHeader><CardTitle>Case record</CardTitle></CardHeader><CardContent className="space-y-3">
      <Label htmlFor="case-select">Choose a case</Label><select id="case-select" className="w-full rounded border p-2" value={selected?.id ?? ''} onChange={event => {
        const id = event.target.value
        if (id) void perform(async () => setSelected(await request(`/api/cases/${id}`)))
      }}><option value="">Select...</option>{cases.map(item => <option key={item.id} value={item.id}>Case {item.id}: {item.page_url}</option>)}</select>
      {selected ? <><img src={selected.matched_image_url} alt="Case evidence" className="max-h-80 object-contain" /><Readable value={selected} /></> : <p>Select a case from Find or the list above.</p>}
    </CardContent></Card>}
    {['decide', 'send', 'verify'].includes(tab) && <Workflow cases={cases} screen={tab} initialId={selected?.id} />}
    {tab === 'agent' && <Card><CardHeader><CardTitle>Strands DNS probe</CardTitle></CardHeader><CardContent className="space-y-3">
      <p>Text only. Resolves localhost using a tool if the model is configured.</p>
      <Button disabled={working} onClick={() => perform(async () => setProbe(await request('/api/agent/probe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ hostname: 'localhost' }) })))}>Run DNS probe</Button>
      {probe !== null && <Readable value={probe} />}
    </CardContent></Card>}
  </main>
}

createRoot(document.getElementById('root')!).render(<App />)

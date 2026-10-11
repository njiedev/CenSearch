import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { useState, type FormEvent } from 'react'
import { api, isSample } from './api'
import { ErrorBox } from './ui'
import type { Run, SearchRequest } from './types'
import { usePoll } from './hooks'
import DeleteFaceCache from './DeleteFaceCache'

const invalidText = (value: string) => /[^\s@]+@[^\s@]+\.[^\s@]+|data:|base64|:\/\//i.test(value)
export default function NewScan({ personId, onStart }: { personId: string; onStart: (run: Run) => void }) {
  const [name, setName] = useState('')
  const [handles, setHandles] = useState<string[]>([])
  const [handle, setHandle] = useState('')
  const [context, setContext] = useState('')
  const [urls, setUrls] = useState('')
  const [consent, setConsent] = useState(false)
  const [faceSearch, setFaceSearch] = useState(!isSample())
  const [faceConsent, setFaceConsent] = useState(false)
  const cache = usePoll(() => api.faceCache(personId), [personId])
  const [sourceChoice, setSourceChoice] = useState<'live' | 'cache' | null>(null)
  const source = sourceChoice ?? (cache.value?.available ? 'cache' : 'live')
  const usingCache = faceSearch && source === 'cache'
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  function clear(field: string) {
    setErrors((current) => ({ ...current, [field]: '' }))
    setError('')
  }
  function addHandles() {
    const next = [
      ...new Set([
        ...handles,
        ...handle.split(/[,\n]/).map((value) => value.trim()).filter(Boolean),
      ]),
    ]
    if (next.length > 10) {
      setErrors((current) => ({ ...current, handles: 'Use at most 10 handles.' }))
      return
    }
    setHandles(next)
    setHandle('')
    clear('handles')
  }
  async function submit(event?: FormEvent) {
    event?.preventDefault()
    const combinedHandles = [
      ...new Set([
        ...handles,
        ...handle.split(/[,\n]/).map((value) => value.trim()).filter(Boolean),
      ]),
    ]
    const supplied = urls.split('\n').map((value) => value.trim()).filter(Boolean)
    const found: Record<string, string> = {}
    if (!faceSearch && !name.trim() && !combinedHandles.length && !supplied.length)
      found.name = 'Enter a name, a handle, or at least one page URL.'
    if (invalidText(name)) found.name = 'Use a name only, without email addresses, URLs or image data.'
    if (invalidText(context))
      found.context = 'Use public context only, without email addresses, URLs or image data.'
    if (combinedHandles.length > 10 || combinedHandles.some((value) => value.length > 100 || invalidText(value)))
      found.handles = 'Use at most 10 handles, up to 100 characters each; no emails, URLs or image data.'
    if (supplied.length > 25) found.urls = 'Use at most 25 page URLs.'
    for (const value of supplied) {
      try {
        const url = new URL(value)
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error()
      } catch {
        found.urls = 'Each line must be an http:// or https:// page URL, without a username or password.'
      }
    }
    if (!usingCache && !consent) found.consent = 'Allow public page fetching to start this scan.'
    if (faceSearch && !usingCache && !faceConsent)
      found.faceConsent = 'Allow the photo upload and 3-credit search to continue.'
    if (usingCache && !cache.value?.available) found.cache = 'No saved scan is available. Choose a new search explicitly.'
    if (faceSearch) {
      for (const key of ['name', 'handles', 'context', 'urls']) delete found[key]
    }
    setErrors(found)
    if (Object.keys(found).length) return
    const mode: SearchRequest['mode'] = faceSearch ? 'face_search' : supplied.length
      ? name.trim() || combinedHandles.length ? 'combined' : 'supplied_urls'
      : 'name_search'
    setBusy(true)
    setError('')
    try {
      onStart(await api.startScan({
        person_id: personId,
        full_name: faceSearch ? '' : name.trim(),
        handles: faceSearch ? [] : combinedHandles,
        context: faceSearch ? '' : context.trim(),
        supplied_urls: faceSearch ? [] : supplied,
        mode,
        allow_public_fetch: !usingCache,
        facecheck_consent: faceSearch && !usingCache && faceConsent,
        facecheck_source: usingCache ? 'cache' : 'live',
      }))
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const fieldError = (key: string) => errors[key] && <span className="field-error" id={`error-${key}`}>{errors[key]}</span>
  return (
    <section className="app-form-view">
      <h1>New scan</h1>
      <p>{faceSearch
        ? 'Search by your enrolled face photo. Only FaceCheck scores above 90 appear; 90 is excluded.'
        : 'Find public pages using your name, handles, or specific links. Your face photos stay out of the text search query.'}</p>
      <form className="scan-form" onSubmit={submit} noValidate>
        <RadioGroup className="col-span-full flex flex-wrap gap-6" value={faceSearch ? 'face' : 'text'} aria-label="Search method"
          onValueChange={(value) => { setFaceSearch(value === 'face'); setErrors({}); setError('') }}>
          <Label className="check-row"><RadioGroupItem value="face" />Face search · FaceCheck</Label>
          <Label className="check-row"><RadioGroupItem value="text" />Name / links · text search</Label>
        </RadioGroup>
        {faceSearch ? (
          <Card className="scan-input-group col-span-full">
            <CardHeader><CardTitle>Search by face</CardTitle></CardHeader>
            <CardContent className="grid gap-4">
              {!cache.value && !cache.error && <p role="status">Checking saved results…</p>}
              {cache.error && <ErrorBox error={cache.error} retry={cache.retry} />}
              {cache.value?.available && <>
                <p>Saved live search · {new Date(cache.value.saved_at!).toLocaleString()} · {cache.value.count} candidates above 90.</p>
                <RadioGroup value={source} aria-label="FaceCheck result source"
                  onValueChange={(value) => { setSourceChoice(value as 'live' | 'cache'); clear('cache') }}>
                  <Label className="check-row"><RadioGroupItem value="cache" />Use saved scan · no credits</Label>
                  <Label className="check-row"><RadioGroupItem value="live" />Run new search · 3 credits</Label>
                </RadioGroup>
                <DeleteFaceCache personId={personId} onDeleted={() => {
                  setSourceChoice('live'); setFaceConsent(false); cache.retry()
                }} />
              </>}
              {usingCache ? <p>Opens the saved scan immediately. No photo upload, new search, or page crawl.
                Results describe the web when that scan ran.</p> : <>
                <p>Your first enrolled face photo will be sent to FaceCheck with its metadata removed.
                  A live search costs 3 credits. Photos are never sent to the language model.</p>
                <p>Page text helps explain qualifying results and find removal contacts. It cannot change
                  the score or admit results at 90 or below.</p>
                <Label className="check-row">
                  <Checkbox checked={faceConsent}
                    onCheckedChange={(checked) => { setFaceConsent(checked === true); clear('faceConsent') }}
                    aria-describedby="error-faceConsent" aria-invalid={!!errors.faceConsent} />
                  I authorize sending this enrolled photo to FaceCheck and spending 3 credits on this scan.
                </Label>
                {fieldError('faceConsent')}
              </>}
              {fieldError('cache')}
            </CardContent>
          </Card>
        ) : <>
          <Card className="scan-input-group">
            <CardHeader><CardTitle>Name & handles</CardTitle></CardHeader>
            <CardContent className="grid gap-4">
              <Label>Full name
                <Input value={name} maxLength={200} onChange={(event) => { setName(event.target.value); clear('name') }}
                  aria-describedby="error-name" aria-invalid={!!errors.name} />
                {fieldError('name')}
              </Label>
              <Label>Handles <span className="muted">Up to 10 · comma or Enter to add</span>
                <Input value={handle} onChange={(event) => { setHandle(event.target.value); clear('handles') }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); addHandles() }
                  }} onBlur={addHandles} aria-invalid={!!errors.handles} aria-describedby="error-handles" />
                {fieldError('handles')}
              </Label>
              <div className="chips">
                {handles.map((value) => <Button variant="outline" type="button" key={value}
                  onClick={() => setHandles(handles.filter((item) => item !== value))} aria-label={`Remove handle ${value}`}>
                  {value} ×
                </Button>)}
              </div>
              <Label>Context <span className="muted">Optional, such as a city or profession</span>
                <Input value={context} maxLength={300} onChange={(event) => { setContext(event.target.value); clear('context') }} aria-describedby="error-context" />
                {fieldError('context')}
              </Label>
            </CardContent>
          </Card>
          <Card className="scan-input-group">
            <CardHeader><CardTitle>Specific pages</CardTitle></CardHeader>
            <CardContent className="grid gap-4">
              <Label>Page URLs <span className="muted">Optional · one per line, up to 25</span>
                <Textarea rows={8} value={urls} onChange={(event) => { setUrls(event.target.value); clear('urls') }}
                  aria-describedby="error-urls" aria-invalid={!!errors.urls} />
                {fieldError('urls')}
              </Label>
            </CardContent>
          </Card>
        </>}
        <div className="scan-form-footer">
          {!usingCache && <Label className="check-row">
            <Checkbox checked={consent} onCheckedChange={(checked) => { setConsent(checked === true); clear('consent') }} />
            <span>I allow this scan to read public pages while logged out.</span>
          </Label>}
          {fieldError('consent')}
          {error && <ErrorBox error={error} retry={() => void submit()} />}
          <Button type="submit" variant="default" disabled={busy || (faceSearch && !cache.value && !cache.error)}>
            {busy ? 'Opening scan…' : usingCache ? 'Open saved scan' : 'Start scan'}
          </Button>
        </div>
      </form>
    </section>
  )
}

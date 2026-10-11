import { useState, type FormEvent } from 'react'
import { api } from './api'
import { ErrorBox } from './ui'
import type { Run, SearchRequest } from './types'

const invalidText = (value: string) => /[^\s@]+@[^\s@]+\.[^\s@]+|data:|base64|:\/\//i.test(value)
export default function NewScan({ personId, onStart }: { personId: string; onStart: (run: Run) => void }) {
  const [name, setName] = useState('')
  const [handles, setHandles] = useState<string[]>([])
  const [handle, setHandle] = useState('')
  const [context, setContext] = useState('')
  const [urls, setUrls] = useState('')
  const [consent, setConsent] = useState(false)
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
        ...handle
          .split(/[,\n]/)
          .map((value) => value.trim())
          .filter(Boolean),
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
        ...handle
          .split(/[,\n]/)
          .map((value) => value.trim())
          .filter(Boolean),
      ]),
    ]
    const supplied = urls
      .split('\n')
      .map((value) => value.trim())
      .filter(Boolean)
    const found: Record<string, string> = {}
    if (!name.trim() && !combinedHandles.length && !supplied.length)
      found.name = 'Enter a name, a handle, or at least one page URL.'
    if (invalidText(name)) found.name = 'Use a name only, without email addresses, URLs or image data.'
    if (invalidText(context))
      found.context = 'Use public context only, without email addresses, URLs or image data.'
    if (
      combinedHandles.length > 10 ||
      combinedHandles.some((value) => value.length > 100 || invalidText(value))
    )
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
    if (!consent) found.consent = 'Allow public page fetching to start this scan.'
    setErrors(found)
    if (Object.keys(found).length) return
    const mode: SearchRequest['mode'] = supplied.length
      ? name.trim() || combinedHandles.length
        ? 'combined'
        : 'supplied_urls'
      : 'name_search'
    setBusy(true)
    setError('')
    try {
      onStart(
        await api.startScan({
          person_id: personId,
          full_name: name.trim(),
          handles: combinedHandles,
          context: context.trim(),
          supplied_urls: supplied,
          mode,
          allow_public_fetch: true,
        }),
      )
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const fieldError = (key: string) =>
    errors[key] && (
      <span className="field-error" id={`error-${key}`}>
        {errors[key]}
      </span>
    )
  return (
    <section className="app-form-view">
      <h1>New scan</h1>
      <p>
        Find public pages using your name, handles, or specific links. Your face photos stay out of the search
        query.
      </p>
      <form onSubmit={submit} noValidate>
        <label>
          Full name
          <input
            value={name}
            maxLength={200}
            onChange={(event) => {
              setName(event.target.value)
              clear('name')
            }}
            aria-describedby="error-name"
            aria-invalid={!!errors.name}
          />
          {fieldError('name')}
        </label>
        <label>
          Handles <span className="muted">Up to 10 · comma or Enter to add</span>
          <input
            value={handle}
            onChange={(event) => {
              setHandle(event.target.value)
              clear('handles')
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ',') {
                event.preventDefault()
                addHandles()
              }
            }}
            onBlur={addHandles}
            aria-invalid={!!errors.handles}
            aria-describedby="error-handles"
          />
          {fieldError('handles')}
        </label>
        <div className="chips">
          {handles.map((value) => (
            <button
              type="button"
              key={value}
              onClick={() => setHandles(handles.filter((item) => item !== value))}
              aria-label={`Remove handle ${value}`}
            >
              {value} ×
            </button>
          ))}
        </div>
        <label>
          Context <span className="muted">Optional, such as a city or profession</span>
          <input
            value={context}
            maxLength={300}
            onChange={(event) => {
              setContext(event.target.value)
              clear('context')
            }}
            aria-describedby="error-context"
          />
          {fieldError('context')}
        </label>
        <label>
          Page URLs <span className="muted">Optional · one per line, up to 25</span>
          <textarea
            rows={4}
            value={urls}
            onChange={(event) => {
              setUrls(event.target.value)
              clear('urls')
            }}
            aria-describedby="error-urls"
            aria-invalid={!!errors.urls}
          />
          {fieldError('urls')}
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => {
              setConsent(event.target.checked)
              clear('consent')
            }}
          />
          <span>
            I allow this scan to fetch public pages. It only reads pages, while logged out, using GET
            requests.
          </span>
        </label>
        {fieldError('consent')}
        {error && <ErrorBox error={error} retry={() => void submit()} />}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Starting scan…' : 'Start scan'}
        </button>
      </form>
    </section>
  )
}

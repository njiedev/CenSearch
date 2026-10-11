import { useEffect, useMemo, useState, type FormEvent } from 'react'
import SnakeEye from './SnakeEye'

// Sign-up is enrollment: POST /api/people (see backend/handoff/openapi.json).
// The person attests to consent and ownership by ticking the exact statements
// below; those statements are what the backend stores.
const CONSENT = 'I agree to let CenSearch store these photos and search the web for my face.'
const OWNERSHIP = 'I took these photos or own the rights to them.'
const OFFLINE = "Can't reach the CenSearch server. Make sure the backend is running, then try again."

type PhotoResult = {
  kind: 'reference' | 'original'
  filename: string
  accepted: boolean
  reason: string | null
}

type Outcome =
  | { state: 'idle' }
  | { state: 'sending' }
  | { state: 'enrolled'; name: string; photos: PhotoResult[] }
  | { state: 'failed'; message: string; photos: PhotoResult[] }

type Errors = Partial<Record<'name' | 'references' | 'consent' | 'ownership', string>>

// Reads either {"error": {...}} or FastAPI's {"detail": ...}; anything else is
// a network or server problem.
async function readFailure(response: Response) {
  try {
    const body = await response.json()
    if (body.error) {
      return { message: body.error.message as string, photos: (body.error.photos ?? []) as PhotoResult[] }
    }
    if (typeof body.detail === 'string') {
      return { message: body.detail, photos: [] }
    }
  } catch {
    // Not JSON; fall through.
  }
  // The dev proxy answers 5xx with no JSON when the backend isn't running.
  if (response.status >= 500) {
    return { message: OFFLINE, photos: [] }
  }
  return { message: `The server answered with an error (${response.status}). Try again in a moment.`, photos: [] }
}

function Previews({ files }: { files: File[] }) {
  const urls = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files])
  useEffect(() => () => urls.forEach((url) => URL.revokeObjectURL(url)), [urls])
  if (files.length === 0) {
    return null
  }
  return (
    <ul className="su-previews">
      {files.map((file, i) => (
        <li key={`${file.name}-${i}`}>
          <img src={urls[i]} alt={`Selected photo ${i + 1}`} />
        </li>
      ))}
    </ul>
  )
}

function PhotoList({ photos }: { photos: PhotoResult[] }) {
  if (photos.length === 0) {
    return null
  }
  return (
    <ul className="su-results">
      {photos.map((photo, i) => (
        <li key={`${photo.filename}-${i}`} className={photo.accepted ? 'ok' : 'bad'}>
          <span className="su-mark" aria-hidden="true">
            {photo.accepted ? '✓' : '✕'}
          </span>
          <span>
            {photo.accepted ? 'Accepted' : 'Rejected'}: {photo.filename}
            {photo.reason && ` (${photo.reason})`}
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function SignUp() {
  const [name, setName] = useState('')
  const [references, setReferences] = useState<File[]>([])
  const [originals, setOriginals] = useState<File[]>([])
  const [consent, setConsent] = useState(false)
  const [ownership, setOwnership] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [outcome, setOutcome] = useState<Outcome>({ state: 'idle' })

  function validate() {
    const found: Errors = {}
    if (!name.trim()) {
      found.name = 'Enter your name.'
    }
    if (references.length === 0) {
      found.references = 'Add at least one photo of your face.'
    }
    if (!consent) {
      found.consent = 'We need your consent to search for your face.'
    }
    if (originals.length > 0 && !ownership) {
      found.ownership = 'Confirm you own these photos, or remove them.'
    }
    return found
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) {
      return
    }

    const data = new FormData()
    data.append('name', name.trim())
    data.append('consent', CONSENT)
    references.forEach((file) => data.append('references', file))
    originals.forEach((file) => data.append('originals', file))
    if (originals.length > 0) {
      data.append('ownership', OWNERSHIP)
    }

    setOutcome({ state: 'sending' })
    try {
      const response = await fetch('/api/people', { method: 'POST', body: data })
      if (response.ok) {
        const body = await response.json()
        setOutcome({ state: 'enrolled', name: body.person.name, photos: body.photos })
      } else {
        setOutcome({ state: 'failed', ...(await readFailure(response)) })
      }
    } catch {
      setOutcome({ state: 'failed', message: OFFLINE, photos: [] })
    }
  }

  function reset() {
    setName('')
    setReferences([])
    setOriginals([])
    setConsent(false)
    setOwnership(false)
    setErrors({})
    setOutcome({ state: 'idle' })
  }

  const sending = outcome.state === 'sending'

  if (outcome.state === 'enrolled') {
    return (
      <div className="su-panel" role="status">
        <SnakeEye className="su-eye" track />
        <h2 className="su-title" id="signup-title">
          You're enrolled, {outcome.name}.
        </h2>
        <p className="su-lede">We'll search the web using the photos marked accepted.</p>
        <PhotoList photos={outcome.photos} />
        <button type="button" className="su-secondary" onClick={reset}>
          Enroll someone else
        </button>
      </div>
    )
  }

  return (
    <form className="su-panel" onSubmit={submit} noValidate>
      <SnakeEye className="su-eye" track />
      <h2 className="su-title" id="signup-title">
        Sign up
      </h2>
      <p className="su-lede">
        Add photos of your face. We'll find where they show up online and help get them taken down.
      </p>

      <div className="su-field">
        <label htmlFor="su-name">Name</label>
        <input
          id="su-name"
          type="text"
          autoComplete="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-invalid={Boolean(errors.name)}
          aria-describedby={errors.name ? 'su-name-error' : undefined}
        />
        {errors.name && (
          <p className="su-error" id="su-name-error">
            {errors.name}
          </p>
        )}
      </div>

      <div className="su-row">
        <div className="su-field">
          <label htmlFor="su-references">Photos of your face</label>
          <p className="su-hint" id="su-references-hint">
            Clear photos with just you in them.
          </p>
          <label className="su-drop">
            <input
              id="su-references"
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => setReferences(Array.from(event.target.files ?? []))}
              aria-invalid={Boolean(errors.references)}
              aria-describedby={errors.references ? 'su-references-hint su-references-error' : 'su-references-hint'}
            />
            <span>
              {references.length > 0
                ? `${references.length} photo${references.length === 1 ? '' : 's'} selected`
                : 'Choose photos'}
            </span>
          </label>
          <Previews files={references} />
          {errors.references && (
            <p className="su-error" id="su-references-error">
              {errors.references}
            </p>
          )}
        </div>

        <div className="su-field">
          <label htmlFor="su-originals">Photos you took (optional)</label>
          <p className="su-hint" id="su-originals-hint">
            These help us find exact copies.
          </p>
          <label className="su-drop">
            <input
              id="su-originals"
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => setOriginals(Array.from(event.target.files ?? []))}
              aria-describedby="su-originals-hint"
            />
            <span>
              {originals.length > 0
                ? `${originals.length} photo${originals.length === 1 ? '' : 's'} selected`
                : 'Choose photos'}
            </span>
          </label>
          <Previews files={originals} />
        </div>
      </div>

      <div className="su-field">
        <label className="su-check">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            aria-invalid={Boolean(errors.consent)}
            aria-describedby={errors.consent ? 'su-consent-error' : undefined}
          />
          <span>{CONSENT}</span>
        </label>
        {errors.consent && (
          <p className="su-error" id="su-consent-error">
            {errors.consent}
          </p>
        )}
      </div>

      {originals.length > 0 && (
        <div className="su-field">
          <label className="su-check">
            <input
              type="checkbox"
              checked={ownership}
              onChange={(event) => setOwnership(event.target.checked)}
              aria-invalid={Boolean(errors.ownership)}
              aria-describedby={errors.ownership ? 'su-ownership-error' : undefined}
            />
            <span>{OWNERSHIP}</span>
          </label>
          {errors.ownership && (
            <p className="su-error" id="su-ownership-error">
              {errors.ownership}
            </p>
          )}
        </div>
      )}

      {outcome.state === 'failed' && (
        <div className="su-failure" role="alert">
          <p>{outcome.message}</p>
          <PhotoList photos={outcome.photos} />
        </div>
      )}

      <button type="submit" className="su-submit" disabled={sending} aria-busy={sending}>
        {sending ? 'Enrolling…' : 'Enroll my face'}
      </button>

      <p className="su-privacy">Your photos are never sent to an AI model.</p>
    </form>
  )
}

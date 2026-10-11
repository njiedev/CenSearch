import { useState, type FormEvent } from 'react'
import { PERSON, WARNING } from './mockData'
import type { Case, Contact } from './types'
import { hostname } from './types'

const FIELDS: { key: keyof Contact; label: string; type?: string; wide?: boolean }[] = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email', type: 'email' },
  { key: 'address', label: 'Address', wide: true },
  { key: 'phone', label: 'Phone', type: 'tel' },
  { key: 'signature', label: 'Signature (type your full name)' },
]

type Props = {
  cases: Case[]
  onRun: (contact: Contact, acceptedBy: string) => void
  onCancel: () => void
}

export default function AuthorizeBatch({ cases, onRun, onCancel }: Props) {
  const [contact, setContact] = useState<Contact>({
    name: PERSON.name,
    email: '',
    address: '',
    phone: '',
    signature: PERSON.name,
  })
  const [acceptedBy, setAcceptedBy] = useState(PERSON.name)
  const [accepted, setAccepted] = useState(false)

  if (cases.length === 0) {
    return (
      <section className="mx-view">
        <div className="mx-empty">
          <h2>Nothing selected</h2>
          <p>Select one or more matches first, then come back here to authorize them.</p>
          <button type="button" className="mx-btn primary" onClick={onCancel}>
            Go to matches
          </button>
        </div>
      </section>
    )
  }

  const complete = FIELDS.every(({ key }) => contact[key].trim()) && acceptedBy.trim() !== ''
  const ready = complete && accepted

  function submit(event: FormEvent) {
    event.preventDefault()
    if (ready) {
      onRun(contact, acceptedBy)
    }
  }

  return (
    <section className="mx-view" aria-labelledby="mx-auth-title">
      <header className="mx-header">
        <div>
          <h1 id="mx-auth-title">Authorize auto review / send</h1>
          <p className="mx-sub">Check the matches, read the warning, and confirm you take responsibility.</p>
        </div>
      </header>

      <form className="mx-auth" onSubmit={submit}>
        <div className="mx-panel">
          <h2>
            {cases.length} match{cases.length === 1 ? '' : 'es'} selected
          </h2>
          <ul className="mx-selection">
            {cases.map((item) => (
              <li key={item.id}>
                <img src={item.matched_image_url} alt="" />
                <span className="mx-mono">Match {item.id}</span>
                <span>{hostname(item.page_url)}</span>
                <span className="mx-muted">{item.possible_action.label}</span>
              </li>
            ))}
          </ul>
          <p className="mx-muted">
            The agent reviews each suggestion and may choose a different legal basis, or hold a match for you to
            review.
          </p>
        </div>

        <div className="mx-panel mx-warning">
          <h2>Legal responsibility</h2>
          <p>{WARNING}</p>
        </div>

        <div className="mx-panel">
          <h2>Your contact details</h2>
          <p className="mx-muted">These go on every request in this batch.</p>
          <div className="mx-fields">
            {FIELDS.map((field) => (
              <label key={field.key} className={`mx-field${field.wide ? ' wide' : ''}`}>
                <span>{field.label}</span>
                <input
                  type={field.type ?? 'text'}
                  required
                  value={contact[field.key]}
                  onChange={(event) => setContact({ ...contact, [field.key]: event.target.value })}
                />
              </label>
            ))}
            <label className="mx-field wide">
              <span>Who accepts responsibility</span>
              <input required value={acceptedBy} onChange={(event) => setAcceptedBy(event.target.value)} />
            </label>
          </div>
        </div>

        <label className="mx-accept">
          <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
          <span>I accept the legal-responsibility warning and authorize this batch.</span>
        </label>

        <div className="mx-actions">
          <button type="button" className="mx-btn ghost" onClick={onCancel}>
            Back to matches
          </button>
          <button type="submit" className="mx-btn primary" disabled={!ready}>
            Run batch
          </button>
          {!ready && <span className="mx-muted">Fill in every field and tick the box to continue.</span>}
        </div>
      </form>
    </section>
  )
}

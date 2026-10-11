import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
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
  warning?: string
  personName?: string
  preparing?: boolean
  allowReview?: boolean
  deliveryNote?: string
  busy?: boolean
  cases: Case[]
  onRun: (contact: Contact, acceptedBy: string, mode?: 'prepare' | 'send') => void
  onCancel: () => void
}

export default function AuthorizeBatch({ cases, onRun, onCancel, warning = WARNING, personName = PERSON.name, preparing = false, allowReview = false, deliveryNote = '', busy = false }: Props) {
  const [reviewFirst, setReviewFirst] = useState(false)
  const prepareOnly = preparing || reviewFirst
  const [contact, setContact] = useState<Contact>({
    name: personName,
    email: '',
    address: '',
    phone: '',
    signature: personName,
  })
  const [acceptedBy, setAcceptedBy] = useState(personName)
  const [accepted, setAccepted] = useState(false)

  if (cases.length === 0) {
    return (
      <section className="mx-view">
        <div className="mx-empty">
          <h2>Nothing selected</h2>
          <p>Select one or more matches first, then come back here to authorize them.</p>
          <Button type="button" variant="default" onClick={onCancel}>
            Go to matches
          </Button>
        </div>
      </section>
    )
  }

  const complete = FIELDS.every(({ key }) => contact[key].trim()) && acceptedBy.trim() !== ''
  const ready = complete && accepted

  function submit(event: FormEvent) {
    event.preventDefault()
    if (ready) {
      onRun(contact, acceptedBy, prepareOnly ? 'prepare' : 'send')
    }
  }

  return (
    <section className="mx-view" aria-labelledby="mx-auth-title">
      <header className="mx-header">
        <div>
          <h1 id="mx-auth-title">{prepareOnly ? 'Authorize agent review' : 'Authorize automatic requests'}</h1>
          <p className="mx-sub">Check the matches, read the warning, and confirm you take responsibility.</p>
        </div>
      </header>

      <p className="mx-callout">{prepareOnly
        ? 'You will review every notice before confirming which requests to send.'
        : 'The agent will review these matches and send eligible requests automatically. You will see each decision, recipient and exact notice afterwards. Uncertain cases stop for review.'}</p>
      {deliveryNote && <p className="mx-callout" role="status">{deliveryNote}</p>}
      <form className="mx-auth" onSubmit={submit}>
        <Card className="gap-4 p-6">
          <h2>
            {cases.length} match{cases.length === 1 ? '' : 'es'} selected
          </h2>
          <ul className="mx-selection">
            {cases.map((item) => (
              <li key={item.id}>
                {item.thumbnail_available === false
                  ? <span className="mx-muted" role="img" aria-label="Thumbnail unavailable">—</span>
                  : <img src={item.matched_image_url} alt="Candidate image" />}
                <span className="mx-mono">Match {item.id}</span>
                <span>{hostname(item.page_url)}
                  {item.match_type === 'facecheck' && <span className="mx-muted block text-xs">
                    FaceCheck · Score {item.provider_score} · Not locally verified
                  </span>}
                </span>
                <span className="mx-muted">{item.possible_action.label}</span>
              </li>
            ))}
          </ul>
          <p className="mx-muted">
            The agent reviews each suggestion and may choose a different legal basis, or hold a match for you to
            review.
          </p>
        </Card>

        <Card className="gap-4 p-6 mx-warning">
          <h2>Legal responsibility</h2>
          <p>{warning}</p>
        </Card>

        <Card className="gap-4 p-6">
          <h2>Your contact details</h2>
          <p className="mx-muted">These go on every request in this batch.</p>
          <div className="mx-fields">
            {FIELDS.map((field) => (
              <Label key={field.key} className={`mx-field${field.wide ? ' wide' : ''}`}>
                <span>{field.label}</span>
                <Input
                  type={field.type ?? 'text'}
                  required
                  maxLength={field.key === 'address' ? 1000 : field.key === 'phone' ? 100 : 300}
                  value={contact[field.key]}
                  onChange={(event) => setContact({ ...contact, [field.key]: event.target.value })}
                />
              </Label>
            ))}
            <Label className="mx-field wide">
              <span>Who accepts responsibility</span>
              <Input required maxLength={300} value={acceptedBy} onChange={(event) => setAcceptedBy(event.target.value)} />
            </Label>
          </div>
        </Card>

        <Label className="mx-accept">
          <Checkbox  checked={accepted} onCheckedChange={(checked) => setAccepted(checked === true)} />
          <span>I accept the legal-responsibility warning and authorize this batch.</span>
        </Label>

        {allowReview && <Label className="mx-accept">
          <Checkbox checked={reviewFirst} onCheckedChange={(checked) => setReviewFirst(checked === true)} disabled={busy} />
          <span>Review notices before sending</span>
        </Label>}

        <div className="mx-actions">
          <Button type="button" variant="outline" onClick={onCancel}>
            Back to matches
          </Button>
          <Button type="submit" variant="default" disabled={!ready || busy}>
            {busy ? 'Starting…' : prepareOnly ? 'Prepare requests' : allowReview ? 'Review and send automatically' : 'Run batch'}
          </Button>
          {!ready && <span className="mx-muted">Fill in every field and tick the box to continue.</span>}
        </div>
      </form>
    </section>
  )
}

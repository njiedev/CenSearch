import { useState } from 'react'
import { api } from './api'
import { signOut, type Session } from './session'
import { ErrorBox } from './ui'

function normalizeDomain(value: string) {
  try {
    const url = new URL(value.includes('://') ? value.trim() : `https://${value.trim()}`)
    const host = url.hostname
      .toLowerCase()
      .replace(/^www\./, '')
      .replace(/\.$/, '')
    if (
      !['https:', 'http:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      !host ||
      !/^[a-z0-9.-]+$/.test(host) ||
      host.includes('..') ||
      (host !== 'localhost' &&
        (!host.includes('.') ||
          host.split('.').some((label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))))
    )
      return ''
    return host
  } catch {
    return ''
  }
}
export default function Settings({
  person,
  domains,
  update,
  busy,
}: {
  person: Session
  domains: string[]
  update: (domains: string[]) => Promise<void>
  busy: boolean
}) {
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const normalized = normalizeDomain(input)
  async function add() {
    if (!normalized) {
      setError('Enter a valid domain or public URL.')
      return
    }
    try {
      await update([...new Set([...domains, normalized])])
      setInput('')
      setError('')
    } catch (failure) {
      setError((failure as Error).message)
    }
  }
  async function remove(domain: string) {
    try {
      await update(domains.filter((value) => value !== domain))
      setError('')
    } catch (failure) {
      setError((failure as Error).message)
    }
  }
  async function deleteEnrollment() {
    setDeleting(true)
    try {
      await api.deletePerson(person.id)
      signOut()
    } catch (failure) {
      setError((failure as Error).message)
      setDeleting(false)
    }
  }
  return (
    <section className="app-form-view">
      <h1>Settings</h1>
      <section className="settings-section">
        <h2>Whitelist: sites to leave alone</h2>
        <p>Matches on these sites are marked and the agent will never draft or send a request to them.</p>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void add()
          }}
        >
          <label>
            Site or URL
            <input
              value={input}
              onChange={(event) => {
                setInput(event.target.value)
                setError('')
              }}
              placeholder="example.com"
            />
          </label>
          {input && (
            <p className="muted">
              {normalized ? `Will save: ${normalized}` : 'Enter a valid domain or URL.'}
            </p>
          )}
          <button type="submit" disabled={busy} className="primary">
            {busy ? 'Saving…' : 'Add site'}
          </button>
        </form>
        {domains.length ? (
          <ul className="domain-list">
            {domains.map((domain) => (
              <li key={domain}>
                <span>{domain}</span>
                <button disabled={busy} onClick={() => void remove(domain)} aria-label={`Remove ${domain}`}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No sites on your whitelist yet. Add a site above to leave it alone.</p>
        )}
      </section>
      <section className="settings-section">
        <h2>Enrollment</h2>
        <p>
          Enrolled name: <strong>{person.name}</strong>
        </p>
        <button className="danger" onClick={() => setConfirm(true)}>
          Delete my enrollment
        </button>
        {confirm && (
          <div className="confirmation">
            <h3>Delete your enrollment?</h3>
            <p>
              Your enrolled photos, matches and related records will be deleted. You will be signed out. This
              cannot be undone.
            </p>
            <div className="actions">
              <button className="danger" disabled={deleting} onClick={deleteEnrollment}>
                {deleting ? 'Deleting…' : 'Delete enrollment permanently'}
              </button>
              <button onClick={() => setConfirm(false)} disabled={deleting}>
                Keep enrollment
              </button>
            </div>
          </div>
        )}
      </section>
      {error && <ErrorBox error={error} />}
    </section>
  )
}

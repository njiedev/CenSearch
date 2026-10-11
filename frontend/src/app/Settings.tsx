import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useState } from 'react'
import { api } from './api'
import { signOut } from './session'
import type { Person } from './types'
import Profile from './Profile'
import { ErrorBox } from './ui'

function normalizeDomain(value: string) {
  try {
    if (/[\r\n\t]/.test(value)) return ''
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
  tab,
  onUpdated,
}: {
  person: Person
  domains: string[]
  update: (domains: string[]) => Promise<void>
  busy: boolean
  tab: string
  onUpdated: () => void
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
      <nav className="settings-tabs" aria-label="Settings sections">
        <a href="#settings" aria-current={tab === 'profile' ? 'page' : undefined}>Profile</a>
        <a href="#settings/whitelist" aria-current={tab === 'whitelist' ? 'page' : undefined}>Whitelist <span>{domains.length}</span></a>
      </nav>
      {tab === 'profile' && <Profile person={person} onUpdated={onUpdated} />}
      {tab === 'whitelist' && <Card className="settings-section">
        <h2>Whitelist: sites to leave alone</h2>
        <p>Matches on these sites and their subdomains stay visible, but new drafts and deliveries are blocked. Requests already sent cannot be recalled.</p>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void add()
          }}
        >
          <Label>
            Site or URL
            <Input
              value={input}
              onChange={(event) => {
                setInput(event.target.value)
                setError('')
              }}
              placeholder="example.com"
            />
          </Label>
          {input && (
            <p className="muted">
              {normalized ? `Will save: ${normalized}` : 'Enter a valid domain or URL.'}
            </p>
          )}
          <Button type="submit" disabled={busy} variant="default">
            {busy ? 'Saving…' : 'Add site'}
          </Button>
        </form>
        {domains.length ? (
          <ul className="domain-list">
            {domains.map((domain) => (
              <li key={domain}>
                <span>{domain}</span>
                <Button variant="outline" disabled={busy} onClick={() => void remove(domain)} aria-label={`Remove ${domain}`}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No sites on your whitelist yet. Add a site above to leave it alone.</p>
        )}
      </Card>}
      {tab === 'profile' && <Card className="settings-section">
        <h2>Enrollment</h2>
        <p>
          Enrolled name: <strong>{person.name}</strong>
        </p>
        <Button variant="destructive" onClick={() => setConfirm(true)}>
          Delete my enrollment
        </Button>
        {confirm && (
          <div className="confirmation">
            <h3>Delete your enrollment?</h3>
            <p>
              Your enrolled photos, matches and related records will be deleted. You will be signed out. This
              cannot be undone.
            </p>
            <div className="actions">
              <Button variant="destructive" disabled={deleting} onClick={deleteEnrollment}>
                {deleting ? 'Deleting…' : 'Delete enrollment permanently'}
              </Button>
              <Button variant="outline" onClick={() => setConfirm(false)} disabled={deleting}>
                Keep enrollment
              </Button>
            </div>
          </div>
        )}
      </Card>}
      {error && <ErrorBox error={error} />}
    </section>
  )
}

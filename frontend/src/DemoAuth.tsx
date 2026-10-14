import { useState, type FormEvent } from 'react'
import Logo from './Logo'
import { REFERENCE_PHOTOS } from './demoPhotos'
import { createAccount, logIn, startDemo } from './app/accounts'
import { saveSession } from './app/session'

type Field = 'name' | 'email' | 'password'
type Errors = Partial<Record<Field | 'form', string>>


function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <p className="su-error" id={id}>{message}</p> : null
}

function Input({ field, label, type, autoComplete, value, error, onChange }: {
  field: Field
  label: string
  type: string
  autoComplete: string
  value: string
  error?: string
  onChange: (value: string) => void
}) {
  const id = `su-${field}`
  return (
    <div className="su-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={type}
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      <FieldError id={`${id}-error`} message={error} />
    </div>
  )
}

function useForm(fields: Field[]) {
  const [values, setValues] = useState<Record<Field, string>>({ name: '', email: '', password: '' })
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)
  function set(field: Field) {
    return (value: string) => {
      setValues((current) => ({ ...current, [field]: value }))
      setErrors((current) => ({ ...current, [field]: undefined, form: undefined }))
    }
  }
  function validate() {
    const found: Errors = {}
    if (fields.includes('name') && !values.name.trim()) found.name = 'Enter your name.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) found.email = 'Enter a valid email address.'
    if (values.password.length < 8) found.password = 'Use at least 8 characters.'
    setErrors(found)
    return Object.keys(found).length === 0
  }
  async function submit(event: FormEvent, action: () => Promise<{ id: string; name: string }>) {
    event.preventDefault()
    if (busy || !validate()) return
    setBusy(true)
    try {
      saveSession(await action())
      window.location.assign('/app/')
    } catch (failure) {
      setErrors({ form: (failure as Error).message })
      setBusy(false)
    }
  }
  return { values, errors, busy, set, submit }
}

function DemoNote() {
  return (
    <div className="su-demo-note">
      <p>
        This is a demo. Your account is saved only in this browser, and scans use a sample person's
        photos instead of yours. Nothing is uploaded or sent.
      </p>
      <ul className="su-previews" aria-label="Sample person's face photos">
        {REFERENCE_PHOTOS.map((src, index) => (
          <li key={src}>
            <img src={src} alt={`Sample face photo ${index + 1}`} />
          </li>
        ))}
      </ul>
    </div>
  )
}

export function DemoSignUp() {
  const form = useForm(['name', 'email', 'password'])
  return (
    <form
      className="su-panel"
      onSubmit={(event) => void form.submit(event, () =>
        createAccount(form.values.name, form.values.email, form.values.password))}
      noValidate
    >
      <span className="su-logo"><Logo /></span>
      <h2 className="su-title" id="signup-title">Sign up</h2>
      <DemoNote />
      <Input field="name" label="Name" type="text" autoComplete="name"
        value={form.values.name} error={form.errors.name} onChange={form.set('name')} />
      <Input field="email" label="Email" type="email" autoComplete="email"
        value={form.values.email} error={form.errors.email} onChange={form.set('email')} />
      <Input field="password" label="Password" type="password" autoComplete="new-password"
        value={form.values.password} error={form.errors.password} onChange={form.set('password')} />
      {form.errors.form && <div className="su-failure" role="alert"><p>{form.errors.form}</p></div>}
      <button type="submit" className="su-submit" disabled={form.busy} aria-busy={form.busy}>
        {form.busy ? 'Creating account…' : 'Create account'}
      </button>
      <p className="su-switch">Already have an account? <a href="/login/">Log in</a></p>
      <button type="button" className="su-demo" onClick={startDemo}>Skip and try the demo as a guest</button>
    </form>
  )
}

export function DemoLogIn() {
  const form = useForm(['email', 'password'])
  return (
    <form
      className="su-panel"
      onSubmit={(event) => void form.submit(event, () => logIn(form.values.email, form.values.password))}
      noValidate
    >
      <span className="su-logo"><Logo /></span>
      <h2 className="su-title" id="signup-title">Log in</h2>
      <p className="su-lede">Demo accounts are saved in this browser only.</p>
      <Input field="email" label="Email" type="email" autoComplete="email"
        value={form.values.email} error={form.errors.email} onChange={form.set('email')} />
      <Input field="password" label="Password" type="password" autoComplete="current-password"
        value={form.values.password} error={form.errors.password} onChange={form.set('password')} />
      {form.errors.form && <div className="su-failure" role="alert"><p>{form.errors.form}</p></div>}
      <button type="submit" className="su-submit" disabled={form.busy} aria-busy={form.busy}>
        {form.busy ? 'Logging in…' : 'Log in'}
      </button>
      <p className="su-switch">New here? <a href="/signup/">Create an account</a></p>
      <button type="button" className="su-demo" onClick={startDemo}>Try the demo as a guest</button>
    </form>
  )
}

import { saveSession, type Session } from './session'

// Demo accounts live in this browser's localStorage and never leave it. The
// password is stored as a SHA-256 hash so it isn't kept in plain text, but this
// is not real authentication; anyone with access to the browser can read it.
type Account = { id: string; name: string; email: string; password: string; createdAt: string }

const KEY = 'censearch.accounts'

function accounts(): Account[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

async function hash(password: string) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(password))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

const normalise = (email: string) => email.trim().toLowerCase()

export function findAccount(id: string) {
  return accounts().find((account) => account.id === id)
}

export function deleteAccount(id: string) {
  localStorage.setItem(KEY, JSON.stringify(accounts().filter((account) => account.id !== id)))
}

export async function createAccount(name: string, email: string, password: string): Promise<Session> {
  const all = accounts()
  if (all.some((account) => account.email === normalise(email))) {
    throw new Error('An account with this email already exists in this browser. Log in instead.')
  }
  const account: Account = {
    id: crypto.randomUUID(),
    name: name.trim(),
    email: normalise(email),
    password: await hash(password),
    createdAt: new Date().toISOString(),
  }
  localStorage.setItem(KEY, JSON.stringify([...all, account]))
  return { id: account.id, name: account.name }
}

export async function logIn(email: string, password: string): Promise<Session> {
  const account = accounts().find((row) => row.email === normalise(email))
  if (!account || account.password !== (await hash(password))) {
    throw new Error('That email and password don’t match an account in this browser.')
  }
  return { id: account.id, name: account.name }
}

export function startDemo() {
  saveSession({ id: 'guest', name: 'Guest' })
  window.location.assign('/app/')
}

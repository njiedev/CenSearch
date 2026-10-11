export type Session = { id: string; name: string }
const KEY = 'censearch.session'
export function readSession(): Session | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(KEY) ?? localStorage.getItem(KEY) ?? 'null')
    return typeof value?.id === 'string' && typeof value?.name === 'string' ? value : null
  } catch {
    return null
  }
}
export function saveSession(session: Session) {
  // Each tab keeps its own profile; a new tab starts from the most recent one.
  sessionStorage.setItem(KEY, JSON.stringify(session))
  localStorage.setItem(KEY, JSON.stringify(session))
  sessionStorage.removeItem('censearch.live')
}
export function signOut(destination = '/') {
  sessionStorage.removeItem(KEY)
  localStorage.removeItem(KEY)
  sessionStorage.removeItem('censearch.live')
  window.location.assign(destination)
}

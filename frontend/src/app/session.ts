export type Session = { id: string; name: string }
const KEY = 'censearch.session'
export function readSession(): Session | null {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    return typeof value?.id === 'string' && typeof value?.name === 'string' ? value : null
  } catch {
    return null
  }
}
export function saveSession(session: Session) {
  localStorage.setItem(KEY, JSON.stringify(session))
  sessionStorage.removeItem('censearch.live')
}
export function signOut(destination = '/') {
  localStorage.removeItem(KEY)
  sessionStorage.removeItem('censearch.live')
  window.location.assign(destination)
}

// Cloud builds omit decorative photos; enrollment images use the API.
export function photoUrl(photo: number | string) {
  if (import.meta.env.VITE_PLACEHOLDER_PHOTOS === '1') return '/favicon.svg'
  return `/photos/${String(photo).padStart(2, '0')}.jpg`
}

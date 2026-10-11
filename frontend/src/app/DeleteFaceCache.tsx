import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { api } from './api'

export default function DeleteFaceCache({ personId, onDeleted }: {
  personId: string
  onDeleted: () => void
}) {
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function remove() {
    setBusy(true)
    setError('')
    try {
      await api.deleteFaceCache(personId)
      setConfirm(false)
      onDeleted()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return <div className="grid gap-3">
    {confirm ? <section aria-label="Confirm cache deletion" className="grid gap-3">
      <p>Delete all saved FaceCheck candidates for this person? They cannot be reused afterward.
        Unreviewed FaceCheck cases and thumbnails are deleted. Reviewed cases, other scan results,
        and notice history stay saved. A new search costs 3 credits.</p>
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="destructive" disabled={busy} onClick={() => void remove()}>
          {busy ? 'Deleting…' : 'Confirm delete cache'}
        </Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => setConfirm(false)}>Keep cache</Button>
      </div>
    </section> : <Button type="button" variant="outline" onClick={() => setConfirm(true)}>Delete FaceCheck cache</Button>}
    {error && <p role="alert" className="field-error">{error}</p>}
  </div>
}

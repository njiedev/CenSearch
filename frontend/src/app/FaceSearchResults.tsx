import { Button } from "@/components/ui/button"
import { useState } from 'react'
import { api } from './api'
import type { Run } from './types'
import DeleteFaceCache from './DeleteFaceCache'
import './face-search.css'

export default function FaceSearchResults({ run, onResumed, onDeleted }: {
  run: Run; onResumed?: () => void; onDeleted?: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [deleted, setDeleted] = useState(false)
  const face = deleted && run.facecheck
    ? { ...run.facecheck, status: 'cache_deleted', items: [], id_search: undefined }
    : run.facecheck
  if (!face) return null
  const items = face.items.filter((item) => item.score >= 88 && item.score <= 100)
  const canResume = face.id_search && face.status !== 'completed' &&
    !['running', 'queued'].includes(run.status)
  async function resume() {
    setBusy(true)
    setError('')
    try {
      await api.resumeFaceSearch(run.id)
      if (onResumed) onResumed()
      else location.hash = `scan/${run.id}/running`
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="face-search-results" aria-label="FaceCheck results">
      <h2>FaceCheck candidates · {items.length}</h2>
      {face.status === 'cache_deleted' ? <p role="status">Saved FaceCheck results deleted. Reviewed cases and other scan results are retained.</p>
        : face.retrieved_at && <p>Saved live FaceCheck search · {new Date(face.retrieved_at).toLocaleString()}.
          Results have not been refreshed.</p>}
      <p>Scores 88 or higher only. These are possible matches, not verified identities.
        Select results below to review with the agent.</p>
      {face.status === 'completed' && items.length === 0 && <p>No results scored 88 or higher.</p>}
      {items.length > 0 && (
        <ul>
          {items.map((item, index) => (
            <li key={`${item.url}-${index}`}>
              <strong>Score {item.score}</strong>
              <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a>
            </li>
          ))}
        </ul>
      )}
      {canResume && <>
        <p>The provider search is unfinished. Check this same search again without a new upload or charge.</p>
        <Button variant="outline" type="button" disabled={busy} onClick={() => void resume()}>
          {busy ? 'Checking…' : 'Check existing FaceCheck search'}
        </Button>
      </>}
      {run.person_id && face.status === 'completed' && <DeleteFaceCache personId={run.person_id} onDeleted={() => {
        setDeleted(true)
        onDeleted?.()
      }} />}
      {run.errors.map((item, index) => <p className="field-error" key={index}>
        {item.message || item.error}
      </p>)}
      {error && <p className="field-error" role="alert">{error}</p>}
    </section>
  )
}

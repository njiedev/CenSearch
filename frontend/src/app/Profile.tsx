import { useRef, useState } from 'react'
import { ImagePlus, UserRound, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { api, isSample } from './api'
import type { Person, ProfilePhoto, PhotoKind } from './types'
import { ErrorBox } from './ui'

export default function Profile({ person, onUpdated }: { person: Person; onUpdated: () => void }) {
  const [current, setCurrent] = useState(person)
  const [kind, setKind] = useState<PhotoKind>('reference')
  const [files, setFiles] = useState<File[]>([])
  const [ownership, setOwnership] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [removing, setRemoving] = useState<{ photo: ProfilePhoto; kind: PhotoKind } | null>(null)
  const picker = useRef<HTMLInputElement>(null)
  async function upload(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!files.length || busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const data = new FormData()
      files.forEach((file) => data.append(kind === 'reference' ? 'references' : 'originals', file))
      if (ownership) data.append('ownership', 'I own the copyright to these original photos.')
      const result = await api.addPhotos(current.id, data)
      setCurrent(result.person)
      setFiles([])
      setOwnership(false)
      if (picker.current) picker.current.value = ''
      setNotice(`${result.photos.length} ${result.photos.length === 1 ? 'photo added' : 'photos added'}. Your enrollment has been updated.`)
      onUpdated()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function remove() {
    if (!removing || busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      setCurrent(await api.deletePhoto(current.id, removing.kind, removing.photo.id))
      setRemoving(null)
      setNotice('Photo removed from your enrollment.')
      onUpdated()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function photos(rows: ProfilePhoto[], photoKind: PhotoKind) {
    return rows.length ? <ul className="profile-photos">
      {rows.map((photo) => <li key={photo.id} className="profile-photo">
        <img src={api.photoUrl(current.id, photoKind, photo.id)} alt={`Enrolled photo: ${photo.filename}`} />
        <div className="profile-photo-caption">
          <span title={photo.filename}>{photo.filename}</span>
          <Button variant="outline" size="sm" aria-label={`Remove ${photo.filename}`}
            disabled={busy || (photoKind === 'reference' && rows.length === 1)}
            onClick={() => { setRemoving({ photo, kind: photoKind }); setError('') }}>
            <Trash2 aria-hidden="true" /> Remove
          </Button>
        </div>
        {removing?.photo.id === photo.id && removing.kind === photoKind && <div className="confirmation" role="region" aria-label={`Confirm removing ${photo.filename}`}>
          <strong>Remove this photo?</strong>
          <p>{photoKind === 'original'
            ? 'This deletes the original and its linked matches and request records. Previously sent requests cannot be recalled.'
            : 'This deletes the saved photo and its face data. Future scans will use your remaining photos.'}</p>
          <div className="actions">
            <Button variant="destructive" disabled={busy} onClick={() => void remove()}>{busy ? 'Removing…' : 'Remove photo permanently'}</Button>
            <Button variant="outline" disabled={busy} onClick={() => setRemoving(null)}>Keep photo</Button>
          </div>
        </div>}
      </li>)}
    </ul> : <p className="muted">{photoKind === 'reference' ? 'No face photos to display.' : 'No original photos yet. Add photos you own to find copies, even when your face is hidden.'}</p>
  }
  return <>
    <Card className="settings-section profile-info">
      <div className="profile-identity"><span className="profile-avatar"><UserRound aria-hidden="true" /></span><div><h2>{current.name}</h2><p>{current.development_fixture ? 'Local test enrollment' : 'Your enrollment'}</p></div></div>
      <dl className="profile-facts">
        <div><dt>Enrolled</dt><dd>{current.created_at ? new Date(current.created_at).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' }) : 'Sample profile'}</dd></div>
        <div><dt>Face photos</dt><dd>{current.references.length}</dd></div>
        <div><dt>Original photos</dt><dd>{current.originals.length}</dd></div>
      </dl>
      <details><summary>Enrollment consent</summary><p className="profile-consent">{current.consent || 'No consent recorded in sample mode.'}</p></details>
    </Card>
    <Card className="settings-section">
      <div><h2>Your photos</h2><p>Manage the photos CenSearch uses to find you and copies of your work.</p></div>
      <h3>Face photos</h3>
      {photos(current.references, 'reference')}
      <p className="muted">Keep at least one face photo. To replace the last one, add a new photo first.</p>
      <p className="muted">Local matching uses the first {current.active_reference_count} face {current.active_reference_count === 1 ? 'photo' : 'photos'} in upload order. Face search uses the first face photo.</p>
      <h3>Original photos</h3>
      {photos(current.originals, 'original')}
      <form className="profile-upload" onSubmit={(event) => void upload(event)}>
        <h3><ImagePlus aria-hidden="true" /> Add photos</h3>
        <fieldset disabled={busy || isSample()}>
          <legend>Photo type</legend>
          <div className="profile-kind">
            <Label className="check-row"><input type="radio" name="photo-kind" checked={kind === 'reference'} onChange={() => { setKind('reference'); setError('') }} />Face photos</Label>
            <Label className="check-row"><input type="radio" name="photo-kind" checked={kind === 'original'} onChange={() => { setKind('original'); setError('') }} />Originals I own</Label>
          </div>
          <p className="muted">{kind === 'reference' ? 'Use a clear photo of just your face. Each photo is checked before it is saved.' : 'Add photos for which you own the copyright.'}</p>
          <Label htmlFor="profile-files">Choose photos</Label>
          <Input id="profile-files" ref={picker} type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => { setFiles(Array.from(event.target.files ?? [])); setError(''); setNotice('') }} />
          {files.length > 0 && <p className="profile-filenames">{files.map((file) => file.name).join(', ')}</p>}
          {kind === 'original' && <Label className="profile-ownership check-row"><Checkbox checked={ownership} onCheckedChange={(value) => setOwnership(value === true)} />I own the copyright to these photos.</Label>}
          <Button type="submit" disabled={!files.length || busy || (kind === 'original' && !ownership)}>{busy ? 'Saving photos…' : 'Add photos'}</Button>
        </fieldset>
        <p className="muted">{isSample() ? 'Connect the backend to manage your real photos.' : 'Photos are saved to your enrollment. Adding photos does not start a search or upload them to a search provider.'}</p>
      </form>
      {error && <ErrorBox error={error} />}
      <p className="profile-feedback" role="status">{notice}</p>
    </Card>
  </>
}

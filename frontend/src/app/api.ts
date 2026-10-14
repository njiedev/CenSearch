import { DEMO } from '../demo'
import { REFERENCE_PHOTOS } from '../demoPhotos'
import { sample } from './sample'
import { signOut } from './session'
import type { Batch, BatchRequest, Case, Person, PhotoKind, Run, Scan, SearchRequest, Workflow, WorkflowNotice } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}
function message(body: { error?: { message?: string }; detail?: unknown }, status: number) {
  if (status === 409) return 'Another operation is running. Wait for it to finish, then retry.'
  if (body.error?.message) return body.error.message
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail))
    return body.detail.map((row) => `${row.loc?.slice(1).join('.') || 'Request'}: ${row.msg}`).join(' ')
  return `The server returned ${status}. Please retry.`
}
// In the demo build every call is answered by `fallback` from sample.ts.
async function request<T>(path: string, fallback: () => T, init?: RequestInit): Promise<T> {
  if (DEMO) return fallback()
  let response: Response
  try {
    response = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError(0, 'Connection lost. Your real data is unchanged. Check the backend and retry.')
  }
  const raw = await response.text()
  let body
  try {
    body = raw ? JSON.parse(raw) : null
  } catch {
    body = null
  }
  if (!response.ok) throw new ApiError(response.status, message(body ?? {}, response.status))
  return body as T
}
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
})
const personPath = (id: string) => `/people/${encodeURIComponent(id)}`
function liveOnly(): never {
  throw new ApiError(503, 'Checking removal and follow-up need the backend; they are not part of the demo.')
}
function photosLiveOnly(): never {
  throw new ApiError(503, 'Photos can’t be changed in the demo.')
}
export const api = {
  workflow: (id: number) => request<Workflow>(`/cases/${id}/workflow`, liveOnly),
  verify: (id: number) => request(`/cases/${id}/verify`, liveOnly, json('POST')),
  advanceClock: () => request('/clock/advance', liveOnly, json('POST', { seconds: 172801 })),
  recipients: (id: number) => request(`/cases/${id}/recipients`, liveOnly, json('POST')),
  approveDraft: (id: number, revision: number, rung: string, approvedBy: string) =>
    request(`/cases/${id}/approve-draft`, liveOnly, json('POST', { revision, rung, approved_by: approvedBy })),
  draft: (id: number, recipientId: string, rung: string) =>
    request<WorkflowNotice>(`/cases/${id}/draft`, liveOnly, json('POST', { recipient_id: recipientId, rung })),
  approveNotice: (id: number, notice: WorkflowNotice, approvedBy: string) =>
    request(`/cases/${id}/approve`, liveOnly, json('POST', {
      notice_id: notice.id, sha256: notice.sha256, approved_by: approvedBy,
    })),
  sendNotice: (id: number) => request(`/cases/${id}/send`, liveOnly, json('POST')),
  person: async (id: string): Promise<Person> => {
    try {
      return await request(personPath(id), () => sample.person(id))
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) signOut('/signup/')
      throw error
    }
  },
  photoUrl: (id: string, kind: PhotoKind, photoId: number) =>
    DEMO ? REFERENCE_PHOTOS[photoId - 1] : `/api${personPath(id)}/photos/${kind}/${photoId}`,
  addPhotos: (id: string, body: FormData) => request<{ person: Person; photos: unknown[] }>(
    `${personPath(id)}/photos`, photosLiveOnly, { method: 'POST', body },
  ),
  deletePhoto: (id: string, kind: PhotoKind, photoId: number) => request<Person>(
    `${personPath(id)}/photos/${kind}/${photoId}`, photosLiveOnly, json('DELETE'),
  ),
  scans: (id: string) => request<Scan[]>(`${personPath(id)}/scans`, sample.scans),
  cases: (id: string, run?: number) =>
    request<Case[]>(
      `/cases?${new URLSearchParams({ person_id: id, ...(run ? { run_id: String(run) } : {}) })}`,
      () => sample.cases(run),
    ),
  whitelist: (id: string) => request(`${personPath(id)}/whitelist`, sample.whitelist),
  putWhitelist: (id: string, domains: string[]) =>
    request(`${personPath(id)}/whitelist`, () => sample.putWhitelist(domains), json('PUT', { domains })),
  deletePerson: (id: string) => request(`${personPath(id)}`, sample.deletePerson, json('DELETE')),
  startScan: (body: SearchRequest) =>
    request<Run>('/public-searches', () => sample.start(body), json('POST', body)),
  run: (id: number) => request<Run>(`/public-searches/${id}`, () => sample.run(id)),
  cancel: (id: number) =>
    request<Run>(`/public-searches/${id}/cancel`, () => sample.cancel(id), json('POST')),
  resumeFaceSearch: (id: number) =>
    request<Run>(`/public-searches/${id}/resume`, () => sample.run(id), json('POST')),
  deleteFaceCache: (id: string) =>
    request<{ deleted: number }>(`${personPath(id)}/face-search-cache`, () => ({ deleted: 0 }), json('DELETE')),
  warning: () => request<{ warning: string; email_delivery?: { ready: boolean } }>('/batches/warning', sample.warning),
  prepare: (body: BatchRequest) => request<Batch>('/batches', () => sample.prepare(body), json('POST', body)),
  batch: (id: string) => request<Batch>(`/batches/${encodeURIComponent(id)}`, () => sample.batch(id)),
  send: (id: string, ids: number[]) =>
    request<Batch>(
      `/batches/${encodeURIComponent(id)}/send`,
      () => sample.send(id, ids),
      json('POST', { case_ids: ids }),
    ),
}

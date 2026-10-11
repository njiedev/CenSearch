import type { Batch, Case, Contact } from '../matches/types'
export type { Batch, Case, Contact }
export type Scan = {
  run_id: number
  kind: 'public_search' | 'crawl'
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  finished_at: string | null
  label: string
  pages_fetched: number
  images_checked: number
  match_count: number
  possible_count: number
  whitelisted_count: number
}
export type Run = {
  id: number
  person_id?: string
  status: string
  started_at: string
  finished_at: string | null
  metrics: Record<string, number>
  pages?: { fetched_at?: string | null }[]
  results: Case[]
  errors: { message?: string; error?: string; url?: string }[]
  facecheck?: {
    status: string
    id_search?: string
    progress?: number | null
    min_score?: number
    score_above?: number
    testing_mode: boolean
    retrieved_at?: string
    items: { url: string; score: number; label: string }[]
  } | null
}
export type SearchRequest = {
  person_id: string
  full_name: string
  handles: string[]
  context: string
  supplied_urls: string[]
  mode: 'name_search' | 'supplied_urls' | 'combined' | 'face_search'
  allow_public_fetch: boolean
  facecheck_consent?: boolean
}
export type BatchRequest = {
  case_ids: number[]
  contact: Contact
  accepted_by: string
  accepted_warning: true
  mode: 'prepare' | 'send'
}

export type WorkflowNotice = {
  id: number
  sha256: string
  rung: string
  recipient: { id: string; address: string; channel: string; endpoint: string }
  payload: { body: string }
}
export type Workflow = {
  case_id: number
  state: string
  revision: number
  next_rung: 'site' | 'host' | 'search'
  demo_clock: boolean
  contact: { name?: string; signature?: string }
  lookup: { recipients?: (WorkflowNotice['recipient'] & { rung: string })[] } | null
  notices: WorkflowNotice[]
  deliveries: { notice_id: number; rung: string; status: string; deadline: string;
    response?: { provider_id?: string; transport?: string } }[]
  checks: { outcome: string; checked_at: string; source_removed: boolean }[]
}

export type PhotoKind = 'reference' | 'original'
export type ProfilePhoto = { id: number; filename: string; ownership_statement?: string }
export type Person = {
  id: string
  name: string
  consent: string
  created_at: string
  development_fixture: boolean
  references: ProfilePhoto[]
  originals: ProfilePhoto[]
  active_reference_count: number
}

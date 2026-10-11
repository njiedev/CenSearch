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
  status: string
  started_at: string
  finished_at: string | null
  metrics: Record<string, number>
  pages?: { fetched_at?: string | null }[]
  results: Case[]
  errors: { message?: string; error?: string; url?: string }[]
}
export type SearchRequest = {
  person_id: string
  full_name: string
  handles: string[]
  context: string
  supplied_urls: string[]
  mode: 'name_search' | 'supplied_urls' | 'combined'
  allow_public_fetch: true
}
export type BatchRequest = {
  case_ids: number[]
  contact: Contact
  accepted_by: string
  accepted_warning: true
  mode: 'prepare'
}

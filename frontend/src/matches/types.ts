// Shapes follow the backend's case and batch responses (backend/handoff/openapi.json,
// backend/censearch/batches.py), trimmed to what these screens read.

export type Route =
  | 'copyright_notice'
  | 'impersonation_report'
  | 'intimate_image_report'
  | 'privacy_request'
  | 'leave_alone'
  | 'hold_for_review'

export type Stage = 'queued' | 'reviewing' | 'capturing' | 'researching' | 'drafting' | 'sending'
export type Outcome = 'sent' | 'drafted_not_sent' | 'left_alone' | 'held_for_review' | 'failed'
export type ItemStatus = Stage | Outcome

export type Action = {
  route: Route
  label: string
  reason: string
  source: 'agent' | 'rule_fallback'
  model_status: string
  possible: boolean
}

export type Recipient = {
  address: string
  channel: 'email' | 'web_form' | 'manual_email' | 'manual_web'
  endpoint: string
}

export type Notice = {
  id: number
  payload: { body: string }
  recipient: Recipient
}

export type Case = {
  id: number
  page_url: string
  matched_image_url: string
  band: 'match' | 'possible'
  state: string
  possible_action: Action
  batch_outcome: { status: ItemStatus; reason: string; decision?: Action } | null
  drafted_request: Notice | null
  deliveries: { notice_id: number; status: string }[]
}

export type ViewState = 'data' | 'loading' | 'empty' | 'error'

export type BatchItem = { case_id: number; status: ItemStatus; reason: string }

export type Batch = {
  id: number
  status: 'queued' | 'running' | 'completed'
  total: number
  completed: number
  items: BatchItem[]
}

export type Contact = {
  name: string
  email: string
  address: string
  phone: string
  signature: string
}

export const TERMINAL: ItemStatus[] = ['sent', 'drafted_not_sent', 'left_alone', 'held_for_review', 'failed']

export function hostname(url: string) {
  return new URL(url).hostname
}

export function isManual(recipient: Recipient) {
  return recipient.channel.startsWith('manual')
}

import { PLANS, finalDecision, noticeBody } from './mockData'
import type { Batch, Case, Contact, ItemStatus } from './types'
import { TERMINAL } from './types'

export function statusOf(item: Case): ItemStatus | 'new' {
  return item.batch_outcome?.status ?? 'new'
}

// Once a batch has decided, show its decision; before that, the suggestion.
export function actionOf(item: Case) {
  return item.batch_outcome?.decision ?? item.possible_action
}

// MOCK BATCH. The real app polls GET /api/batches/{id} instead.

export const STAGE_REASON: Partial<Record<ItemStatus, string>> = {
  queued: 'Waiting to start.',
  reviewing: 'Choosing the legal basis.',
  capturing: 'Saving a screenshot and evidence bundle.',
  researching: 'Finding who handles removal requests.',
  drafting: 'Filling in the fixed notice template.',
  sending: 'Sending to the test site.',
}

// The steps each mock outcome passes through before it ends.
export function pathFor(caseId: number): ItemStatus[] {
  const outcome = PLANS[caseId].outcome
  if (outcome === 'sent') {
    return ['reviewing', 'capturing', 'researching', 'drafting', 'sending', 'sent']
  }
  if (outcome === 'drafted_not_sent') {
    return ['reviewing', 'capturing', 'researching', 'drafting', 'drafted_not_sent']
  }
  if (outcome === 'failed') {
    return ['reviewing', 'capturing', 'researching', 'failed']
  }
  return ['reviewing', outcome]
}

// The furthest working step an item got to, even after it finished.
export function reachedStep(caseId: number, status: ItemStatus): ItemStatus {
  if (!TERMINAL.includes(status)) {
    return status
  }
  const path = pathFor(caseId)
  return path[path.length - 2]
}

// Applies batch progress to a case, the way the backend updates cases.
export function withBatch(row: Case, batch: Batch | null, contact: Contact | null): Case {
  const item = batch?.items.find((entry) => entry.case_id === row.id)
  if (!item) {
    return row
  }
  const plan = PLANS[row.id]
  const finished = TERMINAL.includes(item.status)
  const updated: Case = {
    ...row,
    batch_outcome: {
      status: item.status,
      reason: item.reason,
      decision: finished ? finalDecision(plan.route, row.possible_action.reason) : undefined,
    },
  }
  if (finished && plan.recipient && contact) {
    const id = row.id * 100
    updated.drafted_request = {
      id,
      payload: { body: noticeBody(plan.route, row.page_url, row.matched_image_url, contact) },
      recipient: plan.recipient,
    }
    updated.deliveries = plan.outcome === 'sent' ? [{ notice_id: id, status: 'acted' }] : []
  }
  return updated
}

import { PLANS, WARNING, finalDecision, noticeBody, sampleCases } from '../matches/mockData'
import { prepareSampleItem, STAGE_REASON } from '../matches/logic'
import { TERMINAL, hostname } from '../matches/types'
import { deleteAccount, findAccount } from './accounts'
import { readSession } from './session'
import type { Batch, BatchRequest, Case, Person, Run, Scan, SearchRequest } from './types'

// The browser-only demo backend. Each demo account keeps its scans and batches
// in localStorage; scans and deliveries are simulated on timers.
const KEY = `censearch.demo.${readSession()?.id ?? 'guest'}`
type SampleBatch = { view: Batch; started: number; request: BatchRequest; scan: number }
type State = {
  scans: Scan[]
  cases: Record<number, Case[]>
  runs: Record<number, Run>
  domains: string[]
  batches: Record<string, SampleBatch>
}
function initial(): State {
  return { scans: [], cases: {}, runs: {}, domains: [], batches: {} }
}
function read(): State {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? 'null') ?? initial()
  } catch {
    return initial()
  }
}
let state = read()
function save() {
  localStorage.setItem(KEY, JSON.stringify(state))
}
const REFERENCES = [1, 2, 3].map((id) => ({ id, filename: `sample-face-${id}.jpg` }))
function marked(rows: Case[]) {
  return rows.map((row) => ({
    ...row,
    whitelisted: state.domains.some(
      (domain) => hostname(row.page_url) === domain || hostname(row.page_url).endsWith(`.${domain}`),
    ),
  }))
}
export const sample = {
  person: (id: string): Person => {
    const account = findAccount(id)
    return {
      id,
      name: account?.name ?? 'Guest',
      consent: 'Demo account. The face photos belong to a sample person and stay in this browser.',
      created_at: account?.createdAt ?? '',
      development_fixture: false,
      references: REFERENCES,
      originals: [],
      active_reference_count: REFERENCES.length,
    }
  },
  warning: () => ({ warning: WARNING }),
  scans: () =>
    state.scans.map((row) => ({
      ...row,
      whitelisted_count: marked(state.cases[row.run_id] ?? []).filter((item) => item.whitelisted).length,
    })),
  cases: (run?: number) => marked(run ? (state.cases[run] ?? []) : Object.values(state.cases).flat()),
  whitelist: () => ({ domains: state.domains }),
  putWhitelist: (domains: string[]) => {
    state.domains = [...new Set(domains)]
    save()
    return { domains: state.domains }
  },
  deletePerson: () => {
    const id = readSession()?.id ?? 'guest'
    deleteAccount(id)
    localStorage.removeItem(KEY)
    state = initial()
    return { deleted: id }
  },
  start: (request: SearchRequest): Run => {
    const id = Math.max(...state.scans.map((row) => row.run_id), 0) + 1
    const started = new Date().toISOString()
    const run: Run = {
      id,
      status: 'running',
      started_at: started,
      finished_at: null,
      metrics: {},
      results: [],
      errors: [],
    }
    state.runs[id] = run
    // IDs are unique across sample scans; plans remain based on their eight sample positions.
    state.cases[id] = sampleCases(started).map((row) => ({ ...row, id: (id - 1) * 8 + row.id }))
    state.scans.unshift({
      run_id: id,
      kind: 'public_search',
      status: 'running',
      started_at: started,
      finished_at: null,
      label: request.mode === 'face_search'
        ? 'Face search'
        : request.full_name || request.handles[0] || 'Supplied public pages',
      pages_fetched: 0,
      images_checked: 0,
      match_count: 0,
      possible_count: 0,
      whitelisted_count: 0,
    })
    save()
    return structuredClone(run)
  },
  run: (id: number): Run => {
    const run = state.runs[id]
    if (!run) throw new Error('Sample scan not found. Start a new scan.')
    const scan = state.scans.find((row) => row.run_id === id)!
    if (run.status === 'running') {
      const elapsed = Date.now() - Date.parse(run.started_at)
      const fraction = Math.min(elapsed / 16000, 1)
      run.metrics = {
        pages: Math.floor(fraction * 24),
        analysed: Math.floor(fraction * 86),
        matches: Math.floor(fraction * 8),
      }
      run.results = state.cases[id].slice(0, run.metrics.matches)
      Object.assign(scan, {
        pages_fetched: run.metrics.pages,
        images_checked: run.metrics.analysed,
        match_count: run.results.filter((row) => row.band === 'match').length,
        possible_count: run.results.filter((row) => row.band === 'possible').length,
      })
      if (fraction === 1) {
        run.status = scan.status = 'completed'
        run.finished_at = scan.finished_at = new Date().toISOString()
      }
      save()
    }
    return structuredClone(run)
  },
  cancel: (id: number) => {
    const run = sample.run(id)
    run.status = 'cancelled'
    run.finished_at = new Date().toISOString()
    state.runs[id] = run
    state.cases[id] = run.results
    Object.assign(state.scans.find((row) => row.run_id === id)!, {
      status: 'cancelled',
      finished_at: run.finished_at,
    })
    save()
    return run
  },
  prepare: (request: BatchRequest): Batch => {
    const scan = Number(
      Object.keys(state.cases).find((key) =>
        state.cases[Number(key)].some((row) => row.id === request.case_ids[0]),
      ),
    )
    if (sample.cases(scan).some((row) => request.case_ids.includes(row.id) && row.whitelisted))
      throw new Error('Remove whitelisted matches from your selection.')
    const id = `sample-${Date.now()}`
    const view: Batch = {
      id,
      mode: request.mode,
      phase: 'preparing',
      status: 'running',
      total: request.case_ids.length,
      completed: 0,
      items: request.case_ids.map((case_id) => ({ case_id, status: 'queued', reason: 'Waiting to start.' })),
    }
    state.batches[id] = { view, started: Date.now(), request, scan }
    save()
    return structuredClone(view)
  },
  batch: (id: string): Batch => {
    const entry = state.batches[id]
    if (!entry) throw new Error('Sample batch not found. Return to your scan.')
    const { view, request } = entry
    if (view.phase === 'preparing') {
      const step = Math.floor((Date.now() - entry.started) / 1100)
      view.items.forEach((item) => {
        const planId = ((item.case_id - 1) % 8) + 1
        const plan = PLANS[planId]
        item.status = prepareSampleItem(planId, step)
        if (request.mode === 'send' && item.status === 'ready_to_send') item.status = 'sent'
        item.reason =
          item.status === 'sent'
            ? 'Simulated email delivery. No network request was sent.'
            : item.status === 'ready_to_send'
            ? 'Draft ready. Nothing sent.'
            : (STAGE_REASON[item.status] ?? plan.reason)
        const row = state.cases[entry.scan].find((row) => row.id === item.case_id)!
        item.decision = finalDecision(plan.route, plan.reason)
        row.batch_outcome = { ...item, decision: item.decision }
        if ((TERMINAL.includes(item.status) || item.status === 'ready_to_send') && plan.recipient) {
          row.drafted_request = {
            id: row.id * 100,
            recipient: plan.recipient,
            payload: { body: noticeBody(plan.route, row.page_url, row.matched_image_url, request.contact) },
          }
          row.recipients = [
            { ...plan.recipient, evidence: 'Sample contact found on the sample site policy page.' },
          ]
        }
      })
      if (view.items.every((item) => TERMINAL.includes(item.status) || item.status === 'ready_to_send')) {
        view.phase = view.items.some((item) => item.status === 'ready_to_send') ? 'awaiting_review' : 'done'
        view.status = 'completed'
      }
    } else if (view.phase === 'sending' && Date.now() - entry.started > 1800) {
      view.items.forEach((item) => {
        if (item.status === 'sending') {
          item.status = 'sent'
          item.reason = 'Simulated delivery to a test site. No network request was sent.'
        }
        const row = state.cases[entry.scan].find((row) => row.id === item.case_id)!
        row.batch_outcome = { ...item, decision: item.decision }
      })
      view.phase = 'done'
      view.status = 'completed'
    }
    view.completed = view.items.filter((item) => TERMINAL.includes(item.status)).length
    save()
    return structuredClone(view)
  },
  send: (id: string, ids: number[]): Batch => {
    const entry = state.batches[id]
    if (entry.view.phase !== 'awaiting_review')
      throw new Error('This batch is no longer awaiting review. Refresh it.')
    entry.view.items.forEach((item) => {
      if (item.status === 'ready_to_send') {
        const row = sample.cases(entry.scan).find((row) => row.id === item.case_id)!
        item.status = row.whitelisted
          ? 'left_alone'
          : ids.includes(item.case_id)
            ? 'sending'
            : 'drafted_not_sent'
        item.reason = row.whitelisted
          ? 'Site is on your whitelist.'
          : ids.includes(item.case_id)
            ? 'Sending to test site…'
            : 'You left this request out. Nothing sent.'
      }
    })
    entry.view.phase = 'sending'
    entry.view.status = 'running'
    entry.started = Date.now()
    save()
    return structuredClone(entry.view)
  },
}

import { MATCH_PHOTOS } from '../demoPhotos'
import type { Action, Case, Contact, Outcome, Recipient, Route } from './types'

// MOCK DATA for the browser-only demo. Labels, the warning and the notice
// wording are copied from backend/censearch. The photos are of one sample
// person (public/demo); the pages and outcomes are made up.

export const LABELS: Record<Route, string> = {
  copyright_notice: 'Copyright notice (DMCA 512(c))',
  impersonation_report: 'Impersonation report (platform policy)',
  intimate_image_report: 'Intimate-image removal (platform policy)',
  privacy_request: 'Privacy removal request',
  leave_alone: 'Leave alone',
  hold_for_review: 'Hold for review',
}

export const WARNING =
  'The agent will choose the legal basis and send requests on your behalf. ' +
  'Some notices contain statements made under penalty of perjury. ' +
  'Legal responsibility for what is sent lies with you. ' +
  'By accepting, you authorize this batch and accept the facts in the selected fixed templates: ' +
  'you are the depicted person, the information is accurate and the use is not authorized; ' +
  'for copyright, you own the identified enrolled original, believe in good faith the use lacks ' +
  'permission or legal authorization, and are authorized to act for the owner under penalty of perjury; ' +
  'for impersonation or intimate-image reports, you accept the corresponding description of the use.'

const TEMPLATES: Partial<Record<Route, string>> = {
  copyright_notice:
    'I have a good faith belief that the use complained of is not authorized by the copyright owner, ' +
    'its agent, or the law.\nThe information in this notice is accurate. Under penalty of perjury, I am ' +
    'authorized to act on behalf of the owner of the exclusive right allegedly infringed.\nPlease remove ' +
    'or disable access to the identified material under 17 U.S.C. 512(c)(3).',
  impersonation_report:
    'I confirm this page impersonates me without my authorization. ' +
    'Please review it under your impersonation policy.',
  privacy_request:
    'I am the depicted person and request removal for privacy reasons. This is a voluntary request ' +
    'and does not assert copyright ownership or a statutory removal duty.',
}

export const PERSON = { name: 'John Doe' }

const image = (index: number) => MATCH_PHOTOS[index - 1]

function action(route: Route, reason: string, possible = true): Action {
  return {
    route,
    label: LABELS[route],
    reason,
    source: 'rule_fallback',
    model_status: 'model_not_configured',
    possible,
  }
}

const COPY = 'An exact or derived copy matches an enrolled original photo.'
const PRIVACY = 'A face match on a different photo supports a voluntary privacy request only.'
const UNCERTAIN = 'The photo relationship or original ownership evidence is uncertain.'
const IMPERSONATION = 'A profile uses your face and name and presents itself as you.'

export const CASES: Case[] = [
  {
    id: 1,
    page_url: 'http://pixboard.example/gallery/summer-17',
    matched_image_url: image(1),
    band: 'match',
    state: 'new',
    possible_action: action('copyright_notice', COPY),
  },
  {
    id: 2,
    page_url: 'http://friendlink.example/u/john.doe.official',
    matched_image_url: image(2),
    band: 'match',
    state: 'new',
    possible_action: action('impersonation_report', IMPERSONATION),
  },
  {
    id: 3,
    page_url: 'http://localnews.example/2026/09/street-festival-recap',
    matched_image_url: image(3),
    band: 'possible',
    state: 'new',
    possible_action: action('hold_for_review', UNCERTAIN),
  },
  {
    id: 4,
    page_url: 'http://shadygallery.example/sets/candid-412',
    matched_image_url: image(4),
    band: 'match',
    state: 'new',
    possible_action: action('copyright_notice', COPY),
  },
  {
    id: 5,
    page_url: 'https://streetstyle.example/posts/downtown-looks',
    matched_image_url: image(5),
    band: 'match',
    state: 'new',
    possible_action: action('privacy_request', PRIVACY),
  },
  {
    id: 6,
    page_url: 'http://friendlink.example/groups/campus-2025',
    matched_image_url: image(6),
    band: 'possible',
    state: 'new',
    possible_action: action('privacy_request', PRIVACY),
  },
  {
    id: 7,
    page_url: 'http://pixboard.example/boards/faces-of-the-city',
    matched_image_url: image(7),
    band: 'match',
    state: 'new',
    possible_action: action('privacy_request', PRIVACY),
  },
  {
    id: 8,
    page_url: 'http://localnews.example/2026/10/council-meeting',
    matched_image_url: image(8),
    band: 'possible',
    state: 'new',
    possible_action: action('hold_for_review', UNCERTAIN),
  },
].map((item) => ({ ...item, batch_outcome: null, drafted_request: null, deliveries: [] }) as Case)

// What the mock batch ends with for each case. A real batch decides this.
type Plan = { outcome: Outcome; reason: string; route: Route; recipient?: Recipient }

export const PLANS: Record<number, Plan> = {
  1: {
    outcome: 'sent',
    route: 'copyright_notice',
    reason: 'Sent to the site’s listed copyright agent.',
    recipient: { address: 'copyright@pixboard.example', channel: 'email', endpoint: 'smtp://127.0.0.1:8818' },
  },
  2: {
    outcome: 'sent',
    route: 'impersonation_report',
    reason: 'Sent through the site’s impersonation report form.',
    recipient: {
      address: 'friendlink.example impersonation form',
      channel: 'web_form',
      endpoint: 'http://friendlink.example/report/impersonation',
    },
  },
  3: {
    outcome: 'held_for_review',
    route: 'hold_for_review',
    reason: 'Possible match on a news page. Held so you can check it yourself.',
  },
  4: {
    outcome: 'sent',
    route: 'copyright_notice',
    reason: 'Sent to the host’s abuse contact; the site lists no agent.',
    recipient: { address: 'abuse@host.example', channel: 'email', endpoint: 'smtp://127.0.0.1:8818' },
  },
  5: {
    outcome: 'drafted_not_sent',
    route: 'privacy_request',
    reason: 'Real website: the request is drafted with a named recipient. You send it yourself.',
    recipient: {
      address: 'support@streetstyle.example',
      channel: 'manual_email',
      endpoint: 'mailto:support@streetstyle.example',
    },
  },
  6: {
    outcome: 'left_alone',
    route: 'leave_alone',
    reason: 'Possible match only, in a group photo. Not strong enough to send a request.',
  },
  7: {
    outcome: 'failed',
    route: 'privacy_request',
    reason: 'Couldn’t find a contact: the site’s policy page didn’t load.',
  },
  8: {
    outcome: 'held_for_review',
    route: 'hold_for_review',
    reason: 'Possible match only. Held so you can check it yourself.',
  },
}

export function noticeBody(route: Route, pageUrl: string, imageUrl: string, contact: Contact) {
  const template = TEMPLATES[route] ?? TEMPLATES.privacy_request!
  const signature = [
    `Name: ${contact.name}`,
    `Email: ${contact.email}`,
    `Address: ${contact.address}`,
    `Phone: ${contact.phone}`,
    `Signature: ${contact.signature}`,
  ]
  return [`Page: ${pageUrl}`, `Image: ${imageUrl}`, '', template, '', ...signature].join('\n')
}

export function finalDecision(route: Route, reason: string) {
  return action(route, reason, false)
}

export function sampleCases(startedAt: string): Case[] {
  return CASES.map((row) => ({ ...structuredClone(row), created_at: startedAt, whitelisted: false }))
}

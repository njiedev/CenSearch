import type { ItemStatus } from './types'

// Every status has text and an icon, never color alone. Tones follow Carbon:
// green done, blue in progress or info, yellow needs you, gray neutral, red error.
type Tone = 'done' | 'progress' | 'info' | 'attention' | 'neutral' | 'error'

const STATUS: Record<ItemStatus | 'new', { label: string; icon: string; tone: Tone }> = {
  new: { label: 'Not reviewed', icon: '○', tone: 'neutral' },
  queued: { label: 'Queued', icon: '…', tone: 'progress' },
  reviewing: { label: 'Reviewing', icon: '◔', tone: 'progress' },
  capturing: { label: 'Capturing evidence', icon: '◑', tone: 'progress' },
  researching: { label: 'Finding recipient', icon: '◕', tone: 'progress' },
  drafting: { label: 'Drafting', icon: '✎', tone: 'progress' },
  sending: { label: 'Sending', icon: '➜', tone: 'progress' },
  ready_to_send: { label: 'Ready to send', icon: '□', tone: 'neutral' },
  sent: { label: 'Sent', icon: '✓', tone: 'done' },
  drafted_not_sent: { label: 'Drafted, send it yourself', icon: '✉', tone: 'info' },
  left_alone: { label: 'Left alone', icon: '–', tone: 'neutral' },
  held_for_review: { label: 'Held for review', icon: '!', tone: 'attention' },
  failed: { label: 'Failed', icon: '✕', tone: 'error' },
}

export function StatusPill({ status }: { status: ItemStatus | 'new' }) {
  const info = STATUS[status]
  return (
    <span className={`mx-status tone-${info.tone}`}>
      <span aria-hidden="true">{info.icon}</span>
      {info.label}
    </span>
  )
}

export function ErrorBox({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="app-error" role="alert">
      <strong>Something needs attention</strong>
      <p>{error}</p>
      {retry && <button onClick={retry}>Retry</button>}
    </div>
  )
}
export function Empty({
  title,
  children,
  action,
  onAction,
}: {
  title: string
  children: React.ReactNode
  action: string
  onAction: () => void
}) {
  return (
    <section className="app-empty">
      <h2>{title}</h2>
      <p>{children}</p>
      <button className="primary" onClick={onAction}>
        {action}
      </button>
    </section>
  )
}
export function Loading() {
  return (
    <div className="app-loading" role="status" aria-label="Loading">
      <div />
      <div />
      <div />
      <span className="visually-hidden">Loading…</span>
    </div>
  )
}
export function ScanStatus({ status }: { status: string }) {
  const icon = status === 'completed' ? '✓' : status === 'failed' ? '✕' : status === 'cancelled' ? '–' : '◔'
  const tone =
    status === 'completed'
      ? 'done'
      : status === 'failed'
        ? 'error'
        : status === 'cancelled'
          ? 'neutral'
          : 'progress'
  return (
    <span className={`mx-status tone-${tone}`}>
      <span aria-hidden="true">{icon}</span>
      {status.replaceAll('_', ' ')}
    </span>
  )
}

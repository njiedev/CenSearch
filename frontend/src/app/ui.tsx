import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from "@/components/ui/button"
import { Check, CircleDashed, Minus, X } from 'lucide-react'
export function ErrorBox({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <Alert variant="destructive" className="app-error my-4">
      <AlertTitle>Something needs attention</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
      {retry && <Button type="button" variant="outline" className="col-start-2 mt-2 w-fit" onClick={retry}>Retry</Button>}
    </Alert>
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
      <Button variant="default" onClick={onAction}>
        {action}
      </Button>
    </section>
  )
}
export function Loading() {
  return (
    <div className="app-loading grid gap-4" role="status" aria-label="Loading">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-8 w-2/3" />
      <span className="visually-hidden">Loading…</span>
    </div>
  )
}
export function ScanStatus({ status }: { status: string }) {
  const Icon = status === 'completed' ? Check : status === 'failed' ? X : status === 'cancelled' ? Minus : CircleDashed
  const tone =
    status === 'completed'
      ? 'done'
      : status === 'failed'
        ? 'error'
        : status === 'cancelled'
          ? 'neutral'
          : 'progress'
  return (
    <Badge variant="outline" className={`tone-${tone}`}>
      <Icon aria-hidden="true" />
      {status.replaceAll('_', ' ')}
    </Badge>
  )
}

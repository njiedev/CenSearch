import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from '@/components/ui/sidebar'
import { Home, Plus, ListFilter, Settings as SettingsIcon, ScanLine, LogOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import Logo from '../Logo'
import AuthorizeBatch from '../matches/AuthorizeBatch'
import { hostname } from '../matches/types'
import { DEMO } from '../demo'
import { api } from './api'
import { readSession, signOut, type Session } from './session'
import type { Case, Contact, Scan } from './types'
import { ErrorBox, Loading, ScanStatus } from './ui'
import { relative, usePoll } from './hooks'
import NewScan from './NewScan'
import Scanning from './Scanning'
import ScanDetail from './ScanDetail'
import AllScans from './AllScans'
import Settings from './Settings'
import BatchReview from './BatchReview'

function currentRoute() {
  return location.hash.slice(1) || 'home'
}
function navigate(route: string) {
  location.hash = route
}
export default function App() {
  return <SidebarProvider className="app-shell"><Dashboard /></SidebarProvider>
}
function Dashboard() {
  const [session] = useState<Session | null>(readSession)
  const [route, setRoute] = useState(currentRoute)
  const { state, setOpenMobile } = useSidebar()
  const main = useRef<HTMLDivElement>(null)
  const [version, setVersion] = useState(0)
  const refresh = () => setVersion((value) => value + 1)
  const [domains, setDomains] = useState<string[]>([])
  const [whiteBusy, setWhiteBusy] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selection, setSelection] = useState<number[]>([])
  const [warning, setWarning] = useState('')
  const [deliveryNote, setDeliveryNote] = useState('')
  const [warningError, setWarningError] = useState('')
  const parts = route.split('/')
  const runId = parts[0] === 'scan' ? Number(parts[1]) : undefined
  const batchId = parts[2] === 'batch' ? parts[3] : undefined
  const data = usePoll(
    async () => {
      if (!session) return null
      const person = await api.person(session.id)
      const [scans, cases, whitelist] = await Promise.all([
        api.scans(session.id),
        api.cases(session.id),
        api.whitelist(session.id),
      ])
      setDomains(whitelist.domains)
      return { person, scans, cases, domains: whitelist.domains }
    },
    [session?.id, version],
    0,
    session?.id ?? '',
  )
  useEffect(() => {
    if (!session) location.replace('/signup/')
  }, [session])
  useEffect(() => {
    const change = () => {
      setRoute(currentRoute())
      setOpenMobile(false)
      setError('')
      main.current?.focus()
      refresh()
    }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [setOpenMobile])
  const batchKey = `censearch.batch.${session?.id}.${runId}`
  const savedBatch = localStorage.getItem(batchKey)
  const scans = data.value?.scans ?? []
  const scan = scans.find((row) => row.run_id === runId)
  const scanCases = usePoll(
    () => (session && data.value && runId ? api.cases(session.id, runId) : Promise.resolve([])),
    [session?.id, runId, version, data.value?.person.id],
    0,
    `${session?.id}/${runId}`,
  )
  async function updateWhitelist(next: string[]) {
    if (!session || whiteBusy) return
    const before = domains
    setDomains(next)
    setWhiteBusy(true)
    try {
      const result = await api.putWhitelist(session.id, next)
      setDomains(result.domains)
      refresh()
    } catch (failure) {
      setDomains(before)
      throw failure
    } finally {
      setWhiteBusy(false)
    }
  }
  async function toggleWhitelist(row: Case) {
    const host = hostname(row.page_url).toLowerCase().replace(/^www\./, '').replace(/\.$/, '').replace(/^\[|\]$/g, '')
    const next = row.whitelisted
      ? domains.filter((domain) => host !== domain && !host.endsWith(`.${domain}`))
      : [...new Set([...domains, host])]
    try {
      await updateWhitelist(next)
      setError('')
    } catch (failure) {
      setError((failure as Error).message)
    }
  }
  function openScan(row: Scan) {
    navigate(
      `scan/${row.run_id}${['queued', 'running', 'failed', 'cancelled'].includes(row.status) && row.kind === 'public_search' ? '/running' : ''}`,
    )
  }
  async function loadWarning() {
    setWarningError('')
    try {
      const result = await api.warning()
      setWarning(result.warning)
      setDeliveryNote(DEMO ? 'Demo: deliveries are simulated. No email is sent.'
        : result.email_delivery?.ready ? ''
        : 'The sending account is not connected yet. Email requests will be saved as drafts.')
    } catch (failure) {
      setWarningError((failure as Error).message)
    }
  }
  function authorize(ids: number[]) {
    setSelection(ids)
    setWarning('')
    navigate(`scan/${runId}/authorize`)
    void loadWarning()
  }
  async function prepare(contact: Contact, acceptedBy: string, mode: 'prepare' | 'send' = 'send') {
    setBusy(true)
    setError('')
    try {
      const batch = await api.prepare({
        case_ids: selection,
        contact,
        accepted_by: acceptedBy,
        accepted_warning: true,
        mode,
      })
      localStorage.setItem(batchKey, String(batch.id))
      navigate(`scan/${runId}/batch/${batch.id}`)
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function sidebar() {
    return (
      <Sidebar collapsible="icon" variant="sidebar">
        <SidebarHeader className="h-16 justify-center border-b px-4 group-data-[collapsible=icon]:px-2">
          <a href="/" aria-label="CenSearch home" className="min-w-0 overflow-hidden">
            <Logo compact={state === 'collapsed'} />
          </a>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu aria-label="App navigation">
              {[
                { path: 'new', label: 'New scan', Icon: Plus },
                { path: 'home', label: 'Home', Icon: Home },
                { path: 'scans', label: 'All scans', Icon: ListFilter },
              ].map(({ path, label, Icon }) => (
                <SidebarMenuItem key={path}>
                  <SidebarMenuButton asChild isActive={route === path} tooltip={label}>
                    <a href={`#${path}`} aria-current={route === path ? 'page' : undefined}>
                      <Icon /><span>{label}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
          <SidebarGroup className="group-data-[collapsible=icon]:hidden">
            <SidebarGroupLabel>Recent scans</SidebarGroupLabel>
            <SidebarMenu>
              {scans.map((row) => (
                <SidebarMenuItem key={row.run_id}>
                  <SidebarMenuButton asChild isActive={runId === row.run_id} className="h-auto py-3">
                    <a href={`#scan/${row.run_id}${['queued', 'running', 'failed', 'cancelled'].includes(row.status) && row.kind === 'public_search' ? '/running' : ''}`} title={row.label}>
                      <ScanLine />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">{row.label}</span>
                        <span className="block text-xs text-muted-foreground">{relative(row.started_at)} · {row.match_count} matches</span>
                      </span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="border-t">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={parts[0] === 'settings'} tooltip="Settings">
                <a href="#settings"><SettingsIcon /><span>Settings</span></a>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => signOut()} tooltip="Sign out">
                <LogOut /><span className="truncate">{data.value?.person.name ?? session?.name} · Sign out</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
    )
  }
  let view
  if (!session || !data.value)
    view = data.error ? <ErrorBox error={data.error} retry={data.retry} /> : <Loading />
  else if (route === 'home') {
    const cases = data.value.cases
    view = (
      <section className="app-home">
        <Card className="home-overview">
          <CardContent className="home-start">
            <h1>What should we look for?</h1>
            <p>Find where your face and photos appear. Decide what happens next.</p>
            <div className="actions">
              <Button variant="default" onClick={() => navigate('new')}>
                <span>Start scan</span>
              </Button>
              <Button variant="outline" onClick={() => navigate('scans')}>View all scans</Button>
            </div>
          </CardContent>
          {scans.length > 0 && (
            <div className="summary home-summary">
              <span><strong>{scans.length}</strong>scans run</span>
              <span><strong>{cases.length}</strong>matches found</span>
              <span><strong>{cases.filter((row) => row.batch_outcome?.status === 'sent').length}</strong>requests sent</span>
              <span><strong>{cases.filter((row) => ['ready_to_send', 'held_for_review'].includes(row.batch_outcome?.status ?? '')).length}</strong>awaiting your review</span>
            </div>
          )}
        </Card>
        {scans.length > 0 && (
          <section className="recent-scans" aria-label="Recent scans">
            <h2>Recent scans</h2>
            {scans.slice(0, 5).map((row) => (
              <Button variant="outline" className="recent-scan" key={row.run_id} onClick={() => openScan(row)}>
                <span className="scan-link grid min-w-0 gap-1">
                  <span className="truncate" title={row.label}>{row.label}</span>
                  <small>{relative(row.started_at)}</small>
                </span>
                <ScanStatus status={row.status} />
                <span>{row.match_count} matches</span>
                <span aria-hidden="true">↗</span>
              </Button>
            ))}
          </section>
        )}
      </section>
    )
  } else if (route === 'new')
    view = (
      <NewScan key={session.id} personId={session.id} onStart={(run) => {
        refresh()
        navigate(`scan/${run.id}/running`)
      }} />
    )
  else if (route === 'scans')
    view = <AllScans scans={scans} open={openScan} newScan={() => navigate('new')} />
  else if (parts[0] === 'settings')
    view = <Settings person={data.value.person} domains={domains} update={updateWhitelist} busy={whiteBusy} tab={parts[1] === 'whitelist' ? 'whitelist' : 'profile'} onUpdated={refresh} />
  else if (runId && parts[2] === 'running')
    view = (
      <Scanning key={runId} id={runId}
        onDone={() => { refresh(); navigate(`scan/${runId}`) }}
        onResults={() => navigate(`scan/${runId}`)}
        onRetry={() => navigate('new')} />
    )
  else if (runId && batchId)
    view = (
      <BatchReview
        key={batchId}
        id={batchId}
        personId={session.id}
        runId={runId}
        onBack={() => navigate(`scan/${runId}`)}
        onUpdated={refresh}
      />
    )
  else if (runId && parts[2] === 'authorize')
    view = warningError ? (
      <ErrorBox error={warningError} retry={loadWarning} />
    ) : !selection.length ? (
      <>
        <h1>Select matches first</h1>
        <p>Your unsubmitted selection was not saved.</p>
        <Button variant="outline" onClick={() => navigate(`scan/${runId}`)}>Back to scan</Button>
      </>
    ) : !warning ? (
      <Loading />
    ) : (
      <AuthorizeBatch
        cases={(scanCases.value ?? []).filter((row) => selection.includes(row.id))}
        warning={warning}
        personName={data.value.person.name}
        allowReview
        deliveryNote={deliveryNote}
        busy={busy}
        onRun={prepare}
        onCancel={() => navigate(`scan/${runId}`)}
      />
    )
  else if (runId && scan)
    view = scanCases.error ? (
      <ErrorBox error={scanCases.error} retry={scanCases.retry} />
    ) : !scanCases.value ? (
      <Loading />
    ) : (
      <ScanDetail
        key={runId}
        scan={scan}
        cases={scanCases.value}
        onReview={authorize}
        onWhitelist={toggleWhitelist}
        whitelistBusy={whiteBusy}
        whitelistError={error}
        onNew={() => navigate('new')}
        resume={savedBatch ? () => navigate(`scan/${runId}/batch/${savedBatch}`) : undefined}
      />
    )
  else
    view = (
      <>
        <h1>View not found</h1>
        <p>Open a scan from the sidebar or start a new one.</p>
        <Button variant="outline" onClick={() => navigate('home')}>Go home</Button>
      </>
    )
  return (
    <>
      <a className="skip-link" href="#app-main" onClick={(event) => { event.preventDefault(); main.current?.focus() }}>Skip to content</a>
      {sidebar()}
      <SidebarInset className="min-w-0">
        <header className="flex min-h-16 items-center gap-3 border-b px-4 md:px-6">
          <SidebarTrigger aria-label="Toggle navigation" />
          <Separator orientation="vertical" className="data-[orientation=vertical]:h-4" />
          <span className="text-sm text-muted-foreground">CenSearch / {route === 'home' ? 'Home' : route === 'new' ? 'New scan' : parts[0] === 'settings' ? 'Settings' : route === 'scans' ? 'All scans' : 'Scan'}</span>
          {DEMO && <Badge variant="outline" className="sample-label ml-auto max-w-[50%] shrink whitespace-normal text-right text-amber-200">Demo: sample person, simulated scans and sending</Badge>}
        </header>
        <div id="app-main" ref={main} tabIndex={-1} className="dashboard-content flex-1 p-4 md:p-6">
          {error && <ErrorBox error={error} />}
          {data.value && data.error && <ErrorBox error={data.error} retry={data.retry} />}
          {view}
        </div>
      </SidebarInset>
    </>
  )
}

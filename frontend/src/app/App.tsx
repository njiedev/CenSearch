import { useEffect, useRef, useState } from 'react'
import Logo from '../Logo'
import AuthorizeBatch from '../matches/AuthorizeBatch'
import { hostname } from '../matches/types'
import { api, isSample } from './api'
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
  const [session] = useState<Session | null>(
    () => readSession() ?? (isSample() ? { id: 'sample', name: 'Alex Rivera' } : null),
  )
  const [route, setRoute] = useState(currentRoute)
  const [collapsed, setCollapsed] = useState(false)
  const drawer = useRef<HTMLDialogElement>(null)
  const main = useRef<HTMLElement>(null)
  const [version, setVersion] = useState(0)
  const refresh = () => setVersion((value) => value + 1)
  const [domains, setDomains] = useState<string[]>([])
  const [whiteBusy, setWhiteBusy] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selection, setSelection] = useState<number[]>([])
  const [warning, setWarning] = useState('')
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
    if (!session) location.replace('/signup.html')
  }, [session])
  useEffect(() => {
    const change = () => {
      setRoute(currentRoute())
      drawer.current?.close()
      setError('')
      main.current?.focus()
      refresh()
    }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  const batchKey = `censearch.batch.${isSample() ? 'sample' : session?.id}.${runId}`
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
    const host = hostname(row.page_url)
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
      setWarning((await api.warning()).warning)
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
  async function prepare(contact: Contact, acceptedBy: string) {
    setBusy(true)
    setError('')
    try {
      const batch = await api.prepare({
        case_ids: selection,
        contact,
        accepted_by: acceptedBy,
        accepted_warning: true,
        mode: 'prepare',
      })
      localStorage.setItem(batchKey, String(batch.id))
      navigate(`scan/${runId}/batch/${batch.id}`)
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function sidebar(mobile = false) {
    return (
      <>
        <div className="sidebar-top">
          <a href="/" className="app-logo" aria-label="CenSearch home">
            <Logo compact={collapsed && !mobile} />
          </a>
          {mobile ? (
            <button aria-label="Close navigation" onClick={() => drawer.current?.close()}>
              ×
            </button>
          ) : (
            <button
              className="collapse-toggle"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? '»' : '«'}
            </button>
          )}
        </div>
        <nav aria-label={mobile ? 'Mobile app navigation' : 'App navigation'}>
          <a href="#new" aria-current={route === 'new' ? 'page' : undefined} title="New scan">
            <span aria-hidden="true">＋</span>
            <span className="sidebar-label">New scan</span>
          </a>
          <a href="#home" aria-current={route === 'home' ? 'page' : undefined} title="Home">
            <span aria-hidden="true">⌂</span>
            <span className="sidebar-label">Home</span>
          </a>
          <div className="sidebar-section">
            <a href="#scans" title="All scans">
              <span aria-hidden="true">☷</span>
              <span className="sidebar-label">Scans</span>
            </a>
          </div>
          <div className="scan-history">
            {scans.map((row) => (
              <a
                href={`#scan/${row.run_id}${['queued', 'running', 'failed', 'cancelled'].includes(row.status) && row.kind === 'public_search' ? '/running' : ''}`}
                key={row.run_id}
                aria-current={runId === row.run_id ? 'page' : undefined}
                title={`${row.label} · ${relative(row.started_at)} · ${row.match_count} matches`}
              >
                <span className="scan-icon" aria-hidden="true">
                  ○
                </span>
                <span className="sidebar-label scan-link">
                  <span className="truncate">{row.label}</span>
                  <small>
                    {relative(row.started_at)} · {row.match_count} matches
                  </small>
                  {row.status !== 'completed' && <ScanStatus status={row.status} />}
                </span>
              </a>
            ))}
          </div>
        </nav>
        <div className="sidebar-bottom">
          <a href="#settings" title="Settings" aria-current={route === 'settings' ? 'page' : undefined}>
            <span aria-hidden="true">⚙</span>
            <span className="sidebar-label">Settings</span>
          </a>
          <div className="identity">
            <span className="avatar" aria-hidden="true">
              {(data.value?.person.name ?? session?.name ?? '?').slice(0, 1)}
            </span>
            <span className="sidebar-label">
              <span className="truncate" title={data.value?.person.name ?? session?.name}>
                {data.value?.person.name ?? session?.name}
              </span>
              <button onClick={() => signOut()}>Sign out</button>
            </span>
          </div>
        </div>
      </>
    )
  }
  let view
  if (!session || !data.value)
    view = data.error ? <ErrorBox error={data.error} retry={data.retry} /> : <Loading />
  else if (route === 'home') {
    const cases = data.value.cases
    view = (
      <section className="app-home">
        <div>
          <h1>What should we look for?</h1>
          <p>Find where your face and photos appear. Decide what happens next.</p>
          <div className="actions">
            <button className="primary border-light" onClick={() => navigate('new')}>
              <span>Start scan</span>
            </button>
            <button onClick={() => navigate('scans')}>View all scans</button>
          </div>
          {scans.length > 0 && (
            <div className="summary">
              <span>
                <strong>{scans.length}</strong>scans run
              </span>
              <span>
                <strong>{cases.length}</strong>matches found
              </span>
              <span>
                <strong>{cases.filter((row) => row.batch_outcome?.status === 'sent').length}</strong>requests
                sent
              </span>
              <span>
                <strong>
                  {
                    cases.filter((row) =>
                      ['ready_to_send', 'held_for_review'].includes(row.batch_outcome?.status ?? ''),
                    ).length
                  }
                </strong>
                awaiting your review
              </span>
            </div>
          )}
        </div>
      </section>
    )
  } else if (route === 'new')
    view = (
      <NewScan
        personId={session.id}
        onStart={(run) => {
          refresh()
          navigate(`scan/${run.id}/running`)
        }}
      />
    )
  else if (route === 'scans')
    view = <AllScans scans={scans} open={openScan} newScan={() => navigate('new')} />
  else if (route === 'settings')
    view = <Settings person={data.value.person} domains={domains} update={updateWhitelist} busy={whiteBusy} />
  else if (runId && parts[2] === 'running')
    view = (
      <Scanning
        key={runId}
        id={runId}
        onDone={() => {
          refresh()
          navigate(`scan/${runId}`)
        }}
        onResults={() => navigate(`scan/${runId}`)}
        onRetry={() => navigate('new')}
      />
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
        <button onClick={() => navigate(`scan/${runId}`)}>Back to scan</button>
      </>
    ) : !warning ? (
      <Loading />
    ) : (
      <AuthorizeBatch
        cases={(scanCases.value ?? []).filter((row) => selection.includes(row.id))}
        warning={warning}
        personName={data.value.person.name}
        preparing
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
        <button onClick={() => navigate('home')}>Go home</button>
      </>
    )
  return (
    <div className={`app-shell${collapsed ? ' is-collapsed' : ''}`}>
      <a
        className="skip-link"
        href="#app-main"
        onClick={(event) => {
          event.preventDefault()
          main.current?.focus()
        }}
      >
        Skip to content
      </a>
      <aside className="app-sidebar">{sidebar()}</aside>
      <dialog
        className="app-drawer"
        ref={drawer}
        onClick={(event) => {
          if (event.target === event.currentTarget) drawer.current?.close()
        }}
      >
        {sidebar(true)}
      </dialog>
      <div className="app-body">
        <header className="app-topbar">
          <button
            className="drawer-toggle"
            aria-label="Open navigation"
            onClick={() => drawer.current?.showModal()}
          >
            ☰
          </button>
          <span>
            CenSearch /{' '}
            {route === 'home'
              ? 'Home'
              : route === 'new'
                ? 'New scan'
                : route === 'settings'
                  ? 'Settings'
                  : route === 'scans'
                    ? 'All scans'
                    : 'Scan'}
          </span>
          {isSample() && <span className="sample-label">◇ Sample data: backend not connected</span>}
        </header>
        <main id="app-main" ref={main} tabIndex={-1}>
          {error && <ErrorBox error={error} />}
          {data.value && data.error && <ErrorBox error={data.error} retry={data.retry} />}
          {view}
        </main>
      </div>
    </div>
  )
}

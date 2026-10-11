import { useState } from 'react'
import MatchGrid from '../matches/MatchGrid'
import MatchZoom from '../matches/MatchZoom'
import { statusOf } from '../matches/logic'
import { hostname } from '../matches/types'
import type { Case, Scan } from './types'
import { Empty } from './ui'
import { date, duration } from './hooks'

type Filters = {
  from: string
  to: string
  sites: string[]
  status: string
  strength: string
  search: string
  sort: string
  white: boolean
}
const clean: Filters = {
  from: '',
  to: '',
  sites: [],
  status: '',
  strength: '',
  search: '',
  sort: 'newest',
  white: false,
}
const statuses = [
  ['new', 'New'],
  ['ready_to_send', 'Ready to send'],
  ['sent', 'Sent'],
  ['drafted_not_sent', 'Drafted for you to send'],
  ['left_alone', 'Left alone'],
  ['held_for_review', 'Held for review'],
  ['failed', 'Failed'],
]
export default function ScanDetail({
  scan,
  cases,
  onReview,
  onWhitelist,
  whitelistBusy,
  whitelistError,
  onNew,
  resume,
}: {
  scan: Scan
  cases: Case[]
  onReview: (ids: number[]) => void
  onWhitelist: (row: Case) => void
  whitelistBusy: boolean
  whitelistError: string
  onNew: () => void
  resume?: () => void
}) {
  const [filters, setFilters] = useState<Filters>(clean)
  const [selected, setSelected] = useState<number[]>([])
  const [opened, setOpened] = useState<{ id: number; origin: HTMLElement } | null>(null)
  function update<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters({ ...filters, [key]: value })
  }
  const hosts = [...new Set(cases.map((row) => hostname(row.page_url)))].sort()
  const visible = cases
    .filter((row) => {
      const day = row.created_at?.slice(0, 10) ?? ''
      return (
        (filters.white || !row.whitelisted) &&
        (!filters.from || day >= filters.from) &&
        (!filters.to || (day && day <= filters.to)) &&
        (!filters.sites.length || filters.sites.includes(hostname(row.page_url))) &&
        (!filters.status || statusOf(row) === filters.status) &&
        (!filters.strength || row.band === filters.strength) &&
        (!filters.search || row.page_url.toLowerCase().includes(filters.search.toLowerCase()))
      )
    })
    .sort((a, b) =>
      filters.sort === 'site'
        ? hostname(a.page_url).localeCompare(hostname(b.page_url))
        : filters.sort === 'strongest'
          ? Number(b.band === 'match') - Number(a.band === 'match') || (b.score ?? 0) - (a.score ?? 0)
          : (b.created_at ?? '').localeCompare(a.created_at ?? ''),
    )
  const eligible = visible.filter((row) => !row.whitelisted).map((row) => row.id)
  const safeSelected = selected.filter((id) => cases.some((row) => row.id === id && !row.whitelisted))
  const all = eligible.length > 0 && eligible.every((id) => safeSelected.includes(id))
  const whitelisted = cases.filter((row) => row.whitelisted).length
  const active = Object.entries(filters).filter(
    ([key, value]) => !['sort', 'white', 'sites'].includes(key) && value,
  )
  return (
    <section>
      <header className="page-head">
        <h1>{scan.label}</h1>
        <p>
          {date(scan.started_at)} · Duration {duration(scan.started_at, scan.finished_at)}
        </p>
        <div className="summary">
          <span>
            <strong>{cases.filter((row) => row.band === 'match').length}</strong>matches
          </span>
          <span>
            <strong>{cases.filter((row) => row.band === 'possible').length}</strong>possible matches
          </span>
          <span>
            <strong>{whitelisted}</strong>whitelisted
          </span>
          <span>
            <strong>{cases.filter((row) => ['sent', 'left_alone'].includes(statusOf(row))).length}</strong>
            already handled
          </span>
        </div>
        {resume && <button onClick={resume}>Resume batch</button>}
      </header>
      <div className="filters">
        <label>
          Search pages
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update('search', event.target.value)}
          />
        </label>
        <label>
          From
          <input type="date" value={filters.from} onChange={(event) => update('from', event.target.value)} />
        </label>
        <label>
          To
          <input
            type="date"
            value={filters.to}
            min={filters.from}
            onChange={(event) => update('to', event.target.value)}
          />
        </label>
        <details className="site-filter">
          <summary>Sites ({filters.sites.length || 'all'})</summary>
          <div>
            {hosts.map((host) => (
              <label className="check-row" key={host}>
                <input
                  type="checkbox"
                  checked={filters.sites.includes(host)}
                  onChange={() =>
                    update(
                      'sites',
                      filters.sites.includes(host)
                        ? filters.sites.filter((value) => value !== host)
                        : [...filters.sites, host],
                    )
                  }
                />
                {host}
              </label>
            ))}
          </div>
        </details>
        <label>
          Status
          <select value={filters.status} onChange={(event) => update('status', event.target.value)}>
            <option value="">All statuses</option>
            {statuses.map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Match strength
          <select value={filters.strength} onChange={(event) => update('strength', event.target.value)}>
            <option value="">All strengths</option>
            <option value="match">Match</option>
            <option value="possible">Possible</option>
          </select>
        </label>
        <label>
          Sort
          <select value={filters.sort} onChange={(event) => update('sort', event.target.value)}>
            <option value="newest">Newest</option>
            <option value="strongest">Strongest</option>
            <option value="site">Site</option>
          </select>
        </label>
      </div>
      <div className="chips">
        {active.map(([key, value]) => (
          <button key={key} onClick={() => update(key as keyof Filters, '')}>
            {key}: {String(value)} ×
          </button>
        ))}
        {filters.sites.map((site) => (
          <button
            key={site}
            onClick={() =>
              update(
                'sites',
                filters.sites.filter((value) => value !== site),
              )
            }
          >
            {site} ×
          </button>
        ))}
        {(active.length > 0 || filters.sites.length > 0) && (
          <button onClick={() => setFilters(clean)}>Clear filters</button>
        )}
      </div>
      <div className="filter-summary">
        <span>
          {visible.length} of {cases.length}
        </span>
        <label className="check-row">
          <input
            type="checkbox"
            checked={filters.white}
            onChange={(event) => update('white', event.target.checked)}
          />
          Show whitelisted ({whitelisted})
        </label>
      </div>
      {!cases.length ? (
        <Empty title="No matches found" action="Start a new scan" onAction={onNew}>
          Try different handles or add specific public page URLs.
        </Empty>
      ) : !visible.length ? (
        <Empty
          title="No matches with these filters"
          action="Clear filters"
          onAction={() => setFilters({ ...clean, white: true })}
        >
          Clear the filters to see this scan’s matches.
        </Empty>
      ) : (
        <>
          <button
            onClick={() =>
              setSelected(
                all
                  ? safeSelected.filter((id) => !eligible.includes(id))
                  : [...new Set([...safeSelected, ...eligible])],
              )
            }
          >
            {all ? 'Clear visible selection' : 'Select all visible'}
          </button>
          <MatchGrid
            embedded
            cases={visible}
            selected={safeSelected}
            batch={null}
            viewState="data"
            onToggle={(id) =>
              setSelected(
                safeSelected.includes(id)
                  ? safeSelected.filter((value) => value !== id)
                  : [...safeSelected, id],
              )
            }
            onToggleAll={() => {}}
            onOpen={(id, origin) => setOpened({ id, origin })}
            onAuthorize={() => onReview(safeSelected)}
            onShowProgress={() => {}}
          />
        </>
      )}
      <footer className="sticky-actions">
        <span>{safeSelected.length} selected</span>
        <button className="primary" disabled={!safeSelected.length} onClick={() => onReview(safeSelected)}>
          Review with agent
        </button>
        {!safeSelected.length && <small>Select matches to review.</small>}
      </footer>
      <MatchZoom
        item={cases.find((row) => row.id === opened?.id)}
        origin={opened?.origin ?? null}
        onClose={() => setOpened(null)}
        onWhitelist={onWhitelist}
        whitelistBusy={whitelistBusy}
        whitelistError={whitelistError}
      />
    </section>
  )
}

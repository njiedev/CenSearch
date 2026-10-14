import FollowUp from './FollowUp'
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { NativeSelectOption } from "@/components/ui/native-select"
import { NativeSelect } from "@/components/ui/native-select"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useState } from 'react'
import MatchGrid from '../matches/MatchGrid'
import MatchZoom from '../matches/MatchZoom'
import { statusOf } from '../matches/logic'
import { hostname } from '../matches/types'
import type { Case, Scan } from './types'
import { Empty, ErrorBox } from './ui'
import { date, duration, usePoll } from './hooks'
import { DEMO } from '../demo'
import { api } from './api'

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
  const detail = usePoll(
    () => scan.kind === 'public_search' && !DEMO ? api.run(scan.run_id) : Promise.resolve(null),
    [scan.run_id, scan.kind],
  )
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
        {resume && <Button variant="outline" onClick={resume}>Resume batch</Button>}
      </header>
      {detail.error && <ErrorBox error={detail.error} retry={detail.retry} />}
      <div className="scan-toolbar" aria-label="Filter matches">
        <Popover>
          <PopoverTrigger asChild><Button variant="ghost" size="sm">Sites ({filters.sites.length || 'all'})</Button></PopoverTrigger>
          <PopoverContent className="grid max-h-80 gap-3 overflow-y-auto">
            {hosts.map((host) => (
              <Label className="check-row" key={host}>
                <Checkbox

                  checked={filters.sites.includes(host)}
                  onCheckedChange={() =>
                    update(
                      'sites',
                      filters.sites.includes(host)
                        ? filters.sites.filter((value) => value !== host)
                        : [...filters.sites, host],
                    )
                  }
                />
                {host}
              </Label>
            ))}
          </PopoverContent>
        </Popover>
        <NativeSelect aria-label="Status" value={filters.status} onChange={(event) => update('status', event.target.value)}>
          <NativeSelectOption value="">All statuses</NativeSelectOption>
          {statuses.map(([value, label]) => (
            <NativeSelectOption value={value} key={value}>
              {label}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <NativeSelect aria-label="Match strength" value={filters.strength} onChange={(event) => update('strength', event.target.value)}>
          <NativeSelectOption value="">All strengths</NativeSelectOption>
          <NativeSelectOption value="match">Match</NativeSelectOption>
          <NativeSelectOption value="possible">Possible</NativeSelectOption>
        </NativeSelect>
        <NativeSelect aria-label="Sort" value={filters.sort} onChange={(event) => update('sort', event.target.value)}>
          <NativeSelectOption value="newest">Newest</NativeSelectOption>
          <NativeSelectOption value="strongest">Strongest</NativeSelectOption>
          <NativeSelectOption value="site">Site</NativeSelectOption>
        </NativeSelect>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="sm">
              More filters{(filters.search || filters.from || filters.to || filters.white) ? ' · active' : ''}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="scan-more-filters">
            <Label>
              Search pages
              <Input type="search" value={filters.search}
                onChange={(event) => update('search', event.target.value)} />
            </Label>
            <div className="scan-date-filters">
              <Label>
                From
                <Input type="date" value={filters.from}
                  onChange={(event) => update('from', event.target.value)} />
              </Label>
              <Label>
                To
                <Input type="date" value={filters.to} min={filters.from}
                  onChange={(event) => update('to', event.target.value)} />
              </Label>
            </div>
            <Label className="check-row">
              <Checkbox checked={filters.white}
                onCheckedChange={(checked) => update('white', checked === true)} />
              Show whitelisted ({whitelisted})
            </Label>
          </PopoverContent>
        </Popover>
        <span className="filter-summary" role="status">
          {visible.length} of {cases.length}
        </span>
      </div>
      <div className="chips">
        {active.map(([key, value]) => (
          <Button variant="outline" key={key} onClick={() => update(key as keyof Filters, '')}>
            {key}: {String(value)} ×
          </Button>
        ))}
        {filters.sites.map((site) => (
          <Button variant="outline"
            key={site}
            onClick={() =>
              update(
                'sites',
                filters.sites.filter((value) => value !== site),
              )
            }
          >
            {site} ×
          </Button>
        ))}
        {(active.length > 0 || filters.sites.length > 0) && (
          <Button variant="outline" onClick={() => setFilters(clean)}>Clear filters</Button>
        )}
      </div>
      {!cases.length ? (
        <Empty title="No matches found" action="Start a new scan" onAction={onNew}>
          {detail.value?.facecheck
            ? 'No review candidates are saved for this scan. Older saved scans can be reopened from New scan to add their candidates.'
            : 'Try different handles or add specific public page URLs.'}
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
          <Button variant="outline"
            onClick={() =>
              setSelected(
                all
                  ? safeSelected.filter((id) => !eligible.includes(id))
                  : [...new Set([...safeSelected, ...eligible])],
              )
            }
          >
            {all ? 'Clear visible selection' : 'Select all visible'}
          </Button>
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
        <Button variant="default" disabled={!safeSelected.length} onClick={() => onReview(safeSelected)}>
          Review with agent
        </Button>
        {!safeSelected.length && <small>Select matches to review.</small>}
      </footer>
      <MatchZoom
        item={cases.find((row) => row.id === opened?.id)}
        origin={opened?.origin ?? null}
        onClose={() => setOpened(null)}
        onWhitelist={onWhitelist}
        whitelistBusy={whitelistBusy}
        whitelistError={whitelistError}
        followUp={opened && !DEMO ? <FollowUp key={opened.id} caseId={opened.id} /> : undefined}
      />
    </section>
  )
}

import { useState } from 'react'
import type { Scan } from './types'
import { Empty, ScanStatus } from './ui'
import { date, duration } from './hooks'
export default function AllScans({
  scans,
  open,
  newScan,
}: {
  scans: Scan[]
  open: (scan: Scan) => void
  newScan: () => void
}) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<'started' | 'matches'>('started')
  const [descending, setDescending] = useState(true)
  const rows = scans
    .filter((scan) => scan.label.toLowerCase().includes(query.toLowerCase()))
    .sort(
      (a, b) =>
        (descending ? -1 : 1) *
        (sort === 'matches'
          ? a.match_count - b.match_count
          : (a.started_at ?? '').localeCompare(b.started_at ?? '')),
    )
  function order(key: 'started' | 'matches') {
    if (sort === key) setDescending(!descending)
    else {
      setSort(key)
      setDescending(true)
    }
  }
  return (
    <section>
      <header className="page-head">
        <h1>All scans</h1>
        <p>Your public searches and their results.</p>
      </header>
      <label className="table-search">
        Find a scan
        <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      {!scans.length ? (
        <Empty title="No scans yet" action="Start scan" onAction={newScan}>
          Start your first scan to look for public appearances.
        </Empty>
      ) : !rows.length ? (
        <Empty title="No scans match your search" action="Clear search" onAction={() => setQuery('')}>
          Try another name or clear your search.
        </Empty>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Scan</th>
                <th aria-sort={sort === 'started' ? (descending ? 'descending' : 'ascending') : 'none'}>
                  <button onClick={() => order('started')}>Started ↕</button>
                </th>
                <th>Duration</th>
                <th>Pages</th>
                <th>Images checked</th>
                <th aria-sort={sort === 'matches' ? (descending ? 'descending' : 'ascending') : 'none'}>
                  <button onClick={() => order('matches')}>Matches ↕</button>
                </th>
                <th>Possible</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((scan) => (
                <tr key={scan.run_id} onClick={() => open(scan)}>
                  <td>
                    <button
                      className="scan-name"
                      title={scan.label}
                      onClick={(event) => {
                        event.stopPropagation()
                        open(scan)
                      }}
                    >
                      {scan.label}
                    </button>
                  </td>
                  <td>{date(scan.started_at)}</td>
                  <td>{duration(scan.started_at, scan.finished_at)}</td>
                  <td>{scan.pages_fetched ?? '-'}</td>
                  <td>{scan.images_checked ?? '-'}</td>
                  <td>{scan.match_count ?? '-'}</td>
                  <td>{scan.possible_count ?? '-'}</td>
                  <td>
                    <ScanStatus status={scan.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

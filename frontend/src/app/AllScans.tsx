import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
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
      <Label className="table-search">
        Find a scan
        <Input type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
      </Label>
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
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scan</TableHead>
                <TableHead aria-sort={sort === 'started' ? (descending ? 'descending' : 'ascending') : 'none'}>
                  <Button variant="ghost" onClick={() => order('started')}>Started ↕</Button>
                </TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Pages</TableHead>
                <TableHead>Images checked</TableHead>
                <TableHead aria-sort={sort === 'matches' ? (descending ? 'descending' : 'ascending') : 'none'}>
                  <Button variant="ghost" onClick={() => order('matches')}>Matches ↕</Button>
                </TableHead>
                <TableHead>Possible</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((scan) => (
                <TableRow key={scan.run_id} onClick={() => open(scan)}>
                  <TableCell>
                    <Button variant="ghost"
                      className="scan-name"
                      title={scan.label}
                      onClick={(event) => {
                        event.stopPropagation()
                        open(scan)
                      }}
                    >
                      {scan.label}
                    </Button>
                  </TableCell>
                  <TableCell>{date(scan.started_at)}</TableCell>
                  <TableCell>{duration(scan.started_at, scan.finished_at)}</TableCell>
                  <TableCell>{scan.pages_fetched ?? '-'}</TableCell>
                  <TableCell>{scan.images_checked ?? '-'}</TableCell>
                  <TableCell>{scan.match_count ?? '-'}</TableCell>
                  <TableCell>{scan.possible_count ?? '-'}</TableCell>
                  <TableCell>
                    <ScanStatus status={scan.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}

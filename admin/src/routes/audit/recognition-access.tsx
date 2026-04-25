import { useMemo, useState, useTransition } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { Eye, Shield } from 'lucide-react'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { usePageTitle } from '@/hooks/use-page-title'
import { useRecognitionAccessAudit } from '@/hooks/use-queries'
import type { AccessAuditEntry, AccessAuditFilters } from '@/types'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'
import { formatTimestamp, formatFullDatetime } from '@/lib/format-time'

function buildAccessAuditHaystack(e: AccessAuditEntry): string {
  return joinHaystack([
    e.viewer_name,
    e.viewer_user_id,
    e.event_id,
    e.crop_kind,
    e.crop_kind === 'live' ? 'Live' : 'Registered',
    e.student_name,
    e.student_id,
    e.ip,
    e.user_agent,
    ...isoDateHaystackParts(e.viewed_at),
  ])
}

/**
 * Recognition Access Audit page.
 *
 * Read-only log of every crop-fetch request against the recognition-
 * evidence endpoints. Answers the question a registrar gets when a
 * parent asks "who has viewed my child's face in this system?" — every
 * admin who resolved a crop URL shows up here with timestamp, IP, and
 * user agent.
 *
 * Rows are append-only on the backend (3-year legal retention), so there
 * is no delete/edit action here. Skip/Limit pagination only — no cursor
 * since the table is capped to small totals in practice.
 */
export default function RecognitionAccessAuditPage() {
  usePageTitle('Recognition Access Audit')

  const [viewerInput, setViewerInput] = useState('')
  const [eventInput, setEventInput] = useState('')
  const [filters, setFilters] = useState<AccessAuditFilters>({ limit: 100 })

  const { data, isLoading } = useRecognitionAccessAudit(filters)
  const items = useMemo(() => data?.items ?? [], [data])

  const [searchQuery, setSearchQuery] = useState('')
  const [, startSearchTransition] = useTransition()

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items
    return items.filter((e) => tokenMatches(buildAccessAuditHaystack(e), searchQuery))
  }, [items, searchQuery])

  const apply = () => {
    const next: AccessAuditFilters = { limit: 100 }
    if (viewerInput) next.viewer_id = viewerInput
    if (eventInput) next.event_id = eventInput
    setFilters(next)
  }
  const clear = () => {
    setViewerInput('')
    setEventInput('')
    setFilters({ limit: 100 })
  }

  const columns: ColumnDef<AccessAuditEntry>[] = useMemo(
    () => [
      {
        accessorKey: 'viewed_at',
        header: 'Viewed',
        cell: ({ row }) => (
          <span
            className="font-mono text-xs tabular-nums"
            title={formatFullDatetime(row.original.viewed_at)}
          >
            {formatTimestamp(row.original.viewed_at)}
          </span>
        ),
      },
      {
        accessorKey: 'viewer_name',
        header: 'Viewer',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="text-sm font-medium">
              {row.original.viewer_name ?? 'Admin'}
            </span>
            <span className="text-[11px] font-mono text-muted-foreground">
              {row.original.viewer_user_id.slice(0, 8)}…
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'crop_kind',
        header: 'Crop',
        cell: ({ row }) =>
          row.original.crop_kind === 'live' ? (
            <Badge variant="default">Live</Badge>
          ) : (
            <Badge variant="secondary">Registered</Badge>
          ),
      },
      {
        accessorKey: 'student_name',
        header: 'Subject',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="text-sm">
              {row.original.student_name ?? (
                <span className="text-muted-foreground">Unmatched</span>
              )}
            </span>
            {row.original.student_id && (
              <Link
                to={`/students/${row.original.student_id}`}
                className="text-[11px] text-muted-foreground hover:underline"
              >
                view student
              </Link>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'event_id',
        header: 'Event',
        cell: ({ row }) => (
          <Link
            to={`/recognitions?event=${row.original.event_id}`}
            className="font-mono text-[11px] text-muted-foreground hover:underline"
          >
            {row.original.event_id.slice(0, 8)}…
          </Link>
        ),
      },
      {
        accessorKey: 'ip',
        header: 'IP',
        cell: ({ row }) => (
          <span className="font-mono text-[11px] text-muted-foreground">
            {row.original.ip ?? '—'}
          </span>
        ),
      },
    ],
    [],
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Shield className="h-5 w-5 text-muted-foreground" />
            Recognition Access Audit
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every admin request for a recognition-evidence crop. Retained for 3 years.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Eye className="h-4 w-4" aria-hidden />
          <span>{data?.total ?? '—'} total entries</span>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-md border bg-muted/30 p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-muted-foreground">
            Viewer ID
          </label>
          <Input
            value={viewerInput}
            onChange={(e) => setViewerInput(e.target.value)}
            placeholder="UUID"
            className="h-9 w-64 font-mono text-xs"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-muted-foreground">
            Event ID
          </label>
          <Input
            value={eventInput}
            onChange={(e) => setEventInput(e.target.value)}
            placeholder="UUID"
            className="h-9 w-64 font-mono text-xs"
          />
        </div>
        <Button onClick={apply}>Apply</Button>
        {(viewerInput || eventInput) && (
          <Button variant="ghost" onClick={clear}>
            Clear
          </Button>
        )}
      </div>

      <DataTable
        columns={columns}
        data={filteredItems}
        isLoading={isLoading}
        searchPlaceholder="Search by viewer, subject, event, IP…"
        globalFilter={searchQuery}
        onGlobalFilterChange={(v) => startSearchTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
      />

      {data && data.total > items.length && (
        <div className="text-center text-xs text-muted-foreground">
          Showing {items.length} of {data.total} entries. Narrow the filter to page deeper.
        </div>
      )}
    </div>
  )
}

import { useMemo, useState, useTransition } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { Download } from 'lucide-react'

import { formatTimestamp, formatFullDatetime } from '@/lib/format-time'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
import { RecognitionOutcomePill } from '@/components/shared/status-pills'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePageTitle } from '@/hooks/use-page-title'
import { useRecognitions } from '@/hooks/use-queries'
import { useAuthedImage } from '@/hooks/use-authed-image'
import { recognitionsService } from '@/services/recognitions.service'
import type { RecognitionEvent, RecognitionListFilters } from '@/types'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'

function buildRecognitionHaystack(e: RecognitionEvent): string {
  const outcome = e.is_ambiguous ? 'Ambiguous' : e.matched ? 'Match Matched' : 'Miss Missed'
  return joinHaystack([
    e.student_name,
    e.student_id,
    e.schedule_subject,
    e.schedule_id,
    e.camera_id,
    e.event_id,
    e.model_name,
    `track ${e.track_id}`,
    `frame ${e.frame_idx}`,
    outcome,
    `${(e.similarity * 100).toFixed(1)}%`,
    `${(e.threshold_used * 100).toFixed(0)}%`,
    ...isoDateHaystackParts(e.created_at),
  ])
}

type MatchedFilter = 'all' | 'matched' | 'missed'

export default function RecognitionsPage() {
  usePageTitle('Recognitions')
  const [searchParams, setSearchParams] = useSearchParams()

  const studentFilter = searchParams.get('student_id') ?? ''
  const scheduleFilter = searchParams.get('schedule_id') ?? ''
  const matchedParam = (searchParams.get('matched') ?? 'all') as MatchedFilter

  const [studentInput, setStudentInput] = useState(studentFilter)
  const [scheduleInput, setScheduleInput] = useState(scheduleFilter)

  const filters: RecognitionListFilters = useMemo(
    () => ({
      student_id: studentFilter || undefined,
      schedule_id: scheduleFilter || undefined,
      matched:
        matchedParam === 'matched'
          ? true
          : matchedParam === 'missed'
            ? false
            : undefined,
      limit: 100,
    }),
    [studentFilter, scheduleFilter, matchedParam],
  )

  const { data, isLoading } = useRecognitions(filters)
  const items = useMemo(() => data?.items ?? [], [data])

  const [searchQuery, setSearchQuery] = useState('')
  const [, startSearchTransition] = useTransition()
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items
    return items.filter((e) => tokenMatches(buildRecognitionHaystack(e), searchQuery))
  }, [items, searchQuery])

  const applyTextFilters = () => {
    const next = new URLSearchParams(searchParams)
    if (studentInput) next.set('student_id', studentInput)
    else next.delete('student_id')
    if (scheduleInput) next.set('schedule_id', scheduleInput)
    else next.delete('schedule_id')
    setSearchParams(next)
  }

  const setMatched = (value: MatchedFilter) => {
    const next = new URLSearchParams(searchParams)
    if (value === 'all') next.delete('matched')
    else next.set('matched', value)
    setSearchParams(next)
  }

  const clearAll = () => {
    setStudentInput('')
    setScheduleInput('')
    setSearchParams({})
  }

  const columns: ColumnDef<RecognitionEvent>[] = useMemo(
    () => [
      {
        accessorKey: 'created_at',
        header: 'When',
        cell: ({ row }) => (
          <span
            className="font-mono text-xs tabular-nums"
            title={formatFullDatetime(row.original.created_at)}
          >
            {formatTimestamp(row.original.created_at)}
          </span>
        ),
      },
      {
        accessorKey: 'student_name',
        header: 'Student',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="text-sm font-medium">
              {row.original.student_name ?? (row.original.matched ? 'Unknown' : 'Unmatched')}
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
        accessorKey: 'schedule_subject',
        header: 'Schedule',
        cell: ({ row }) => (
          <span className="text-sm">
            {row.original.schedule_subject ?? '—'}
            <span className="ml-1 text-xs text-muted-foreground">
              · {row.original.camera_id}
            </span>
          </span>
        ),
      },
      {
        accessorKey: 'matched',
        header: 'Outcome',
        cell: ({ row }) => (
          <RecognitionOutcomePill
            matched={row.original.matched}
            ambiguous={row.original.is_ambiguous}
          />
        ),
      },
      {
        accessorKey: 'similarity',
        header: 'Sim / Thr',
        cell: ({ row }) => (
          <span className="font-mono text-sm">
            {(row.original.similarity * 100).toFixed(1)}% /{' '}
            {(row.original.threshold_used * 100).toFixed(0)}%
          </span>
        ),
      },
      {
        id: 'live',
        header: 'Live',
        cell: ({ row }) => (
          <CropLink url={row.original.crop_urls.live} label="live" />
        ),
      },
      {
        id: 'registered',
        header: 'Registered',
        cell: ({ row }) =>
          row.original.crop_urls.registered ? (
            <CropLink url={row.original.crop_urls.registered} label="reg" />
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          ),
      },
    ],
    [],
  )

  const hasFilters = studentFilter || scheduleFilter || matchedParam !== 'all'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Recognition Audit</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every FAISS decision logged by the realtime pipeline.
          </p>
        </div>
        <Button asChild variant="outline">
          <a
            href={recognitionsService.exportCsvUrl(filters)}
            target="_blank"
            rel="noreferrer"
          >
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </a>
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-md border bg-muted/30 p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-muted-foreground">
            Student ID
          </label>
          <Input
            value={studentInput}
            onChange={(e) => setStudentInput(e.target.value)}
            placeholder="UUID"
            className="h-9 w-64 font-mono text-xs"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-muted-foreground">
            Schedule ID
          </label>
          <Input
            value={scheduleInput}
            onChange={(e) => setScheduleInput(e.target.value)}
            placeholder="UUID"
            className="h-9 w-64 font-mono text-xs"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-muted-foreground">
            Outcome
          </label>
          <Select value={matchedParam} onValueChange={(v) => setMatched(v as MatchedFilter)}>
            <SelectTrigger className="h-9 w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="matched">Matched only</SelectItem>
              <SelectItem value="missed">Missed only</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={applyTextFilters}>Apply</Button>
        {hasFilters && (
          <Button variant="ghost" onClick={clearAll}>
            Clear
          </Button>
        )}
      </div>

      <DataTable
        columns={columns}
        data={filteredItems}
        isLoading={isLoading}
        searchPlaceholder="Search by student, subject, camera, outcome…"
        globalFilter={searchQuery}
        onGlobalFilterChange={(v) => startSearchTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
      />

      {data?.next_cursor && (
        <div className="text-center text-xs text-muted-foreground">
          Showing {items.length} events. Export CSV for the complete filtered set.
        </div>
      )}
    </div>
  )
}

function CropLink({ url, label }: { url: string; label: string }) {
  // Both the <img> preview AND the click-to-open-in-new-tab path need the
  // bearer token. The preview gets it via useAuthedImage (blob URL); the
  // link itself drops the target="_blank" affordance since a new tab
  // would lack the auth context anyway. Clicking the thumbnail now opens
  // the blob URL inline, which is still useful for zooming in.
  const { src } = useAuthedImage(url)
  const href = src ?? undefined
  return (
    <a
      href={href}
      target={src ? '_blank' : undefined}
      rel="noreferrer"
      className="inline-flex h-10 w-10 items-center justify-center overflow-hidden rounded border bg-muted/30"
    >
      {src ? (
        <img src={src} alt={label} className="h-full w-full object-cover" />
      ) : (
        <span className="text-[9px] text-muted-foreground">—</span>
      )}
    </a>
  )
}

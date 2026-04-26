import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { Download, SlidersHorizontal } from 'lucide-react'

import { formatTimestamp, formatFullDatetime } from '@/lib/format-time'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RecognitionOutcomePill } from '@/components/shared/status-pills'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
              // The recognition record's `student_id` field is actually
              // the user's UUID (the backend stores user UUIDs in that
              // column). The `/students/:studentId` route expects the
              // human student ID like "21-A-02177", so we route through
              // `/users/:id` which accepts UUIDs and renders the same
              // student detail page when `user.role === 'student'`.
              <Link
                to={`/users/${row.original.student_id}`}
                state={{ role: 'student' }}
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

  if (isLoading) {
    // Mirror the loaded layout (header + DataTable toolbar + table + pagination)
    // so the cut-over to real data doesn't shift the page. Layout matches the
    // Students/Faculty/Admins registries for visual consistency across the
    // admin portal.
    return (
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-72" />
          </div>
          <Skeleton className="h-9 w-32 rounded-md" />
        </div>

        <div>
          {/* DataTable toolbar — search + outcome dropdown + More popover */}
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[150px] rounded-md" />
              <Skeleton className="h-9 w-20 rounded-md" />
            </div>
          </div>

          {/* Table */}
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Sim / Thr</TableHead>
                  <TableHead>Live</TableHead>
                  <TableHead>Registered</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`recog-skel-${String(i)}`}>
                    <TableCell>
                      <Skeleton className="h-3 w-24" />
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-3 w-20" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-40" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-10 w-10 rounded" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-10 w-10 rounded" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-2 py-4">
            <Skeleton className="h-4 w-44" />
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-[70px] rounded-md" />
              </div>
              <div className="flex items-center gap-1">
                <Skeleton className="h-8 w-8 rounded-md" />
                <Skeleton className="h-8 w-8 rounded-md" />
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Toolbar slot for the DataTable — same shape as the Students /
  // Faculty / Admins registries so the page reads as one consistent
  // surface across the admin portal. Outcome is the primary filter
  // (always visible); the rare-touched Student/Schedule UUID inputs
  // live behind a "More" popover with an active-count badge.
  const idFilterCount = (studentFilter ? 1 : 0) + (scheduleFilter ? 1 : 0)
  const filterToolbar = (
    <>
      <Select
        value={matchedParam}
        onValueChange={(v) => setMatched(v as MatchedFilter)}
      >
        <SelectTrigger className="w-[150px] h-9">
          <SelectValue placeholder="Outcome" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All outcomes</SelectItem>
          <SelectItem value="matched">Matched only</SelectItem>
          <SelectItem value="missed">Missed only</SelectItem>
        </SelectContent>
      </Select>

      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" className="h-9">
            <SlidersHorizontal className="h-3.5 w-3.5 mr-1.5" />
            More
            {idFilterCount > 0 && (
              <Badge variant="secondary" className="ml-1.5 h-4 px-1">
                {idFilterCount}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-80 space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">
              Student ID
            </label>
            <Input
              value={studentInput}
              onChange={(e) => setStudentInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyTextFilters()}
              placeholder="UUID"
              className="h-8 font-mono text-xs"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">
              Schedule ID
            </label>
            <Input
              value={scheduleInput}
              onChange={(e) => setScheduleInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyTextFilters()}
              placeholder="UUID"
              className="h-8 font-mono text-xs"
            />
          </div>
          <Button onClick={applyTextFilters} size="sm" className="w-full">
            Apply
          </Button>
        </PopoverContent>
      </Popover>

      {hasFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={clearAll}
          className="h-9 px-2 text-muted-foreground"
        >
          Clear
        </Button>
      )}
    </>
  )

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

      <DataTable
        columns={columns}
        data={filteredItems}
        isLoading={isLoading}
        searchPlaceholder="Search by student, subject, camera, outcome…"
        globalFilter={searchQuery}
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
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

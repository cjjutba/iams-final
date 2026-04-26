import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { safeFormat } from '@/lib/utils'
import { CalendarIcon } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useEarlyLeaves } from '@/hooks/use-queries'
import type { EarlyLeaveAlert } from '@/types'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'
import {
  ConsecutiveMissesPill,
  NotifiedPill,
  ReturnedPill,
} from '@/components/shared/status-pills'

function buildEarlyLeaveHaystack(a: EarlyLeaveAlert): string {
  return joinHaystack([
    a.student_name,
    a.student_student_id,
    a.subject_code,
    a.subject_name,
    a.date,
    ...isoDateHaystackParts(a.date),
    ...isoDateHaystackParts(a.detected_at),
    ...isoDateHaystackParts(a.last_seen_at),
    ...isoDateHaystackParts(a.returned_at),
    `${a.consecutive_misses} misses`,
    a.notified ? 'notified' : 'not notified',
    a.returned ? 'returned' : 'not returned',
  ])
}

const columns: ColumnDef<EarlyLeaveAlert>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.student_name}</div>
        {row.original.student_student_id && (
          <div className="font-mono text-xs text-muted-foreground">{row.original.student_student_id}</div>
        )}
      </div>
    ),
  },
  {
    accessorKey: 'subject_code',
    header: 'Subject',
    cell: ({ row }) => (
      <div>
        <div className="font-mono text-xs text-muted-foreground">{row.original.subject_code}</div>
        <div className="text-sm">{row.original.subject_name}</div>
      </div>
    ),
  },
  {
    accessorKey: 'date',
    header: 'Date',
    cell: ({ row }) => <span className="text-sm">{safeFormat(row.original.date, 'MMM d, yyyy')}</span>,
  },
  {
    accessorKey: 'detected_at',
    header: 'Detected',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums text-muted-foreground">
        {safeFormat(row.original.detected_at, 'h:mm a')}
      </span>
    ),
  },
  {
    accessorKey: 'last_seen_at',
    header: 'Last Seen',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums text-muted-foreground">
        {safeFormat(row.original.last_seen_at, 'h:mm a')}
      </span>
    ),
  },
  {
    accessorKey: 'consecutive_misses',
    header: 'Misses',
    cell: ({ row }) => <ConsecutiveMissesPill count={row.original.consecutive_misses} />,
  },
  {
    accessorKey: 'notified',
    header: 'Notified',
    cell: ({ row }) => <NotifiedPill notified={row.original.notified} />,
  },
  {
    accessorKey: 'returned',
    header: 'Returned',
    cell: ({ row }) => (
      <ReturnedPill
        returned={row.original.returned}
        returnedAt={
          row.original.returned_at
            ? safeFormat(row.original.returned_at, 'h:mm a')
            : undefined
        }
      />
    ),
  },
  {
    accessorKey: 'absence_duration_seconds',
    header: 'Duration',
    cell: ({ row }) => {
      const seconds = row.original.absence_duration_seconds
      if (!seconds) return <span className="text-sm text-muted-foreground">—</span>
      const mins = Math.floor(seconds / 60)
      const secs = seconds % 60
      return (
        <span className="text-sm tabular-nums text-muted-foreground">
          {mins > 0 ? `${mins}m ${secs}s` : `${secs}s`}
        </span>
      )
    },
  },
]

export default function EarlyLeavesPage() {
  usePageTitle('Early Leaves')
  const navigate = useNavigate()
  const { data: alerts = [], isLoading } = useEarlyLeaves()

  const [startDate, setStartDate] = useState<Date | undefined>(undefined)
  const [endDate, setEndDate] = useState<Date | undefined>(undefined)
  const [startOpen, setStartOpen] = useState(false)
  const [endOpen, setEndOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result: EarlyLeaveAlert[] = alerts
    if (startDate) {
      const start = format(startDate, 'yyyy-MM-dd')
      result = result.filter((a: EarlyLeaveAlert) => a.date >= start)
    }
    if (endDate) {
      const end = format(endDate, 'yyyy-MM-dd')
      result = result.filter((a: EarlyLeaveAlert) => a.date <= end)
    }
    if (searchQuery.trim()) {
      result = result.filter((a: EarlyLeaveAlert) =>
        tokenMatches(buildEarlyLeaveHaystack(a), searchQuery),
      )
    }
    return result
  }, [alerts, startDate, endDate, searchQuery])

  const hasFilters =
    startDate !== undefined || endDate !== undefined || searchQuery.trim().length > 0

  function clearFilters() {
    startTransition(() => {
      setStartDate(undefined)
      setEndDate(undefined)
      setSearchQuery('')
    })
  }

  const showSkeleton = isLoading || isPending

  const filterToolbar = (
    <>
      <Popover open={startOpen} onOpenChange={setStartOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-9 w-[150px] justify-start text-left font-normal">
            <CalendarIcon className="mr-2 h-3.5 w-3.5" />
            {startDate ? format(startDate, 'MMM d, yyyy') : 'Start date'}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={startDate}
            onSelect={(date) => {
              startTransition(() => setStartDate(date))
              setStartOpen(false)
            }}
            disabled={(date) => endDate ? date > endDate : false}
          />
        </PopoverContent>
      </Popover>

      <Popover open={endOpen} onOpenChange={setEndOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-9 w-[150px] justify-start text-left font-normal">
            <CalendarIcon className="mr-2 h-3.5 w-3.5" />
            {endDate ? format(endDate, 'MMM d, yyyy') : 'End date'}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={endDate}
            onSelect={(date) => {
              startTransition(() => setEndDate(date))
              setEndOpen(false)
            }}
            disabled={(date) => startDate ? date < startDate : false}
          />
        </PopoverContent>
      </Popover>

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2 text-muted-foreground">
          Clear
        </Button>
      )}
    </>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Early Leaves</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${filtered.length} of ${alerts.length} events`
                : `${alerts.length} early leave event${alerts.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={showSkeleton}
        searchPlaceholder="Search by student, subject, date, status..."
        globalFilter={searchQuery}
        onGlobalFilterChange={(v) => startTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}

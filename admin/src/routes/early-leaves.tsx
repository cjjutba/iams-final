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

type NotifiedFilter = 'all' | 'notified' | 'not_notified'
type ReturnedFilter = 'all' | 'returned' | 'not_returned'

export default function EarlyLeavesPage() {
  usePageTitle('Early Leaves')
  const navigate = useNavigate()
  const { data: alerts = [], isLoading } = useEarlyLeaves()

  const [startDate, setStartDate] = useState<Date | undefined>(undefined)
  const [endDate, setEndDate] = useState<Date | undefined>(undefined)
  const [startOpen, setStartOpen] = useState(false)
  const [endOpen, setEndOpen] = useState(false)
  const [notifiedFilter, setNotifiedFilter] = useState<NotifiedFilter>('all')
  const [returnedFilter, setReturnedFilter] = useState<ReturnedFilter>('all')
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
    if (notifiedFilter === 'notified') {
      result = result.filter((a) => a.notified)
    } else if (notifiedFilter === 'not_notified') {
      result = result.filter((a) => !a.notified)
    }
    if (returnedFilter === 'returned') {
      result = result.filter((a) => a.returned)
    } else if (returnedFilter === 'not_returned') {
      result = result.filter((a) => !a.returned)
    }
    if (searchQuery.trim()) {
      result = result.filter((a: EarlyLeaveAlert) =>
        tokenMatches(buildEarlyLeaveHaystack(a), searchQuery),
      )
    }
    return result
  }, [alerts, startDate, endDate, notifiedFilter, returnedFilter, searchQuery])

  const hasFilters =
    startDate !== undefined ||
    endDate !== undefined ||
    notifiedFilter !== 'all' ||
    returnedFilter !== 'all' ||
    searchQuery.trim().length > 0

  function clearFilters() {
    startTransition(() => {
      setStartDate(undefined)
      setEndDate(undefined)
      setNotifiedFilter('all')
      setReturnedFilter('all')
      setSearchQuery('')
    })
  }

  function handleSelectChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  const showSkeleton = isLoading || isPending

  const filterToolbar = (
    <>
      <Select value={notifiedFilter} onValueChange={handleSelectChange(setNotifiedFilter)}>
        <SelectTrigger className="w-[170px] h-9">
          <SelectValue placeholder="Notified" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All notification</SelectItem>
          <SelectItem value="notified">Notified</SelectItem>
          <SelectItem value="not_notified">Not notified</SelectItem>
        </SelectContent>
      </Select>

      <Select value={returnedFilter} onValueChange={handleSelectChange(setReturnedFilter)}>
        <SelectTrigger className="w-[160px] h-9">
          <SelectValue placeholder="Returned" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All returns</SelectItem>
          <SelectItem value="returned">Returned</SelectItem>
          <SelectItem value="not_returned">Not returned</SelectItem>
        </SelectContent>
      </Select>

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

  if (isLoading) {
    // Mirror the loaded layout (header + toolbar + table + pagination) so
    // the cut-over to real data doesn't shift the page.
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-32" />
            <Skeleton className="h-4 w-44" />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[170px] rounded-md" />
              <Skeleton className="h-9 w-[160px] rounded-md" />
              <Skeleton className="h-9 w-[150px] rounded-md" />
              <Skeleton className="h-9 w-[150px] rounded-md" />
            </div>
          </div>

          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Detected</TableHead>
                  <TableHead>Last Seen</TableHead>
                  <TableHead>Misses</TableHead>
                  <TableHead>Notified</TableHead>
                  <TableHead>Returned</TableHead>
                  <TableHead>Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`el-skel-${String(i)}`}>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-4 w-36" />
                        <Skeleton className="h-3 w-20" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-3 w-24" />
                        <Skeleton className="h-3 w-32" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-12 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-12" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Early Leaves</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {hasFilters
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
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}

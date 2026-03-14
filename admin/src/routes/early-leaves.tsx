import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useEarlyLeaves } from '@/hooks/use-queries'
import type { EarlyLeaveAlert } from '@/types'

const columns: ColumnDef<EarlyLeaveAlert>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.student_name}</div>
        {row.original.student_student_id && (
          <div className="text-sm text-muted-foreground font-mono">{row.original.student_student_id}</div>
        )}
      </div>
    ),
  },
  {
    accessorKey: 'subject_code',
    header: 'Subject',
    cell: ({ row }) => (
      <div>
        <div className="text-sm font-medium">{row.original.subject_code}</div>
        <div className="text-sm text-muted-foreground">{row.original.subject_name}</div>
      </div>
    ),
  },
  {
    accessorKey: 'date',
    header: 'Date',
    cell: ({ row }) => {
      try {
        return <span className="text-sm">{format(new Date(row.original.date), 'MMM d, yyyy')}</span>
      } catch {
        return <span className="text-sm">{row.original.date}</span>
      }
    },
  },
  {
    accessorKey: 'detected_at',
    header: 'Detected At',
    cell: ({ row }) => {
      try {
        return <span className="text-sm">{format(new Date(row.original.detected_at), 'h:mm a')}</span>
      } catch {
        return <span className="text-sm">{row.original.detected_at}</span>
      }
    },
  },
  {
    accessorKey: 'last_seen_at',
    header: 'Last Seen',
    cell: ({ row }) => {
      try {
        return <span className="text-sm">{format(new Date(row.original.last_seen_at), 'h:mm a')}</span>
      } catch {
        return <span className="text-sm">{row.original.last_seen_at}</span>
      }
    },
  },
  {
    accessorKey: 'consecutive_misses',
    header: 'Misses',
    cell: ({ row }) => (
      <Badge variant={row.original.consecutive_misses >= 3 ? 'destructive' : 'secondary'}>
        {row.original.consecutive_misses}
      </Badge>
    ),
  },
  {
    accessorKey: 'notified',
    header: 'Notified',
    cell: ({ row }) =>
      row.original.notified ? (
        <Badge variant="default">Yes</Badge>
      ) : (
        <span className="text-sm text-muted-foreground">No</span>
      ),
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
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result = alerts
    if (startDate) {
      const start = format(startDate, 'yyyy-MM-dd')
      result = result.filter((a) => a.date >= start)
    }
    if (endDate) {
      const end = format(endDate, 'yyyy-MM-dd')
      result = result.filter((a) => a.date <= end)
    }
    return result
  }, [alerts, startDate, endDate])

  const hasFilters = startDate !== undefined || endDate !== undefined

  function clearFilters() {
    startTransition(() => {
      setStartDate(undefined)
      setEndDate(undefined)
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
        searchPlaceholder="Search students..."
        searchColumn="student_name"
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}

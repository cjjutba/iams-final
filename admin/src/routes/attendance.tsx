import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { safeFormat } from '@/lib/utils'
import { CalendarIcon, Download, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
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
import { useAttendanceList } from '@/hooks/use-queries'
import { attendanceService } from '@/services/attendance.service'
import type { AttendanceRecord } from '@/types'
import { formatStatus } from '@/types/attendance'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'
import { AttendanceStatusPill } from '@/components/shared/status-pills'

function buildAttendanceHaystack(r: AttendanceRecord): string {
  return joinHaystack([
    r.student_name,
    r.student_id,
    r.subject_code,
    formatStatus(r.status),
    r.status,
    r.remarks,
    r.date,
    ...isoDateHaystackParts(r.date),
    ...isoDateHaystackParts(r.check_in_time),
    ...isoDateHaystackParts(r.check_out_time),
    `${Math.round(r.presence_score)}%`,
  ])
}

const columns: ColumnDef<AttendanceRecord>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
    cell: ({ row }) => (
      <span className="text-sm font-medium">
        {row.original.student_name ?? '—'}
      </span>
    ),
  },
  {
    accessorKey: 'subject_code',
    header: 'Subject',
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.original.subject_code ?? '—'}
      </span>
    ),
  },
  {
    accessorKey: 'date',
    header: 'Date',
    cell: ({ row }) => (
      <span className="text-sm">{safeFormat(row.original.date, 'MMM d, yyyy')}</span>
    ),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <AttendanceStatusPill status={row.original.status} />,
  },
  {
    accessorKey: 'check_in_time',
    header: 'Check-in',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums text-muted-foreground">
        {safeFormat(row.original.check_in_time, 'h:mm a')}
      </span>
    ),
  },
  {
    accessorKey: 'check_out_time',
    header: 'Check-out',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums text-muted-foreground">
        {safeFormat(row.original.check_out_time, 'h:mm a')}
      </span>
    ),
  },
  {
    accessorKey: 'presence_score',
    header: 'Presence',
    cell: ({ row }) => {
      const score = row.original.presence_score
      const color =
        score >= 85
          ? 'text-emerald-600 dark:text-emerald-400'
          : score >= 70
            ? 'text-amber-600 dark:text-amber-400'
            : 'text-red-600 dark:text-red-400'
      return (
        <span className={`font-mono text-xs tabular-nums ${color}`}>
          {score.toFixed(0)}%
        </span>
      )
    },
  },
]

export default function AttendancePage() {
  usePageTitle('Attendance')
  const navigate = useNavigate()
  const [startDate, setStartDate] = useState<Date | undefined>(undefined)
  const [endDate, setEndDate] = useState<Date | undefined>(undefined)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [exporting, setExporting] = useState(false)
  const [startOpen, setStartOpen] = useState(false)
  const [endOpen, setEndOpen] = useState(false)

  const queryParams = useMemo(() => {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = format(startDate, 'yyyy-MM-dd')
    if (endDate) params.end_date = format(endDate, 'yyyy-MM-dd')
    if (statusFilter !== 'all') params.status = statusFilter
    return params
  }, [startDate, endDate, statusFilter])

  const { data: records = [], isLoading } = useAttendanceList(queryParams)

  const [searchQuery, setSearchQuery] = useState('')

  const filteredRecords = useMemo(() => {
    if (!searchQuery.trim()) return records
    return records.filter((r) => tokenMatches(buildAttendanceHaystack(r), searchQuery))
  }, [records, searchQuery])

  const hasFilters =
    startDate !== undefined ||
    endDate !== undefined ||
    statusFilter !== 'all' ||
    searchQuery.trim().length > 0

  const clearFilters = () => {
    setStartDate(undefined)
    setEndDate(undefined)
    setStatusFilter('all')
    setSearchQuery('')
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const params: Record<string, string> = { format: 'csv' }
      if (startDate) params.start_date = format(startDate, 'yyyy-MM-dd')
      if (endDate) params.end_date = format(endDate, 'yyyy-MM-dd')
      if (statusFilter !== 'all') params.status = statusFilter
      const blob = await attendanceService.export({ ...params, format: 'csv' })
      const url = URL.createObjectURL(blob as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `attendance-export-${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Export downloaded')
    } catch {
      toast.error('Failed to export attendance data')
    } finally {
      setExporting(false)
    }
  }

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
              setStartDate(date)
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
              setEndDate(date)
              setEndOpen(false)
            }}
            disabled={(date) => startDate ? date < startDate : false}
          />
        </PopoverContent>
      </Popover>

      <Select value={statusFilter} onValueChange={setStatusFilter}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="All status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All status</SelectItem>
          <SelectItem value="present">Present</SelectItem>
          <SelectItem value="late">Late</SelectItem>
          <SelectItem value="absent">Absent</SelectItem>
          <SelectItem value="excused">Excused</SelectItem>
          <SelectItem value="early_leave">Early Leave</SelectItem>
        </SelectContent>
      </Select>

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
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-44" />
          </div>
          <Skeleton className="h-9 w-32 rounded-md" />
        </div>

        <div>
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[150px] rounded-md" />
              <Skeleton className="h-9 w-[150px] rounded-md" />
              <Skeleton className="h-9 w-[140px] rounded-md" />
            </div>
          </div>

          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Presence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`att-skel-${String(i)}`}>
                    <TableCell>
                      <Skeleton className="h-4 w-40" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-3 w-28" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-10" />
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
          <h1 className="text-2xl font-semibold tracking-tight">Attendance Overview</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {hasFilters
              ? `${filteredRecords.length} of ${records.length} records`
              : `${records.length} attendance record${records.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <Button variant="outline" onClick={() => void handleExport()} disabled={exporting || records.length === 0}>
          {exporting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              Export CSV
            </>
          )}
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={filteredRecords}
        isLoading={isLoading}
        searchPlaceholder="Search by student, subject, status, date..."
        globalFilter={searchQuery}
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}

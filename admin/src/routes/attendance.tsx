import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { safeFormat } from '@/lib/utils'
import { CalendarIcon, Download, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAttendanceList } from '@/hooks/use-queries'
import { attendanceService } from '@/services/attendance.service'
import type { AttendanceRecord, AttendanceStatus } from '@/types'
import { formatStatus } from '@/types/attendance'

const statusColors: Record<AttendanceStatus, string> = {
  present: 'bg-green-100 text-green-800 hover:bg-green-100',
  late: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
  absent: 'bg-red-100 text-red-800 hover:bg-red-100',
  excused: 'bg-blue-100 text-blue-800 hover:bg-blue-100',
  early_leave: 'bg-orange-100 text-orange-800 hover:bg-orange-100',
}

const columns: ColumnDef<AttendanceRecord>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
    cell: ({ row }) => row.original.student_name ?? '\u2014',
  },
  {
    accessorKey: 'subject_code',
    header: 'Subject',
    cell: ({ row }) => row.original.subject_code ?? '\u2014',
  },
  {
    accessorKey: 'date',
    header: 'Date',
    cell: ({ row }) => safeFormat(row.original.date, 'MMM d, yyyy'),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <Badge className={statusColors[row.original.status]}>
        {formatStatus(row.original.status)}
      </Badge>
    ),
  },
  {
    accessorKey: 'check_in_time',
    header: 'Check-in',
    cell: ({ row }) => safeFormat(row.original.check_in_time, 'h:mm a'),
  },
  {
    accessorKey: 'presence_score',
    header: 'Presence Score',
    cell: ({ row }) => {
      const score = row.original.presence_score
      const color = score >= 85 ? 'text-green-600' : score >= 70 ? 'text-yellow-600' : 'text-red-600'
      return <span className={`font-medium ${color}`}>{score.toFixed(0)}%</span>
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

  const hasFilters = startDate !== undefined || endDate !== undefined || statusFilter !== 'all'

  const clearFilters = () => {
    setStartDate(undefined)
    setEndDate(undefined)
    setStatusFilter('all')
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
          <SelectValue placeholder="All Statuses" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Statuses</SelectItem>
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Attendance Overview</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${records.length} filtered records`
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
        data={records}
        isLoading={isLoading}
        searchPlaceholder="Search students..."
        searchColumn="student_name"
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}

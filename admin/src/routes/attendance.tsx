import { useState, useEffect, useCallback } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { CalendarIcon, Download } from 'lucide-react'
import { toast } from 'sonner'

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
import { attendanceService } from '@/services/attendance.service'
import type { AttendanceRecord, AttendanceStatus } from '@/types'

const statusColors: Record<AttendanceStatus, string> = {
  PRESENT: 'bg-green-100 text-green-800 hover:bg-green-100',
  LATE: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
  ABSENT: 'bg-red-100 text-red-800 hover:bg-red-100',
  EXCUSED: 'bg-blue-100 text-blue-800 hover:bg-blue-100',
  EARLY_LEAVE: 'bg-orange-100 text-orange-800 hover:bg-orange-100',
}

const columns: ColumnDef<AttendanceRecord>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
    cell: ({ row }) => row.original.student_name ?? '—',
  },
  {
    accessorKey: 'subject_code',
    header: 'Subject',
    cell: ({ row }) => row.original.subject_code ?? '—',
  },
  {
    accessorKey: 'date',
    header: 'Date',
    cell: ({ row }) => {
      try {
        return format(new Date(row.original.date), 'MMM d, yyyy')
      } catch {
        return row.original.date
      }
    },
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <Badge className={statusColors[row.original.status]}>
        {row.original.status.replace('_', ' ')}
      </Badge>
    ),
  },
  {
    accessorKey: 'check_in_time',
    header: 'Check-in',
    cell: ({ row }) => {
      const t = row.original.check_in_time
      if (!t) return '—'
      try {
        return format(new Date(t), 'h:mm a')
      } catch {
        return t
      }
    },
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
  const [records, setRecords] = useState<AttendanceRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [startDate, setStartDate] = useState<Date | undefined>(undefined)
  const [endDate, setEndDate] = useState<Date | undefined>(undefined)
  const [status, setStatus] = useState<string>('all')
  const [exporting, setExporting] = useState(false)

  const fetchRecords = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (startDate) params.start_date = format(startDate, 'yyyy-MM-dd')
      if (endDate) params.end_date = format(endDate, 'yyyy-MM-dd')
      if (status !== 'all') params.status = status
      const data = await attendanceService.list(params)
      setRecords(data)
    } catch {
      toast.error('Failed to load attendance records')
    } finally {
      setLoading(false)
    }
  }, [startDate, endDate, status])

  useEffect(() => {
    void fetchRecords()
  }, [fetchRecords])

  const handleExport = async () => {
    setExporting(true)
    try {
      const params: Record<string, string> = { format: 'csv' }
      if (startDate) params.start_date = format(startDate, 'yyyy-MM-dd')
      if (endDate) params.end_date = format(endDate, 'yyyy-MM-dd')
      if (status !== 'all') params.status = status
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Attendance Overview</h1>
        <p className="text-muted-foreground">View and export attendance records</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-[180px] justify-start text-left font-normal">
              <CalendarIcon className="mr-2 h-4 w-4" />
              {startDate ? format(startDate, 'MMM d, yyyy') : 'Start date'}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar mode="single" selected={startDate} onSelect={setStartDate} />
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-[180px] justify-start text-left font-normal">
              <CalendarIcon className="mr-2 h-4 w-4" />
              {endDate ? format(endDate, 'MMM d, yyyy') : 'End date'}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar mode="single" selected={endDate} onSelect={setEndDate} />
          </PopoverContent>
        </Popover>

        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="PRESENT">Present</SelectItem>
            <SelectItem value="LATE">Late</SelectItem>
            <SelectItem value="ABSENT">Absent</SelectItem>
            <SelectItem value="EXCUSED">Excused</SelectItem>
            <SelectItem value="EARLY_LEAVE">Early Leave</SelectItem>
          </SelectContent>
        </Select>

        <Button variant="outline" onClick={() => void handleExport()} disabled={exporting}>
          <Download className="mr-2 h-4 w-4" />
          {exporting ? 'Exporting...' : 'Export CSV'}
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={records}
        isLoading={loading}
        searchPlaceholder="Search students..."
        searchColumn="student_name"
      />
    </div>
  )
}

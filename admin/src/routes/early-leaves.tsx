import { useState, useEffect, useCallback } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { attendanceService } from '@/services/attendance.service'
import type { EarlyLeaveAlert } from '@/types'

const columns: ColumnDef<EarlyLeaveAlert>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
  },
  {
    accessorKey: 'subject_name',
    header: 'Subject',
  },
  {
    accessorKey: 'detected_at',
    header: 'Detected At',
    cell: ({ row }) => {
      try {
        return format(new Date(row.original.detected_at), 'MMM d, yyyy h:mm a')
      } catch {
        return row.original.detected_at
      }
    },
  },
  {
    accessorKey: 'last_seen_at',
    header: 'Last Seen',
    cell: ({ row }) => {
      try {
        return format(new Date(row.original.last_seen_at), 'h:mm a')
      } catch {
        return row.original.last_seen_at
      }
    },
  },
  {
    accessorKey: 'consecutive_misses',
    header: 'Consecutive Misses',
    cell: ({ row }) => (
      <Badge className={row.original.consecutive_misses >= 3
        ? 'bg-red-100 text-red-800 hover:bg-red-100'
        : 'bg-gray-100 text-gray-800 hover:bg-gray-100'
      }>
        {row.original.consecutive_misses}
      </Badge>
    ),
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
]

export default function EarlyLeavesPage() {
  const [alerts, setAlerts] = useState<EarlyLeaveAlert[]>([])
  const [loading, setLoading] = useState(true)

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await attendanceService.getAlerts()
      setAlerts(data)
    } catch {
      toast.error('Failed to load early leave alerts')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchAlerts()
  }, [fetchAlerts])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Early Leave Monitoring</h1>
        <p className="text-muted-foreground">Track students who left class early</p>
      </div>

      <DataTable
        columns={columns}
        data={alerts}
        isLoading={loading}
        searchPlaceholder="Search students..."
        searchColumn="student_name"
      />
    </div>
  )
}

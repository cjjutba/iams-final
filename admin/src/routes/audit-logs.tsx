import { useCallback, useEffect, useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { format, parseISO } from 'date-fns'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { auditService } from '@/services/audit.service'

interface AuditLog {
  id: string
  created_at: string
  action: string
  target_type: string
  target_id: string | null
  details: string | null
  user_id: string | null
}

const ACTION_OPTIONS = [
  { value: '__all__', label: 'All Actions' },
  { value: 'create', label: 'Create' },
  { value: 'update', label: 'Update' },
  { value: 'delete', label: 'Delete' },
  { value: 'login', label: 'Login' },
  { value: 'logout', label: 'Logout' },
]

const TARGET_TYPE_OPTIONS = [
  { value: '__all__', label: 'All Types' },
  { value: 'user', label: 'User' },
  { value: 'room', label: 'Room' },
  { value: 'schedule', label: 'Schedule' },
  { value: 'attendance', label: 'Attendance' },
  { value: 'setting', label: 'Setting' },
]

const columns: ColumnDef<AuditLog>[] = [
  {
    accessorKey: 'created_at',
    header: 'Timestamp',
    cell: ({ row }) => {
      try {
        return (
          <span className="text-sm whitespace-nowrap">
            {format(parseISO(row.original.created_at), 'MMM d, yyyy h:mm a')}
          </span>
        )
      } catch {
        return <span className="text-sm">{row.original.created_at}</span>
      }
    },
  },
  {
    accessorKey: 'action',
    header: 'Action',
    cell: ({ row }) => (
      <Badge variant="outline">{row.original.action}</Badge>
    ),
  },
  {
    accessorKey: 'target_type',
    header: 'Target Type',
    cell: ({ row }) => (
      <span className="text-sm">{row.original.target_type}</span>
    ),
  },
  {
    accessorKey: 'target_id',
    header: 'Target ID',
    cell: ({ row }) => (
      <span className="text-sm font-mono">
        {row.original.target_id ?? '\u2014'}
      </span>
    ),
  },
  {
    accessorKey: 'details',
    header: 'Details',
    cell: ({ row }) => {
      const details = row.original.details
      if (!details) return <span className="text-sm text-muted-foreground">\u2014</span>
      const truncated = details.length > 80 ? `${details.slice(0, 80)}...` : details
      return (
        <span className="text-sm" title={details}>
          {truncated}
        </span>
      )
    },
  },
]

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState('__all__')
  const [targetTypeFilter, setTargetTypeFilter] = useState('__all__')

  const fetchLogs = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = { limit: 100 }
      if (actionFilter !== '__all__') params.action = actionFilter
      if (targetTypeFilter !== '__all__') params.target_type = targetTypeFilter

      const data = await auditService.getLogs(params)
      setLogs(Array.isArray(data) ? data : data.items ?? [])
    } catch {
      setError('Unable to load audit logs')
      setLogs([])
    } finally {
      setIsLoading(false)
    }
  }, [actionFilter, targetTypeFilter])

  useEffect(() => {
    void fetchLogs()
  }, [fetchLogs])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Audit Logs</h1>
        <p className="text-muted-foreground mt-1">
          {isLoading
            ? 'Loading audit logs...'
            : error
              ? error
              : `${logs.length} log${logs.length !== 1 ? 's' : ''}`}
        </p>
      </div>

      {error && !isLoading ? (
        <div className="rounded-md border border-dashed p-8 text-center">
          <p className="text-muted-foreground">{error}</p>
          <Button variant="outline" className="mt-4" onClick={fetchLogs}>
            Retry
          </Button>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={logs}
          isLoading={isLoading}
          searchColumn="action"
          searchPlaceholder="Search by action..."
          toolbar={
            <div className="flex gap-2">
              <Select value={actionFilter} onValueChange={setActionFilter}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Action" />
                </SelectTrigger>
                <SelectContent>
                  {ACTION_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={targetTypeFilter} onValueChange={setTargetTypeFilter}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Target Type" />
                </SelectTrigger>
                <SelectContent>
                  {TARGET_TYPE_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          }
        />
      )}
    </div>
  )
}

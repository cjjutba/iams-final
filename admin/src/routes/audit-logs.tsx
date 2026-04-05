import { useMemo, useState, useTransition } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { usePageTitle } from '@/hooks/use-page-title'

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
import { useAuditLogs } from '@/hooks/use-queries'

interface AuditLog {
  id: string
  created_at: string
  action: string
  target_type: string
  target_id: string | null
  details: string | null
  admin_id: string | null
}

const columns: ColumnDef<AuditLog>[] = [
  {
    accessorKey: 'created_at',
    header: 'Timestamp',
    cell: ({ row }) => (
      <span className="text-sm whitespace-nowrap">
        {safeFormat(row.original.created_at, 'MMM d, yyyy h:mm a')}
      </span>
    ),
  },
  {
    accessorKey: 'action',
    header: 'Action',
    cell: ({ row }) => {
      const action = row.original.action
      const variant = action === 'delete' ? 'destructive' as const : 'outline' as const
      return <Badge variant={variant}>{action.charAt(0).toUpperCase() + action.slice(1)}</Badge>
    },
  },
  {
    accessorKey: 'target_type',
    header: 'Target Type',
    cell: ({ row }) => (
      <span className="text-sm">
        {row.original.target_type.charAt(0).toUpperCase() + row.original.target_type.slice(1)}
      </span>
    ),
  },
  {
    accessorKey: 'target_id',
    header: 'Target ID',
    cell: ({ row }) => (
      <span className="text-sm font-mono">
        {row.original.target_id ? row.original.target_id.slice(0, 8) + '...' : '\u2014'}
      </span>
    ),
  },
  {
    accessorKey: 'details',
    header: 'Details',
    cell: ({ row }) => {
      const details = row.original.details
      if (!details) return <span className="text-sm text-muted-foreground">{'\u2014'}</span>
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
  usePageTitle('Audit Logs')

  const [actionFilter, setActionFilter] = useState('all')
  const [targetTypeFilter, setTargetTypeFilter] = useState('all')
  const [isPending, startTransition] = useTransition()

  const queryParams = useMemo(() => {
    const params: Record<string, string | number> = { limit: 100 }
    if (actionFilter !== 'all') params.action = actionFilter
    if (targetTypeFilter !== 'all') params.target_type = targetTypeFilter
    return params
  }, [actionFilter, targetTypeFilter])

  const { data: rawData, isLoading } = useAuditLogs(queryParams)
  const logs: AuditLog[] = Array.isArray(rawData)
    ? rawData
    : (rawData as { items?: AuditLog[] })?.items ?? []

  const hasFilters = actionFilter !== 'all' || targetTypeFilter !== 'all'

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setActionFilter('all')
      setTargetTypeFilter('all')
    })
  }

  const showSkeleton = isLoading || isPending

  const filterToolbar = (
    <>
      <Select value={actionFilter} onValueChange={handleFilterChange(setActionFilter)}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="Action" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Actions</SelectItem>
          <SelectItem value="create">Create</SelectItem>
          <SelectItem value="update">Update</SelectItem>
          <SelectItem value="delete">Delete</SelectItem>
          <SelectItem value="login">Login</SelectItem>
          <SelectItem value="logout">Logout</SelectItem>
        </SelectContent>
      </Select>

      <Select value={targetTypeFilter} onValueChange={handleFilterChange(setTargetTypeFilter)}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="Target Type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          <SelectItem value="user">User</SelectItem>
          <SelectItem value="room">Room</SelectItem>
          <SelectItem value="schedule">Schedule</SelectItem>
          <SelectItem value="attendance">Attendance</SelectItem>
          <SelectItem value="setting">Setting</SelectItem>
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
          <h1 className="text-2xl font-semibold tracking-tight">Audit Logs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${logs.length} filtered log${logs.length !== 1 ? 's' : ''}`
                : `${logs.length} log entr${logs.length !== 1 ? 'ies' : 'y'}`}
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={logs}
        isLoading={showSkeleton}
        searchColumn="action"
        searchPlaceholder="Search by action..."
        toolbar={filterToolbar}
      />
    </div>
  )
}

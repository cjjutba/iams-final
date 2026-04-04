import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
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
import { useEdgeStatus } from '@/hooks/use-queries'

interface EdgeDevice {
  id: string
  name: string
  building: string
  camera_endpoint: string
  stream_key: string
  is_active: boolean
  capacity: number | null
  status: 'scanning' | 'idle'
  schedule_count: number
  session: {
    schedule_id: string
    subject: string
    started_at: string
    ends_at: string
  } | null
}

interface EdgeStatusResponse {
  total_devices: number
  scanning_devices: number
  idle_devices: number
  devices: EdgeDevice[]
}

type StatusFilter = 'all' | 'scanning' | 'idle'

const columns: ColumnDef<EdgeDevice>[] = [
  {
    accessorKey: 'name',
    header: 'Room',
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.name}</div>
        {row.original.building && (
          <div className="text-sm text-muted-foreground">{row.original.building}</div>
        )}
      </div>
    ),
  },
  {
    accessorKey: 'camera_endpoint',
    header: 'Endpoint',
    cell: ({ row }) => (
      <span className="text-sm font-mono">{row.original.camera_endpoint}</span>
    ),
  },
  {
    accessorKey: 'stream_key',
    header: 'Stream Key',
    cell: ({ row }) => (
      <span className="text-sm font-mono">{row.original.stream_key ?? '\u2014'}</span>
    ),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) =>
      row.original.status === 'scanning' ? (
        <Badge variant="default">Scanning</Badge>
      ) : (
        <Badge variant="secondary">Idle</Badge>
      ),
  },
  {
    accessorKey: 'session',
    header: 'Current Session',
    cell: ({ row }) => {
      const session = row.original.session
      if (!session) return <span className="text-sm text-muted-foreground">{'\u2014'}</span>
      return (
        <div>
          <div className="text-sm font-medium">{session.subject}</div>
        </div>
      )
    },
  },
  {
    accessorKey: 'schedule_count',
    header: 'Schedules',
    cell: ({ row }) => (
      <span className="text-sm">{row.original.schedule_count}</span>
    ),
  },
  {
    accessorKey: 'is_active',
    header: 'Room Status',
    cell: ({ row }) =>
      row.original.is_active ? (
        <Badge variant="default">Active</Badge>
      ) : (
        <Badge variant="destructive">Inactive</Badge>
      ),
  },
]

export default function EdgeDevicesPage() {
  usePageTitle('Edge Devices')
  const navigate = useNavigate()
  const { data: rawData, isLoading } = useEdgeStatus()
  const statusData = rawData as EdgeStatusResponse | null | undefined
  const devices: EdgeDevice[] = statusData?.devices ?? []

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    if (statusFilter === 'all') return devices
    return devices.filter((d) => d.status === statusFilter)
  }, [devices, statusFilter])

  const hasFilters = statusFilter !== 'all'

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setStatusFilter('all')
    })
  }

  const showSkeleton = isLoading || isPending

  const filterToolbar = (
    <>
      <Select value={statusFilter} onValueChange={handleFilterChange(setStatusFilter)}>
        <SelectTrigger className="w-[130px] h-9">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Status</SelectItem>
          <SelectItem value="scanning">Scanning</SelectItem>
          <SelectItem value="idle">Idle</SelectItem>
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
          <h1 className="text-2xl font-semibold tracking-tight">Edge Devices</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : devices.length === 0
                ? 'No edge devices configured'
                : hasFilters
                  ? `${filtered.length} of ${devices.length} devices`
                  : `${devices.length} device${devices.length !== 1 ? 's' : ''} \u00B7 ${statusData?.scanning_devices ?? 0} scanning`}
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={showSkeleton}
        searchColumn="name"
        searchPlaceholder="Search rooms..."
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/edge-devices/${row.id}`)}
      />
    </div>
  )
}

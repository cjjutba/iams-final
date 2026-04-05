import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import {
  ArrowLeft,
  Building2,
  Cpu,
  Radio,
  Video,
  Calendar,
  Users,
} from 'lucide-react'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useEdgeDevice } from '@/hooks/use-queries'

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

interface DeviceSchedule {
  id: string
  subject_code: string
  subject_name: string
  day_of_week: number
  day_name: string
  start_time: string | null
  end_time: string | null
  faculty_id: string
}

function formatTime(time: string | null): string {
  if (!time) return ''
  const [hours, minutes] = time.split(':')
  const h = parseInt(hours, 10)
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${String(h12)}:${minutes} ${ampm}`
}

const scheduleColumns: ColumnDef<DeviceSchedule>[] = [
  {
    accessorKey: 'subject_name',
    header: 'Subject',
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.subject_code}</div>
        <div className="text-sm text-muted-foreground">{row.original.subject_name}</div>
      </div>
    ),
  },
  {
    accessorKey: 'day_of_week',
    header: 'Day',
    cell: ({ row }) => (
      <span className="text-sm">{row.original.day_name}</span>
    ),
  },
  {
    id: 'time',
    header: 'Time',
    enableSorting: false,
    cell: ({ row }) => (
      <span className="text-sm">
        {formatTime(row.original.start_time)} - {formatTime(row.original.end_time)}
      </span>
    ),
  },
]

export default function EdgeDeviceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: device, isLoading } = useEdgeDevice(id!)

  const deviceName = device?.name ?? null
  usePageTitle(deviceName ?? 'Edge Device Details')

  useEffect(() => {
    if (deviceName) setLabel(deviceName)
    return () => setLabel(null)
  }, [deviceName, setLabel])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!device) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/edge-devices')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Edge Devices
        </Button>
        <p className="text-muted-foreground">Edge device not found.</p>
      </div>
    )
  }

  const schedules: DeviceSchedule[] = device.schedules ?? []

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/edge-devices')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Edge Devices
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-xl">{device.name}</CardTitle>
              <div className="mt-2 flex items-center gap-2">
                {device.is_active ? (
                  <Badge variant="default">Active</Badge>
                ) : (
                  <Badge variant="destructive">Inactive</Badge>
                )}
                {device.status === 'scanning' ? (
                  <Badge variant="default">Scanning</Badge>
                ) : (
                  <Badge variant="secondary">Idle</Badge>
                )}
              </div>
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-center gap-3">
              <Building2 className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Building</p>
                <p className="text-sm font-medium">{device.building ?? '\u2014'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Users className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Capacity</p>
                <p className="text-sm font-medium">
                  {device.capacity != null ? device.capacity : '\u2014'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Video className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Camera Endpoint</p>
                <p className="text-sm font-medium font-mono">
                  {device.camera_endpoint ?? 'Not configured'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Radio className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Stream Key</p>
                <p className="text-sm font-medium font-mono">
                  {device.stream_key ?? '\u2014'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Assigned Schedules</p>
                <p className="text-sm font-medium">{schedules.length}</p>
              </div>
            </div>
            {device.session && (
              <div className="flex items-center gap-3">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Current Session</p>
                  <p className="text-sm font-medium">{device.session.subject}</p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div>
        <h3 className="text-lg font-semibold mb-4">Assigned Schedules</h3>
        <DataTable
          columns={scheduleColumns}
          data={schedules}
          searchColumn="subject_name"
          searchPlaceholder="Search by subject..."
          onRowClick={(row) => navigate(`/schedules/${row.id}`)}
        />
      </div>
    </div>
  )
}

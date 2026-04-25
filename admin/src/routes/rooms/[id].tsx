import { useState, useEffect, useMemo, useTransition } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  ArrowLeft,
  Building2,
  DoorOpen,
  Loader2,
  Users,
  Video,
  Pencil,
} from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useRoom, useSchedules, useUpdateRoom } from '@/hooks/use-queries'
import type { ScheduleResponse } from '@/types'
import { tokenMatches, joinHaystack, formatTime12h, DAY_NAMES_MON_FIRST } from '@/lib/search'

function buildScheduleHaystackForRoom(s: ScheduleResponse): string {
  return joinHaystack([
    s.subject_code,
    s.subject_name,
    s.faculty ? `${s.faculty.first_name} ${s.faculty.last_name}` : 'Unassigned',
    s.faculty?.first_name,
    s.faculty?.last_name,
    s.faculty_name,
    DAY_NAMES_MON_FIRST[s.day_of_week],
    s.start_time,
    s.end_time,
    formatTime12h(s.start_time),
    formatTime12h(s.end_time),
    `${formatTime12h(s.start_time)} - ${formatTime12h(s.end_time)}`,
    s.is_active ? 'Active' : 'Inactive',
    s.semester,
    s.academic_year,
    s.target_course,
    s.target_year_level != null ? `Year ${s.target_year_level}` : null,
  ])
}

// Indexed Monday-first to match the backend's `day_of_week` convention
// (0=Mon..6=Sun — see backend/scripts/seed_data.py).
const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function formatTime(time: string): string {
  if (!time) return ''
  const [hours, minutes] = time.split(':')
  const h = parseInt(hours, 10)
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${String(h12)}:${minutes} ${ampm}`
}

const editFormSchema = z.object({
  name: z.string().min(1, 'Room name is required'),
  building: z.string().optional(),
  capacity: z.string().optional(),
  camera_endpoint: z.string().optional(),
})

type EditFormValues = z.infer<typeof editFormSchema>

export default function RoomDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: room, isLoading } = useRoom(id!)

  const roomName = room?.name ?? null
  usePageTitle(roomName ?? 'Room Details')

  useEffect(() => {
    if (roomName) setLabel(roomName)
    return () => setLabel(null)
  }, [roomName, setLabel])
  const { data: allSchedules = [] } = useSchedules()
  const updateRoom = useUpdateRoom()

  const [editOpen, setEditOpen] = useState(false)

  const form = useForm<EditFormValues>({
    resolver: zodResolver(editFormSchema),
    defaultValues: { name: '', building: '', capacity: '', camera_endpoint: '' },
  })

  useEffect(() => {
    if (room && editOpen) {
      form.reset({
        name: room.name,
        building: room.building ?? '',
        capacity: room.capacity != null ? String(room.capacity) : '',
        camera_endpoint: room.camera_endpoint ?? '',
      })
    }
  }, [room, editOpen, form])

  const roomSchedules = useMemo(
    () => allSchedules.filter((s: ScheduleResponse) => s.room_id === id),
    [allSchedules, id],
  )

  const [scheduleSearch, setScheduleSearch] = useState('')
  const [, startScheduleSearchTransition] = useTransition()
  const filteredRoomSchedules = useMemo(() => {
    if (!scheduleSearch.trim()) return roomSchedules
    return roomSchedules.filter((s) => tokenMatches(buildScheduleHaystackForRoom(s), scheduleSearch))
  }, [roomSchedules, scheduleSearch])

  const onSubmit = async (values: EditFormValues) => {
    if (!room) return
    try {
      await updateRoom.mutateAsync({
        id: room.id,
        data: {
          name: values.name,
          building: values.building || undefined,
          capacity: values.capacity ? Number(values.capacity) : undefined,
          camera_endpoint: values.camera_endpoint || undefined,
        },
      })
      toast.success(`Room "${values.name}" has been updated.`)
      setEditOpen(false)
    } catch {
      toast.error('Failed to update room.')
    }
  }

  const scheduleColumns: ColumnDef<ScheduleResponse>[] = [
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
      accessorKey: 'faculty',
      header: 'Faculty',
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-sm">
          {row.original.faculty
            ? `${row.original.faculty.first_name} ${row.original.faculty.last_name}`
            : 'Unassigned'}
        </span>
      ),
    },
    {
      accessorKey: 'day_of_week',
      header: 'Day',
      cell: ({ row }) => (
        <span className="text-sm">{DAY_NAMES[row.original.day_of_week]}</span>
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
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ row }) =>
        row.original.is_active ? (
          <Badge variant="default">Active</Badge>
        ) : (
          <Badge variant="destructive">Inactive</Badge>
        ),
    },
  ]

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!room) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/rooms')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Rooms
        </Button>
        <p className="text-muted-foreground">Room not found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/rooms')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Rooms
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-xl">{room.name}</CardTitle>
              <div className="mt-2 flex items-center gap-2">
                {room.is_active ? (
                  <Badge variant="default">Active</Badge>
                ) : (
                  <Badge variant="destructive">Inactive</Badge>
                )}
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-center gap-3">
              <Building2 className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Building</p>
                <p className="text-sm font-medium">{room.building ?? '\u2014'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Users className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Capacity</p>
                <p className="text-sm font-medium">
                  {room.capacity != null ? room.capacity : '\u2014'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Video className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Camera Endpoint</p>
                <p className="text-sm font-medium font-mono">
                  {room.camera_endpoint ?? 'Not configured'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <DoorOpen className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Assigned Schedules</p>
                <p className="text-sm font-medium">{roomSchedules.length}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div>
        <h3 className="text-lg font-semibold mb-4">Schedules in this Room</h3>
        <DataTable
          columns={scheduleColumns}
          data={filteredRoomSchedules}
          searchPlaceholder="Search by subject, faculty, day, time, status..."
          globalFilter={scheduleSearch}
          onGlobalFilterChange={(v) => startScheduleSearchTransition(() => setScheduleSearch(v))}
          globalFilterFn={() => true}
          onRowClick={(row) => navigate(`/schedules/${row.id}`)}
        />
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Room</DialogTitle>
            <DialogDescription>Update the room details below.</DialogDescription>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name *</Label>
              <Input id="name" placeholder="e.g. Room 101" {...form.register('name')} />
              {form.formState.errors.name && (
                <p className="text-sm text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="building">Building</Label>
              <Input id="building" placeholder="e.g. Main Building" {...form.register('building')} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="capacity">Capacity</Label>
              <Input id="capacity" type="number" placeholder="e.g. 40" {...form.register('capacity')} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="camera_endpoint">Camera Endpoint</Label>
              <Input
                id="camera_endpoint"
                placeholder="e.g. http://192.168.1.10:8080"
                {...form.register('camera_endpoint')}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={updateRoom.isPending}>
                {updateRoom.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

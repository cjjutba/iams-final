import { useMemo, useState, useEffect, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, Plus, Pencil, Trash2, ToggleLeft, Eye, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useForm } from 'react-hook-form'
import { usePageTitle } from '@/hooks/use-page-title'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  useRooms,
  useSchedules,
  useCreateRoom,
  useUpdateRoom,
  useDeleteRoom,
} from '@/hooks/use-queries'
import type { Room } from '@/types'
import { tokenMatches, joinHaystack } from '@/lib/search'
import {
  ActiveStatusPill,
  CameraConfiguredPill,
  LiveNowPill,
} from '@/components/shared/status-pills'

function buildRoomHaystack(r: Room): string {
  return joinHaystack([
    r.name,
    r.building,
    r.capacity != null ? String(r.capacity) : null,
    r.capacity != null ? `capacity ${r.capacity}` : null,
    r.camera_endpoint,
    r.camera_endpoint ? 'Camera Configured' : 'No Camera',
    r.is_active ? 'Active' : 'Inactive',
  ])
}

type StatusFilter = 'all' | 'active' | 'inactive'
type CameraFilter = 'all' | 'configured' | 'not_configured'

const roomFormSchema = z.object({
  name: z.string().min(1, 'Room name is required'),
  building: z.string().optional(),
  capacity: z.string().optional(),
  camera_endpoint: z.string().optional(),
})

type RoomFormValues = z.infer<typeof roomFormSchema>

function RoomFormDialog({
  open,
  onOpenChange,
  room,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  room: Room | null
}) {
  const isEdit = room !== null
  const createRoom = useCreateRoom()
  const updateRoom = useUpdateRoom()
  const loading = createRoom.isPending || updateRoom.isPending

  const form = useForm<RoomFormValues>({
    resolver: zodResolver(roomFormSchema),
    defaultValues: {
      name: '',
      building: '',
      capacity: '',
      camera_endpoint: '',
    },
  })

  useEffect(() => {
    if (open) {
      if (room) {
        form.reset({
          name: room.name,
          building: room.building ?? '',
          capacity: room.capacity != null ? String(room.capacity) : '',
          camera_endpoint: room.camera_endpoint ?? '',
        })
      } else {
        form.reset({
          name: '',
          building: '',
          capacity: '',
          camera_endpoint: '',
        })
      }
    }
  }, [open, room, form])

  const onSubmit = async (values: RoomFormValues) => {
    const payload = {
      name: values.name,
      building: values.building || undefined,
      capacity: values.capacity ? Number(values.capacity) : undefined,
      camera_endpoint: values.camera_endpoint || undefined,
    }

    try {
      if (isEdit) {
        await updateRoom.mutateAsync({ id: room.id, data: payload })
        toast.success(`Room "${values.name}" has been updated.`)
      } else {
        await createRoom.mutateAsync(payload)
        toast.success(`Room "${values.name}" has been created.`)
      }
      onOpenChange(false)
    } catch {
      toast.error(isEdit ? 'Failed to update room.' : 'Failed to create room.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Room' : 'Add Room'}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? 'Update the room details below.'
              : 'Fill in the details to create a new room.'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              placeholder="e.g. Room 101"
              {...form.register('name')}
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="building">Building</Label>
            <Input
              id="building"
              placeholder="e.g. Main Building"
              {...form.register('building')}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="capacity">Capacity</Label>
            <Input
              id="capacity"
              type="number"
              placeholder="e.g. 40"
              {...form.register('capacity')}
            />
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
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {isEdit ? 'Saving...' : 'Creating...'}
                </>
              ) : (
                isEdit ? 'Save Changes' : 'Create Room'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ActionsCell({
  room,
  onEdit,
}: {
  room: Room
  onEdit: (room: Room) => void
}) {
  const navigate = useNavigate()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const updateRoom = useUpdateRoom()
  const deleteRoom = useDeleteRoom()

  const handleToggleActive = async () => {
    try {
      await updateRoom.mutateAsync({ id: room.id, data: { is_active: !room.is_active } })
      toast.success(
        `Room "${room.name}" has been ${room.is_active ? 'deactivated' : 'activated'}.`
      )
    } catch {
      toast.error('Failed to update room status.')
    }
  }

  const handleDelete = async () => {
    try {
      await deleteRoom.mutateAsync(room.id)
      toast.success(`Room "${room.name}" has been deleted.`)
    } catch {
      toast.error('Failed to delete room.')
    } finally {
      setDeleteOpen(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => navigate(`/rooms/${room.id}`)}>
            <Eye className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => onEdit(room)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => void handleToggleActive()}>
            <ToggleLeft className="mr-2 h-4 w-4" />
            {room.is_active ? 'Deactivate' : 'Activate'}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setDeleteOpen(true)}
            className="text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Room</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{room.name}&quot;? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteRoom.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDelete()
              }}
              disabled={deleteRoom.isPending}
            >
              {deleteRoom.isPending ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deleting...</>) : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function RoomsPage() {
  usePageTitle('Rooms')
  const navigate = useNavigate()
  const { data: rooms = [], isLoading } = useRooms()
  // Pull schedules so we can derive both the per-room schedule count and
  // the live-now indicator without a dedicated backend endpoint. The
  // schedules query is cached by react-query, so the cost is at most one
  // round-trip on first mount.
  const { data: allSchedules = [] } = useSchedules()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRoom, setEditingRoom] = useState<Room | null>(null)

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [cameraFilter, setCameraFilter] = useState<CameraFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isPending, startTransition] = useTransition()

  // Per-room aggregates: schedule count + whether anything is live now.
  const roomStats = useMemo(() => {
    const map = new Map<string, { count: number; hasLive: boolean }>()
    for (const s of allSchedules) {
      const prev = map.get(s.room_id) ?? { count: 0, hasLive: false }
      prev.count += 1
      if (s.runtime_status === 'live') prev.hasLive = true
      map.set(s.room_id, prev)
    }
    return map
  }, [allSchedules])

  const filtered = useMemo(() => {
    let result = rooms
    if (statusFilter === 'active') result = result.filter((r) => r.is_active)
    else if (statusFilter === 'inactive') result = result.filter((r) => !r.is_active)

    if (cameraFilter === 'configured') result = result.filter((r) => !!r.camera_endpoint)
    else if (cameraFilter === 'not_configured') result = result.filter((r) => !r.camera_endpoint)

    if (searchQuery.trim()) {
      result = result.filter((r) => tokenMatches(buildRoomHaystack(r), searchQuery))
    }

    // Live rooms float to the top, then by name. So when something's
    // running you can scan the list and act on it without sorting first.
    return [...result].sort((a, b) => {
      const aLive = roomStats.get(a.id)?.hasLive ? 0 : 1
      const bLive = roomStats.get(b.id)?.hasLive ? 0 : 1
      if (aLive !== bLive) return aLive - bLive
      return a.name.localeCompare(b.name)
    })
  }, [rooms, statusFilter, cameraFilter, searchQuery, roomStats])

  const hasFilters =
    statusFilter !== 'all' || cameraFilter !== 'all' || searchQuery.trim().length > 0

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setStatusFilter('all')
      setCameraFilter('all')
      setSearchQuery('')
    })
  }

  const showSkeleton = isLoading || isPending

  const handleEdit = (room: Room) => {
    setEditingRoom(room)
    setDialogOpen(true)
  }

  const handleAddNew = () => {
    setEditingRoom(null)
    setDialogOpen(true)
  }

  const columns: ColumnDef<Room>[] = [
    {
      accessorKey: 'name',
      header: 'Name',
      cell: ({ row }) => {
        const stats = roomStats.get(row.original.id)
        return (
          <div className="flex items-center gap-2">
            <span className="font-medium">{row.original.name}</span>
            {stats?.hasLive && <LiveNowPill />}
          </div>
        )
      },
    },
    {
      accessorKey: 'building',
      header: 'Building',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">{row.original.building ?? '—'}</span>
      ),
    },
    {
      accessorKey: 'capacity',
      header: 'Capacity',
      cell: ({ row }) => (
        <span className="text-sm tabular-nums">
          {row.original.capacity != null ? row.original.capacity : '—'}
        </span>
      ),
    },
    {
      id: 'schedules',
      header: 'Schedules',
      enableSorting: false,
      cell: ({ row }) => {
        const stats = roomStats.get(row.original.id)
        return (
          <span className="text-sm tabular-nums text-muted-foreground">
            {stats?.count ?? 0}
          </span>
        )
      },
    },
    {
      accessorKey: 'camera_endpoint',
      header: 'Camera',
      cell: ({ row }) => (
        <CameraConfiguredPill configured={!!row.original.camera_endpoint} />
      ),
    },
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ row }) => <ActiveStatusPill active={row.original.is_active} />,
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: ({ row }) => (
        <ActionsCell
          room={row.original}
          onEdit={handleEdit}
        />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Room Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${filtered.length} of ${rooms.length} rooms`
                : `${rooms.length} room${rooms.length !== 1 ? 's' : ''} total`}
          </p>
        </div>
        <Button onClick={handleAddNew}>
          <Plus className="mr-2 h-4 w-4" />
          Add Room
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={showSkeleton}
        searchPlaceholder="Search by name, building, capacity, status..."
        globalFilter={searchQuery}
        onGlobalFilterChange={(v) => startTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
        toolbar={
          <>
            <Select value={statusFilter} onValueChange={handleFilterChange(setStatusFilter)}>
              <SelectTrigger className="w-[130px] h-9">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>

            <Select value={cameraFilter} onValueChange={handleFilterChange(setCameraFilter)}>
              <SelectTrigger className="w-[150px] h-9">
                <SelectValue placeholder="Camera" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All camera</SelectItem>
                <SelectItem value="configured">Configured</SelectItem>
                <SelectItem value="not_configured">Not configured</SelectItem>
              </SelectContent>
            </Select>

            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2 text-muted-foreground">
                Clear
              </Button>
            )}
          </>
        }
        onRowClick={(row) => navigate(`/rooms/${row.id}`)}
      />

      <RoomFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        room={editingRoom}
      />
    </div>
  )
}

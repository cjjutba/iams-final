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
import { Badge } from '@/components/ui/badge'
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
import { useRooms, useCreateRoom, useUpdateRoom, useDeleteRoom } from '@/hooks/use-queries'
import type { Room } from '@/types'

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
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRoom, setEditingRoom] = useState<Room | null>(null)

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [cameraFilter, setCameraFilter] = useState<CameraFilter>('all')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result = rooms
    if (statusFilter === 'active') result = result.filter((r) => r.is_active)
    else if (statusFilter === 'inactive') result = result.filter((r) => !r.is_active)

    if (cameraFilter === 'configured') result = result.filter((r) => !!r.camera_endpoint)
    else if (cameraFilter === 'not_configured') result = result.filter((r) => !r.camera_endpoint)

    return result
  }, [rooms, statusFilter, cameraFilter])

  const hasFilters = statusFilter !== 'all' || cameraFilter !== 'all'

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setStatusFilter('all')
      setCameraFilter('all')
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
      cell: ({ row }) => (
        <span className="font-medium">{row.original.name}</span>
      ),
    },
    {
      accessorKey: 'building',
      header: 'Building',
      cell: ({ row }) => (
        <span className="text-sm">{row.original.building ?? '\u2014'}</span>
      ),
    },
    {
      accessorKey: 'capacity',
      header: 'Capacity',
      cell: ({ row }) => (
        <span className="text-sm">
          {row.original.capacity != null ? row.original.capacity : '\u2014'}
        </span>
      ),
    },
    {
      accessorKey: 'camera_endpoint',
      header: 'Camera Endpoint',
      cell: ({ row }) =>
        row.original.camera_endpoint ? (
          <span className="text-sm font-mono">{row.original.camera_endpoint}</span>
        ) : (
          <span className="text-sm text-muted-foreground">Not configured</span>
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
        searchColumn="name"
        searchPlaceholder="Search rooms..."
        toolbar={
          <>
            <Select value={statusFilter} onValueChange={handleFilterChange(setStatusFilter)}>
              <SelectTrigger className="w-[130px] h-9">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>

            <Select value={cameraFilter} onValueChange={handleFilterChange(setCameraFilter)}>
              <SelectTrigger className="w-[150px] h-9">
                <SelectValue placeholder="Camera" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Camera</SelectItem>
                <SelectItem value="configured">Configured</SelectItem>
                <SelectItem value="not_configured">Not Configured</SelectItem>
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

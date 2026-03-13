import { useCallback, useEffect, useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, Plus, Pencil, Trash2, ToggleLeft } from 'lucide-react'
import { toast } from 'sonner'
import { useForm } from 'react-hook-form'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { roomsService } from '@/services/rooms.service'
import type { Room } from '@/types'

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
  onSuccess,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  room: Room | null
  onSuccess: () => void
}) {
  const [loading, setLoading] = useState(false)
  const isEdit = room !== null

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
    setLoading(true)
    try {
      const payload = {
        name: values.name,
        building: values.building || undefined,
        capacity: values.capacity ? Number(values.capacity) : undefined,
        camera_endpoint: values.camera_endpoint || undefined,
      }

      if (isEdit) {
        await roomsService.update(room.id, payload)
        toast.success(`Room "${values.name}" has been updated.`)
      } else {
        await roomsService.create(payload)
        toast.success(`Room "${values.name}" has been created.`)
      }
      onOpenChange(false)
      onSuccess()
    } catch {
      toast.error(isEdit ? 'Failed to update room.' : 'Failed to create room.')
    } finally {
      setLoading(false)
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
              {loading
                ? isEdit
                  ? 'Saving...'
                  : 'Creating...'
                : isEdit
                  ? 'Save Changes'
                  : 'Create Room'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ActionsCell({
  room,
  onRefresh,
  onEdit,
}: {
  room: Room
  onRefresh: () => void
  onEdit: (room: Room) => void
}) {
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleToggleActive = async () => {
    try {
      await roomsService.update(room.id, { is_active: !room.is_active })
      toast.success(
        `Room "${room.name}" has been ${room.is_active ? 'deactivated' : 'activated'}.`
      )
      onRefresh()
    } catch {
      toast.error('Failed to update room status.')
    }
  }

  const handleDelete = async () => {
    setLoading(true)
    try {
      await roomsService.delete(room.id)
      toast.success(`Room "${room.name}" has been deleted.`)
      onRefresh()
    } catch {
      toast.error('Failed to delete room.')
    } finally {
      setLoading(false)
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
          <DropdownMenuItem onClick={() => onEdit(room)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleToggleActive}>
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
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={loading}>
              {loading ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function RoomsPage() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRoom, setEditingRoom] = useState<Room | null>(null)

  const fetchRooms = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await roomsService.list()
      setRooms(data)
    } catch {
      setError('Unable to load rooms')
      setRooms([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchRooms()
  }, [fetchRooms])

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
          <Badge variant="default" className="bg-green-600 hover:bg-green-700">
            Active
          </Badge>
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
          onRefresh={fetchRooms}
          onEdit={handleEdit}
        />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Room Management</h1>
          <p className="text-muted-foreground mt-1">
            {isLoading
              ? 'Loading rooms...'
              : error
                ? error
                : `${rooms.length} room${rooms.length !== 1 ? 's' : ''} total`}
          </p>
        </div>
        <Button onClick={handleAddNew}>
          <Plus className="mr-2 h-4 w-4" />
          Add Room
        </Button>
      </div>

      {error && !isLoading ? (
        <div className="rounded-md border border-dashed p-8 text-center">
          <p className="text-muted-foreground">{error}</p>
          <Button variant="outline" className="mt-4" onClick={fetchRooms}>
            Retry
          </Button>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={rooms}
          isLoading={isLoading}
          searchColumn="name"
          searchPlaceholder="Search rooms..."
        />
      )}

      <RoomFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        room={editingRoom}
        onSuccess={fetchRooms}
      />
    </div>
  )
}

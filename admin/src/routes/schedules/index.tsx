import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  MoreHorizontal,
  Eye,
  Pencil,
  Trash2,
  Plus,
} from 'lucide-react'
import { toast } from 'sonner'

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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { schedulesService } from '@/services/schedules.service'
import { usersService } from '@/services/users.service'
import { roomsService } from '@/services/rooms.service'
import type { ScheduleResponse, UserResponse, Room } from '@/types'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

interface ScheduleFormValues {
  subject_code: string
  subject_name: string
  faculty_id: string
  room_id: string
  day_of_week: number
  start_time: string
  end_time: string
  semester: string
  academic_year: string
  target_course?: string
  target_year_level?: number
}

const scheduleFormSchema = z.object({
  subject_code: z.string().min(1, 'Subject code is required').max(20, 'Max 20 characters'),
  subject_name: z.string().min(1, 'Subject name is required'),
  faculty_id: z.string().min(1, 'Faculty is required'),
  room_id: z.string().min(1, 'Room is required'),
  day_of_week: z.number().min(0).max(6),
  start_time: z.string().min(1, 'Start time is required'),
  end_time: z.string().min(1, 'End time is required'),
  semester: z.string().min(1, 'Semester is required'),
  academic_year: z.string().min(1, 'Academic year is required'),
  target_course: z.string().optional(),
  target_year_level: z.number().optional(),
})

function formatTime(time: string): string {
  if (!time) return ''
  const [hours, minutes] = time.split(':')
  const h = parseInt(hours, 10)
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${String(h12)}:${minutes} ${ampm}`
}

function ActionsCell({
  schedule,
  onEdit,
  onDelete,
}: {
  schedule: ScheduleResponse
  onEdit: (schedule: ScheduleResponse) => void
  onDelete: (schedule: ScheduleResponse) => void
}) {
  const navigate = useNavigate()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => navigate(`/schedules/${schedule.id}`)}>
          <Eye className="mr-2 h-4 w-4" />
          View Details
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onEdit(schedule)}>
          <Pencil className="mr-2 h-4 w-4" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => onDelete(schedule)} className="text-destructive">
          <Trash2 className="mr-2 h-4 w-4" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [faculty, setFaculty] = useState<UserResponse[]>([])
  const [rooms, setRooms] = useState<Room[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ScheduleResponse | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ScheduleResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<ScheduleFormValues>({
    resolver: zodResolver(scheduleFormSchema),
    defaultValues: {
      subject_code: '',
      subject_name: '',
      faculty_id: '',
      room_id: '',
      day_of_week: 1,
      start_time: '',
      end_time: '',
      semester: '',
      academic_year: '',
      target_course: '',
      target_year_level: undefined,
    },
  })

  const fetchSchedules = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await schedulesService.list()
      setSchedules(data)
    } catch {
      toast.error('Failed to load schedules.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchFaculty = useCallback(async () => {
    try {
      const data = await usersService.list({ role: 'faculty' })
      setFaculty(data)
    } catch {
      // Faculty endpoint may not support role filter — fail silently
    }
  }, [])

  const fetchRooms = useCallback(async () => {
    try {
      const data = await roomsService.list()
      setRooms(data)
    } catch {
      // Rooms endpoint may not exist yet — fail silently
    }
  }, [])

  useEffect(() => {
    void fetchSchedules()
    void fetchFaculty()
    void fetchRooms()
  }, [fetchSchedules, fetchFaculty, fetchRooms])

  const openCreateDialog = () => {
    setEditingSchedule(null)
    form.reset({
      subject_code: '',
      subject_name: '',
      faculty_id: '',
      room_id: '',
      day_of_week: 1,
      start_time: '',
      end_time: '',
      semester: '',
      academic_year: '',
      target_course: '',
      target_year_level: undefined,
    })
    setDialogOpen(true)
  }

  const openEditDialog = (schedule: ScheduleResponse) => {
    setEditingSchedule(schedule)
    form.reset({
      subject_code: schedule.subject_code,
      subject_name: schedule.subject_name,
      faculty_id: schedule.faculty_id,
      room_id: schedule.room_id,
      day_of_week: schedule.day_of_week,
      start_time: schedule.start_time.slice(0, 5),
      end_time: schedule.end_time.slice(0, 5),
      semester: schedule.semester,
      academic_year: schedule.academic_year,
      target_course: schedule.target_course ?? '',
      target_year_level: schedule.target_year_level ?? undefined,
    })
    setDialogOpen(true)
  }

  const onSubmit = async (values: ScheduleFormValues) => {
    setSubmitting(true)
    try {
      const payload = {
        ...values,
        target_course: values.target_course || undefined,
        target_year_level: values.target_year_level || undefined,
      }

      if (editingSchedule) {
        await schedulesService.update(editingSchedule.id, payload)
        toast.success('Schedule updated successfully.')
      } else {
        await schedulesService.create(payload)
        toast.success('Schedule created successfully.')
      }
      setDialogOpen(false)
      void fetchSchedules()
    } catch {
      toast.error(editingSchedule ? 'Failed to update schedule.' : 'Failed to create schedule.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setSubmitting(true)
    try {
      await schedulesService.delete(deleteTarget.id)
      toast.success('Schedule deleted successfully.')
      setDeleteTarget(null)
      void fetchSchedules()
    } catch {
      toast.error('Failed to delete schedule.')
    } finally {
      setSubmitting(false)
    }
  }

  const columns: ColumnDef<ScheduleResponse>[] = [
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
      accessorKey: 'room',
      header: 'Room',
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-sm">
          {row.original.room?.name ?? 'Unassigned'}
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
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: ({ row }) => (
        <ActionsCell
          schedule={row.original}
          onEdit={openEditDialog}
          onDelete={setDeleteTarget}
        />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Schedule Management</h1>
          <p className="text-muted-foreground mt-1">
            {isLoading
              ? 'Loading schedules...'
              : `${schedules.length} schedule${schedules.length !== 1 ? 's' : ''} total`}
          </p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Create Schedule
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={schedules}
        isLoading={isLoading}
        searchColumn="subject_name"
        searchPlaceholder="Search by subject..."
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingSchedule ? 'Edit Schedule' : 'Create Schedule'}
            </DialogTitle>
            <DialogDescription>
              {editingSchedule
                ? 'Update the schedule details below.'
                : 'Fill in the details to create a new schedule.'}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="subject_code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Subject Code</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. CS 101" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="subject_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Subject Name</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. Introduction to Computing" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="faculty_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Faculty</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select faculty" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {faculty.map((f) => (
                            <SelectItem key={f.id} value={f.id}>
                              {f.first_name} {f.last_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="room_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Room</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select room" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {rooms.map((r) => (
                            <SelectItem key={r.id} value={r.id}>
                              {r.name}{r.building ? ` (${r.building})` : ''}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <FormField
                  control={form.control}
                  name="day_of_week"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Day</FormLabel>
                      <Select
                        onValueChange={(val) => field.onChange(parseInt(val, 10))}
                        value={String(field.value)}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select day" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {DAY_NAMES.map((name, i) => (
                            <SelectItem key={name} value={String(i)}>
                              {name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="start_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Start Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="end_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>End Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="semester"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Semester</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select semester" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="1st">1st Semester</SelectItem>
                          <SelectItem value="2nd">2nd Semester</SelectItem>
                          <SelectItem value="summer">Summer</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="academic_year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Academic Year</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. 2025-2026" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="target_course"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Target Course (optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. BSCS" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="target_year_level"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Target Year Level (optional)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={1}
                          max={6}
                          placeholder="e.g. 1"
                          {...field}
                          value={field.value ?? ''}
                          onChange={(e) =>
                            field.onChange(e.target.value ? parseInt(e.target.value, 10) : undefined)
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting
                    ? editingSchedule
                      ? 'Updating...'
                      : 'Creating...'
                    : editingSchedule
                      ? 'Update Schedule'
                      : 'Create Schedule'}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Schedule</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {deleteTarget?.subject_code} -{' '}
              {deleteTarget?.subject_name}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={submitting}>
              {submitting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

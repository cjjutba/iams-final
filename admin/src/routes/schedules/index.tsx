import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { type ColumnDef } from '@tanstack/react-table'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  MoreHorizontal,
  Eye,
  Loader2,
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
import { useSchedules, useCreateSchedule, useUpdateSchedule, useDeleteSchedule, useUsers, useRooms } from '@/hooks/use-queries'
import type { ScheduleResponse } from '@/types'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

type StatusFilter = 'all' | 'active' | 'inactive'
type DayFilter = 'all' | '0' | '1' | '2' | '3' | '4' | '5' | '6'

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
  usePageTitle('Schedules')
  const navigate = useNavigate()
  const { data: schedules = [], isLoading } = useSchedules()
  const { data: faculty = [] } = useUsers({ role: 'faculty' })
  const { data: rooms = [] } = useRooms()
  const createSchedule = useCreateSchedule()
  const updateSchedule = useUpdateSchedule()
  const deleteScheduleMutation = useDeleteSchedule()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ScheduleResponse | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ScheduleResponse | null>(null)

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [dayFilter, setDayFilter] = useState<DayFilter>('all')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result = schedules
    if (statusFilter === 'active') result = result.filter((s) => s.is_active)
    else if (statusFilter === 'inactive') result = result.filter((s) => !s.is_active)

    if (dayFilter !== 'all') result = result.filter((s) => s.day_of_week === parseInt(dayFilter, 10))

    return result
  }, [schedules, statusFilter, dayFilter])

  const hasFilters = statusFilter !== 'all' || dayFilter !== 'all'

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setStatusFilter('all')
      setDayFilter('all')
    })
  }

  const showSkeleton = isLoading || isPending

  const submitting = createSchedule.isPending || updateSchedule.isPending || deleteScheduleMutation.isPending

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
    try {
      const payload = {
        ...values,
        target_course: values.target_course || undefined,
        target_year_level: values.target_year_level || undefined,
      }

      if (editingSchedule) {
        await updateSchedule.mutateAsync({ id: editingSchedule.id, data: payload })
        toast.success('Schedule updated successfully.')
      } else {
        await createSchedule.mutateAsync(payload)
        toast.success('Schedule created successfully.')
      }
      setDialogOpen(false)
    } catch {
      toast.error(editingSchedule ? 'Failed to update schedule.' : 'Failed to create schedule.')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteScheduleMutation.mutateAsync(deleteTarget.id)
      toast.success('Schedule deleted successfully.')
      setDeleteTarget(null)
    } catch {
      toast.error('Failed to delete schedule.')
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
          <h1 className="text-2xl font-semibold tracking-tight">Schedule Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${filtered.length} of ${schedules.length} schedules`
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
        data={filtered}
        isLoading={showSkeleton}
        searchColumn="subject_name"
        searchPlaceholder="Search by subject..."
        toolbar={
          <>
            <Select value={dayFilter} onValueChange={handleFilterChange(setDayFilter)}>
              <SelectTrigger className="w-[140px] h-9">
                <SelectValue placeholder="Day" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Days</SelectItem>
                {DAY_NAMES.map((name, i) => (
                  <SelectItem key={name} value={String(i)}>{name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

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

            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2 text-muted-foreground">
                Clear
              </Button>
            )}
          </>
        }
        onRowClick={(row) => navigate(`/schedules/${row.id}`)}
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
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {editingSchedule ? 'Updating...' : 'Creating...'}
                    </>
                  ) : (
                    editingSchedule ? 'Update Schedule' : 'Create Schedule'
                  )}
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
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDelete()
              }}
              disabled={submitting}
            >
              {submitting ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deleting...</>) : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

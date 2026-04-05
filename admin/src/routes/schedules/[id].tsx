import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import {
  ArrowLeft,
  BookOpen,
  Calendar,
  Clock,
  DoorOpen,
  GraduationCap,
  Loader2,
  Pencil,
  User,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useSchedule,
  useScheduleStudents,
  useScheduleAttendanceSummary,
  useUpdateSchedule,
  useUsers,
  useRooms,
} from '@/hooks/use-queries'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

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

type ScheduleFormValues = z.infer<typeof scheduleFormSchema>

function formatTime(time: string): string {
  if (!time) return ''
  const [hours, minutes] = time.split(':')
  const h = parseInt(hours, 10)
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${String(h12)}:${minutes} ${ampm}`
}

interface EnrolledStudent {
  id: string
  student_id: string | null
  first_name: string
  last_name: string
  is_active: boolean
}

interface AttendanceSummaryData {
  total_sessions?: number
  total_enrolled?: number
  average_attendance_rate?: number
  present_count?: number
  late_count?: number
  absent_count?: number
}

export default function ScheduleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: schedule, isLoading } = useSchedule(id!)
  const { data: faculty = [] } = useUsers({ role: 'faculty' })
  const { data: rooms = [] } = useRooms()
  const updateSchedule = useUpdateSchedule()

  const [editOpen, setEditOpen] = useState(false)

  const scheduleName = schedule ? `${schedule.subject_code} - ${schedule.subject_name}` : null
  usePageTitle(scheduleName ?? 'Schedule Details')

  useEffect(() => {
    if (scheduleName) setLabel(scheduleName)
    return () => setLabel(null)
  }, [scheduleName, setLabel])

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

  useEffect(() => {
    if (editOpen && schedule) {
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
    }
  }, [editOpen, schedule, form])

  const onSubmit = async (values: ScheduleFormValues) => {
    if (!schedule) return
    try {
      await updateSchedule.mutateAsync({
        id: schedule.id,
        data: {
          ...values,
          target_course: values.target_course || undefined,
          target_year_level: values.target_year_level || undefined,
        },
      })
      toast.success('Schedule updated successfully.')
      setEditOpen(false)
    } catch {
      toast.error('Failed to update schedule.')
    }
  }

  const { data: studentsData, isLoading: studentsLoading, isError: studentsError } = useScheduleStudents(id!)
  const { data: summaryRaw, isLoading: summaryLoading } = useScheduleAttendanceSummary(id!)

  const students = Array.isArray(studentsData)
    ? studentsData
    : (studentsData as { students?: EnrolledStudent[] })?.students ?? []
  const summary = summaryRaw as AttendanceSummaryData | null | undefined

  const studentColumns: ColumnDef<EnrolledStudent>[] = [
    {
      accessorKey: 'first_name',
      header: 'Student Name',
      cell: ({ row }) => (
        <span className="text-sm font-medium">
          {row.original.first_name} {row.original.last_name}
        </span>
      ),
    },
    {
      accessorKey: 'student_id',
      header: 'Student ID',
      cell: ({ row }) => (
        <span className="text-sm">{row.original.student_id ?? '\u2014'}</span>
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

  if (!schedule) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/schedules')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Schedules
        </Button>
        <p className="text-muted-foreground">Schedule not found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/schedules')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Schedules
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-xl">
                {schedule.subject_code} - {schedule.subject_name}
              </CardTitle>
              <div className="mt-2 flex items-center gap-2">
                {schedule.is_active ? (
                  <Badge variant="default">Active</Badge>
                ) : (
                  <Badge variant="destructive">Inactive</Badge>
                )}
                {schedule.target_course && (
                  <Badge variant="outline">{schedule.target_course}</Badge>
                )}
                {schedule.target_year_level && (
                  <Badge variant="outline">Year {schedule.target_year_level}</Badge>
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex items-center gap-3">
              <User className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Faculty</p>
                <p className="text-sm font-medium">
                  {schedule.faculty
                    ? `${schedule.faculty.first_name} ${schedule.faculty.last_name}`
                    : 'Unassigned'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <DoorOpen className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Room</p>
                <p className="text-sm font-medium">
                  {schedule.room?.name ?? 'Unassigned'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Day</p>
                <p className="text-sm font-medium">{DAY_NAMES[schedule.day_of_week]}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Time</p>
                <p className="text-sm font-medium">
                  {formatTime(schedule.start_time)} - {formatTime(schedule.end_time)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Semester</p>
                <p className="text-sm font-medium">
                  {schedule.semester} &middot; {schedule.academic_year}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {summary && !summaryLoading && (
        <Card>
          <CardHeader>
            <CardTitle>Attendance Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {summary.total_sessions != null && (
                <div className="rounded-lg border p-4">
                  <p className="text-sm text-muted-foreground">Total Sessions</p>
                  <p className="text-2xl font-bold">{summary.total_sessions}</p>
                </div>
              )}
              {summary.total_enrolled != null && (
                <div className="rounded-lg border p-4">
                  <p className="text-sm text-muted-foreground">Enrolled Students</p>
                  <p className="text-2xl font-bold">{summary.total_enrolled}</p>
                </div>
              )}
              {summary.average_attendance_rate != null && (
                <div className="rounded-lg border p-4">
                  <p className="text-sm text-muted-foreground">Avg. Attendance Rate</p>
                  <p className="text-2xl font-bold">{summary.average_attendance_rate}%</p>
                </div>
              )}
              {summary.present_count != null && (
                <div className="rounded-lg border p-4">
                  <p className="text-sm text-muted-foreground">Present / Late / Absent</p>
                  <p className="text-2xl font-bold">
                    {summary.present_count} / {summary.late_count ?? 0} / {summary.absent_count ?? 0}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5" />
            Enrolled Students
          </CardTitle>
        </CardHeader>
        <CardContent>
          {studentsError ? (
            <p className="text-sm text-muted-foreground">
              Unable to load enrolled students. The endpoint may not be available yet.
            </p>
          ) : (
            <DataTable
              columns={studentColumns}
              data={students as EnrolledStudent[]}
              isLoading={studentsLoading}
              searchColumn="first_name"
              searchPlaceholder="Search students..."
              onRowClick={(row) => navigate(`/users/${row.id}`, { state: { role: 'student' } })}
            />
          )}
        </CardContent>
      </Card>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Schedule</DialogTitle>
            <DialogDescription>Update the schedule details below.</DialogDescription>
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
                <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={updateSchedule.isPending}>
                  {updateSchedule.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Updating...
                    </>
                  ) : (
                    'Update Schedule'
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

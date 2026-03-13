import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import {
  ArrowLeft,
  BookOpen,
  Calendar,
  Clock,
  DoorOpen,
  GraduationCap,
  User,
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
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { schedulesService } from '@/services/schedules.service'
import { attendanceService } from '@/services/attendance.service'
import type { ScheduleResponse } from '@/types'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

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
  const [schedule, setSchedule] = useState<ScheduleResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [students, setStudents] = useState<EnrolledStudent[]>([])
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [studentsError, setStudentsError] = useState(false)
  const [summary, setSummary] = useState<AttendanceSummaryData | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const fetchSchedule = useCallback(async () => {
    if (!id) return
    setIsLoading(true)
    try {
      const data = await schedulesService.getById(id)
      setSchedule(data)
    } catch {
      toast.error('Failed to load schedule.')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  const fetchStudents = useCallback(async () => {
    if (!id) return
    setStudentsLoading(true)
    setStudentsError(false)
    try {
      const data = await schedulesService.getEnrolledStudents(id)
      const list = Array.isArray(data) ? data : (data as { students?: EnrolledStudent[] }).students ?? []
      setStudents(list as EnrolledStudent[])
    } catch {
      setStudentsError(true)
    } finally {
      setStudentsLoading(false)
    }
  }, [id])

  const fetchSummary = useCallback(async () => {
    if (!id) return
    setSummaryLoading(true)
    try {
      const data = await attendanceService.getScheduleSummary(id)
      setSummary(data as AttendanceSummaryData)
    } catch {
      // Summary endpoint may not be available — fail silently
    } finally {
      setSummaryLoading(false)
    }
  }, [id])

  useEffect(() => {
    void fetchSchedule()
    void fetchStudents()
    void fetchSummary()
  }, [fetchSchedule, fetchStudents, fetchSummary])

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
              data={students}
              isLoading={studentsLoading}
              searchColumn="first_name"
              searchPlaceholder="Search students..."
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

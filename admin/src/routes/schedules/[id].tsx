import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Loader2,
  MoreVertical,
  Pencil,
  Plus,
  RotateCcw,
  ScanLine,
  Trash2,
  UserCircle2,
  Video,
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useSchedule,
  useScheduleStudents,
  useScheduleSessions,
  useScheduleAttendanceSummary,
  useUpdateSchedule,
  useUsers,
  useRooms,
  useEnrollStudent,
  useUnenrollStudent,
  useDeregisterFace,
} from '@/hooks/use-queries'
import { EarlyLeaveTimeoutControl } from '@/components/schedules/early-leave-timeout-control'
import type { ScheduleRuntimeStatus } from '@/types'
import { usersService } from '@/services/users.service'
import { tokenMatches, joinHaystack } from '@/lib/search'

// Indexed Monday-first to match the backend's `day_of_week` convention
// (0=Mon..6=Sun — see backend/scripts/seed_data.py).
const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

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

function formatSessionDate(iso: string): string {
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

interface EnrolledStudent {
  id: string
  student_id: string | null
  first_name: string
  last_name: string
  is_active: boolean
  has_face_registered?: boolean
}

interface AttendanceSummaryData {
  total_sessions?: number
  total_records?: number
  total_enrolled?: number
  average_attendance_rate?: number
  attendance_rate?: number
  present_count?: number
  late_count?: number
  absent_count?: number
  early_leave_count?: number
}

type FaceFilter = 'all' | 'registered' | 'pending'

// ---------------------------------------------------------------------------
// Small presentational helpers — kept local so the rebuild stays
// self-contained. Promote into components/schedules/ if any grow further.
// ---------------------------------------------------------------------------

const RUNTIME_STATUS_STYLES: Record<ScheduleRuntimeStatus, { label: string; dot: string; pulse: boolean }> = {
  live: { label: 'LIVE', dot: 'bg-emerald-500', pulse: true },
  upcoming: { label: 'UPCOMING', dot: 'bg-amber-500', pulse: false },
  ended: { label: 'ENDED TODAY', dot: 'bg-muted-foreground/60', pulse: false },
  scheduled: { label: 'SCHEDULED', dot: 'bg-muted-foreground/60', pulse: false },
  disabled: { label: 'DISABLED', dot: 'bg-muted-foreground/40', pulse: false },
}

function RuntimeStatusPill({ status }: { status: ScheduleRuntimeStatus }) {
  const cfg = RUNTIME_STATUS_STYLES[status] ?? RUNTIME_STATUS_STYLES.scheduled
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-foreground">
      <span className="relative flex h-1.5 w-1.5">
        {cfg.pulse && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${cfg.dot} opacity-75`} />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      </span>
      {cfg.label}
    </span>
  )
}

function MetaItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-sm font-medium text-foreground">{value}</div>
    </div>
  )
}

function OverviewStat({
  label,
  value,
  hint,
}: {
  label: string
  value: React.ReactNode
  hint?: string
}) {
  return (
    <div className="rounded-md border bg-card px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums leading-none text-foreground">
        {value}
      </div>
      {hint && <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

interface SegmentSpec {
  key: string
  label: string
  count: number
  segment: string
  swatch: string
}

function SegmentedBreakdown({ segments, total }: { segments: SegmentSpec[]; total: number }) {
  const denom = Math.max(total, 1)
  return (
    <div className="space-y-2">
      <div
        className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label="Status breakdown"
      >
        {segments.map((s) => {
          if (s.count === 0) return null
          return (
            <div
              key={s.key}
              className={s.segment}
              style={{ width: `${(s.count / denom) * 100}%` }}
              title={`${s.label}: ${s.count}`}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${s.swatch}`} />
            <span className="font-semibold tabular-nums text-foreground">{s.count}</span>
            <span className="text-muted-foreground">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function FaceStatusPill({ registered }: { registered: boolean }) {
  if (registered) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
        <ScanLine className="h-3 w-3" />
        Registered
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-700 dark:text-amber-400">
      Pending
    </span>
  )
}

export default function ScheduleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: schedule, isLoading } = useSchedule(id!)
  const { data: faculty = [] } = useUsers({ role: 'faculty' })
  const { data: rooms = [] } = useRooms()
  const updateSchedule = useUpdateSchedule()
  const deregisterFace = useDeregisterFace()

  const [editOpen, setEditOpen] = useState(false)
  const [enrollOpen, setEnrollOpen] = useState(false)
  const [enrollSearch, setEnrollSearch] = useState('')
  const [allStudents, setAllStudents] = useState<Array<{ user_id: string | null; student_id: string; first_name: string; last_name: string; is_registered?: boolean }>>([])
  const enrollStudent = useEnrollStudent()
  const unenrollStudent = useUnenrollStudent()
  const [unenrollConfirm, setUnenrollConfirm] = useState<{ studentUserId: string; name: string } | null>(null)
  const [resetFaceConfirm, setResetFaceConfirm] = useState<{ studentUserId: string; name: string } | null>(null)
  const [studentSearch, setStudentSearch] = useState('')
  const [faceFilter, setFaceFilter] = useState<FaceFilter>('all')

  // Use just the human-readable name for the page title; the breadcrumb leaf
  // renders the same string so we don't compound code+name+time anywhere.
  const breadcrumbLabel = schedule
    ? `${schedule.subject_code} · ${schedule.subject_name}`
    : null
  usePageTitle(breadcrumbLabel ?? 'Schedule Details')

  useEffect(() => {
    if (breadcrumbLabel) setLabel(breadcrumbLabel)
    return () => setLabel(null)
  }, [breadcrumbLabel, setLabel])

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
  const { data: sessionsData, isLoading: sessionsLoading } = useScheduleSessions(id!, { limit: 30 })

  const students = useMemo<EnrolledStudent[]>(() => {
    if (Array.isArray(studentsData)) return studentsData as EnrolledStudent[]
    const wrapped = studentsData as
      | { enrolled_students?: EnrolledStudent[]; students?: EnrolledStudent[] }
      | null
      | undefined
    return wrapped?.enrolled_students ?? wrapped?.students ?? []
  }, [studentsData])
  const summary = summaryRaw as AttendanceSummaryData | null | undefined
  const sessions = useMemo(() => sessionsData ?? [], [sessionsData])

  const filteredStudents = useMemo(() => {
    let pool: EnrolledStudent[] = students
    if (faceFilter === 'registered') {
      pool = pool.filter((s) => s.has_face_registered === true)
    } else if (faceFilter === 'pending') {
      pool = pool.filter((s) => s.has_face_registered !== true)
    }
    if (!studentSearch.trim()) return pool
    return pool.filter((s) =>
      tokenMatches(
        joinHaystack([
          s.first_name,
          s.last_name,
          `${s.first_name} ${s.last_name}`,
          s.student_id,
          s.is_active ? 'Active' : 'Inactive',
          s.has_face_registered ? 'Registered' : 'Pending',
        ]),
        studentSearch,
      ),
    )
  }, [students, studentSearch, faceFilter])

  // Load all students when enroll dialog opens
  useEffect(() => {
    if (enrollOpen && allStudents.length === 0) {
      usersService.listStudentRecords().then(setAllStudents).catch(() => {})
    }
  }, [enrollOpen, allStudents.length])

  const enrolledUserIds = new Set(students.map((s) => s.id))

  // Debounce the dialog's search so a fast typer doesn't re-filter the
  // whole student record list on every keystroke. Matches the toolbar
  // behaviour for the rest of the admin portal.
  const debouncedEnrollSearch = useDebouncedValue(enrollSearch, 300)

  // Renamed from `filteredStudents` to disambiguate from the
  // schedule-students search above. This list is the *enrollable*
  // candidate set inside the Enroll Dialog (everyone not already enrolled
  // who matches the dialog's separate ``enrollSearch`` input). Renamed
  // 2026-04-25 alongside the live-feed-overlay deploy because both lists
  // collided on a single `filteredStudents` const and broke the build.
  const filteredEnrollableStudents = allStudents.filter(
    (s) =>
      (!s.user_id || !enrolledUserIds.has(s.user_id)) &&
      (debouncedEnrollSearch === '' ||
        `${s.first_name} ${s.last_name} ${s.student_id}`.toLowerCase().includes(debouncedEnrollSearch.toLowerCase()))
  )

  const handleEnroll = async (studentUserId: string, studentName: string) => {
    if (!id) return
    try {
      await enrollStudent.mutateAsync({ scheduleId: id, studentUserId })
      // Refresh the student list for the dialog to remove enrolled student
      usersService.listStudentRecords().then(setAllStudents).catch(() => {})
      toast.success(`${studentName} enrolled successfully`)
    } catch {
      toast.error('Failed to enroll student')
    }
  }

  const confirmUnenroll = () => {
    if (!id || !unenrollConfirm) return
    unenrollStudent.mutate(
      { scheduleId: id, studentUserId: unenrollConfirm.studentUserId },
      {
        onSuccess: () => { toast.success('Student unenrolled successfully'); setUnenrollConfirm(null) },
        onError: () => toast.error('Failed to unenroll student'),
      }
    )
  }

  const confirmResetFace = () => {
    if (!resetFaceConfirm) return
    deregisterFace.mutate(resetFaceConfirm.studentUserId, {
      onSuccess: () => {
        toast.success(`Face registration cleared for ${resetFaceConfirm.name}`)
        setResetFaceConfirm(null)
      },
      onError: () => toast.error('Failed to clear face registration'),
    })
  }

  // ── Derived stats for the overview block ──
  const enrolledCount = students.length || summary?.total_enrolled || 0

  const sessionsHeld = sessions.length || summary?.total_sessions || 0

  const avgAttendanceRate = useMemo<number | null>(() => {
    if (sessions.length > 0) {
      const rates = sessions
        .map((s) => s.attendance_rate)
        .filter((r): r is number => r !== null)
      if (rates.length === 0) return null
      const mean = rates.reduce((a, b) => a + b, 0) / rates.length
      return Math.round(mean * 10) / 10
    }
    if (summary?.average_attendance_rate != null) return summary.average_attendance_rate
    if (summary?.attendance_rate != null) return summary.attendance_rate
    return null
  }, [sessions, summary])

  const earlyLeaveTotal = useMemo(() => {
    if (sessions.length > 0) {
      return sessions.reduce((acc, s) => acc + (s.early_leave ?? 0), 0)
    }
    return summary?.early_leave_count ?? 0
  }, [sessions, summary])

  const latestSession = sessions[0]

  const overviewLoading = summaryLoading || sessionsLoading

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
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.student_id ?? '—'}
        </span>
      ),
    },
    {
      accessorKey: 'has_face_registered',
      header: 'Face Registration',
      cell: ({ row }) => <FaceStatusPill registered={row.original.has_face_registered === true} />,
    },
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ row }) =>
        row.original.is_active === false ? (
          <Badge variant="outline" className="border-muted-foreground/30 text-muted-foreground">
            Inactive
          </Badge>
        ) : (
          <Badge
            variant="outline"
            className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
          >
            Active
          </Badge>
        ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const student = row.original
        const fullName = `${student.first_name} ${student.last_name}`
        return (
          <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  aria-label={`Actions for ${fullName}`}
                >
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem
                  onClick={() => navigate(`/users/${student.id}`, { state: { role: 'student' } })}
                >
                  <UserCircle2 className="mr-2 h-4 w-4" />
                  View profile
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={!student.has_face_registered}
                  onClick={() => setResetFaceConfirm({ studentUserId: student.id, name: fullName })}
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Reset face registration
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setUnenrollConfirm({ studentUserId: student.id, name: fullName })}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Unenroll
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )
      },
    },
  ]

  if (isLoading) {
    // Mirror the loaded layout (Back → Header → Attendance Settings →
    // Attendance Overview → Sessions → Enrolled Students) so the cut-over
    // to real data doesn't shift the page. Each skeleton block is sized
    // to match its eventual counterpart's width, height, and rhythm.
    return (
      <div className="space-y-6">
        {/* Back to Schedules */}
        <Skeleton className="h-9 w-36 rounded-md" />

        {/* ── Header Card ──────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 space-y-2">
                <Skeleton className="h-7 w-80" />
                <div className="flex flex-wrap items-center gap-2">
                  <Skeleton className="h-6 w-32 rounded-md" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                  <Skeleton className="h-6 w-20 rounded-full" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-28 rounded-md" />
                <Skeleton className="h-9 w-20 rounded-md" />
              </div>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="pt-6">
            <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-4 w-40" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ── Attendance Settings Card ─────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-5 w-44" />
            <Skeleton className="mt-1.5 h-3 w-[28rem] max-w-full" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3 rounded-md border bg-card p-4">
              <div className="flex items-start gap-2">
                <Skeleton className="mt-0.5 h-4 w-4 rounded" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-44" />
                  <Skeleton className="h-3 w-[26rem] max-w-full" />
                </div>
              </div>
              <div className="space-y-3">
                <Skeleton className="h-3 w-72 max-w-full" />
                <div className="flex items-baseline justify-between">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-7 w-14" />
                </div>
                <Skeleton className="h-2 w-full rounded-full" />
                <div className="flex items-center justify-between">
                  <Skeleton className="h-3 w-12" />
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-3 w-12" />
                </div>
                <div className="flex justify-end pt-1">
                  <Skeleton className="h-8 w-20 rounded-md" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ── Attendance Overview Card ─────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-5 w-44" />
            <Skeleton className="mt-1.5 h-3 w-96 max-w-full" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-1.5 rounded-md border bg-card px-4 py-3">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="mt-1 h-7 w-16" />
                  <Skeleton className="mt-1 h-3 w-24" />
                </div>
              ))}
            </div>

            {/* Latest session block */}
            <div className="rounded-md border bg-muted/30 p-4">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <div className="space-y-1.5">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-4 w-48" />
                </div>
                <div className="space-y-1 text-right">
                  <Skeleton className="ml-auto h-7 w-16" />
                  <Skeleton className="ml-auto h-3 w-16" />
                </div>
              </div>
              <Skeleton className="h-1.5 w-full rounded-full" />
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-3 w-20" />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ── Sessions Card ────────────────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="mt-1.5 h-3 w-44" />
          </CardHeader>
          <CardContent className="p-0">
            {/* Table header row */}
            <div className="grid grid-cols-[1.4fr_1.2fr_repeat(5,1fr)] gap-4 border-b px-4 py-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton
                  key={i}
                  className={`h-3 ${i < 2 ? 'w-16' : 'w-12 ml-auto'}`}
                />
              ))}
            </div>
            {/* Sample rows */}
            {Array.from({ length: 3 }).map((_, r) => (
              <div
                key={r}
                className="grid grid-cols-[1.4fr_1.2fr_repeat(5,1fr)] items-center gap-4 border-b px-4 py-4 last:border-b-0"
              >
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="ml-auto h-4 w-6" />
                <Skeleton className="ml-auto h-4 w-6" />
                <Skeleton className="ml-auto h-4 w-6" />
                <Skeleton className="ml-auto h-4 w-6" />
                <Skeleton className="ml-auto h-4 w-12" />
              </div>
            ))}
          </CardContent>
        </Card>

        {/* ── Enrolled Students Card ───────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="space-y-1.5">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-3 w-72" />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-8 w-44 rounded-md" />
                <Skeleton className="h-8 w-32 rounded-md" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-10 w-full max-w-md rounded-md" />
            <div className="mt-4 space-y-0">
              {/* Table header */}
              <div className="grid grid-cols-[1.4fr_1fr_1fr_0.7fr_40px] gap-4 border-b py-3">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-28" />
                <Skeleton className="h-3 w-16" />
                <span />
              </div>
              {/* Rows */}
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[1.4fr_1fr_1fr_0.7fr_40px] items-center gap-4 border-b py-4 last:border-b-0"
                >
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-5 w-24 rounded-full" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="ml-auto h-7 w-7 rounded-md" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
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

  const runtimeStatus = (schedule.runtime_status as ScheduleRuntimeStatus) ?? 'scheduled'

  const latestSegments: SegmentSpec[] = latestSession
    ? [
        { key: 'present', label: 'Present', count: latestSession.present, segment: 'bg-emerald-500', swatch: 'bg-emerald-500' },
        { key: 'late', label: 'Late', count: latestSession.late, segment: 'bg-amber-500', swatch: 'bg-amber-500' },
        { key: 'early_leave', label: 'Early Leave', count: latestSession.early_leave, segment: 'bg-orange-500', swatch: 'bg-orange-500' },
        { key: 'absent', label: 'Absent', count: latestSession.absent, segment: 'bg-red-500', swatch: 'bg-red-500' },
      ]
    : []

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/schedules')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Schedules
      </Button>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-2">
              <CardTitle className="text-xl leading-tight">
                {schedule.subject_name}
              </CardTitle>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md border bg-muted/40 px-2 py-0.5 font-mono text-xs text-foreground">
                  {schedule.subject_code}
                </span>
                {schedule.is_active ? (
                  <Badge
                    variant="outline"
                    className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                  >
                    Active
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-muted-foreground/30 text-muted-foreground">
                    Inactive
                  </Badge>
                )}
                {schedule.target_course && (
                  <Badge variant="outline" className="text-muted-foreground">
                    {schedule.target_course}
                  </Badge>
                )}
                {schedule.target_year_level != null && (
                  <Badge variant="outline" className="text-muted-foreground">
                    Year {schedule.target_year_level}
                  </Badge>
                )}
                <RuntimeStatusPill status={runtimeStatus} />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => navigate(`/schedules/${id}/live`)}
                disabled={!schedule.room}
                title={schedule.room ? 'Open live feed' : 'Room required'}
              >
                <Video className="mr-2 h-4 w-4" />
                Watch Live
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetaItem
              label="Faculty"
              value={
                schedule.faculty
                  ? `${schedule.faculty.first_name} ${schedule.faculty.last_name}`
                  : <span className="text-muted-foreground">Unassigned</span>
              }
            />
            <MetaItem
              label="Room"
              value={schedule.room?.name ?? <span className="text-muted-foreground">Unassigned</span>}
            />
            <MetaItem
              label="Schedule"
              value={
                <>
                  {DAY_NAMES[schedule.day_of_week]}
                  <span className="text-muted-foreground"> · </span>
                  {formatTime(schedule.start_time)} – {formatTime(schedule.end_time)}
                </>
              }
            />
            <MetaItem
              label="Semester"
              value={
                <>
                  {schedule.semester}
                  <span className="text-muted-foreground"> · </span>
                  {schedule.academic_year}
                </>
              }
            />
            {(schedule.target_course || schedule.target_year_level != null) && (
              <MetaItem
                label="Program / Year"
                value={
                  <>
                    {schedule.target_course ?? '—'}
                    {schedule.target_year_level != null && (
                      <>
                        <span className="text-muted-foreground"> · </span>
                        Year {schedule.target_year_level}
                      </>
                    )}
                  </>
                }
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Attendance Settings ──────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Attendance Settings</CardTitle>
          <p className="text-xs text-muted-foreground">
            Tuning that controls how this schedule's sessions detect early
            leave. Saving applies immediately to a running session.
          </p>
        </CardHeader>
        <CardContent>
          <EarlyLeaveTimeoutControl
            scheduleId={schedule.id}
            currentMinutes={schedule.early_leave_timeout_minutes ?? null}
            helperText="Lower values flag early leaves faster but tolerate fewer brief gaps (bathroom break, phone). 5 min is a safe default for hour-long classes."
          />
        </CardContent>
      </Card>

      {/* ── Attendance Overview ──────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Attendance Overview</CardTitle>
          <p className="text-xs text-muted-foreground">
            Term to date — aggregated across all sessions held for this schedule.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {overviewLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-[88px] w-full" />
              ))}
            </div>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
                <OverviewStat label="Enrolled" value={enrolledCount} />
                <OverviewStat
                  label="Attendance rate"
                  value={avgAttendanceRate != null ? `${avgAttendanceRate}%` : '—'}
                  hint={avgAttendanceRate != null ? 'Avg across sessions' : 'No sessions yet'}
                />
                <OverviewStat label="Sessions held" value={sessionsHeld} />
                <OverviewStat label="Early leaves" value={earlyLeaveTotal} />
                <OverviewStat
                  label="Last session"
                  value={latestSession ? formatSessionDate(latestSession.date) : '—'}
                  hint={
                    latestSession?.attendance_rate != null
                      ? `${latestSession.attendance_rate}% attendance`
                      : undefined
                  }
                />
              </div>

              {latestSession && (
                <div className="rounded-md border bg-muted/30 p-4">
                  <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                        Latest session
                      </div>
                      <div className="text-sm font-medium text-foreground">
                        {formatSessionDate(latestSession.date)}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {formatTime(latestSession.start_time)} – {formatTime(latestSession.end_time)}
                        </span>
                      </div>
                    </div>
                    {latestSession.attendance_rate != null && (
                      <div className="text-right">
                        <div className="text-2xl font-semibold tabular-nums leading-none">
                          {latestSession.attendance_rate}%
                        </div>
                        <div className="text-[11px] text-muted-foreground">attendance</div>
                      </div>
                    )}
                  </div>
                  <SegmentedBreakdown segments={latestSegments} total={latestSession.total_records} />
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* ── Sessions ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Sessions</CardTitle>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Most recent first{sessions.length ? ` · ${sessions.length} shown` : ''}
          </p>
        </CardHeader>
        <CardContent className="p-0">
          {sessionsLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-muted-foreground">
              No sessions have been held for this schedule yet.
              <div className="mt-1 text-xs">
                A session is recorded once attendance is started — auto-started by the
                lifecycle scheduler when the time window opens, or manually via Watch Live.
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead className="text-right">Present</TableHead>
                  <TableHead className="text-right">Late</TableHead>
                  <TableHead className="text-right">Early Leave</TableHead>
                  <TableHead className="text-right">Absent</TableHead>
                  <TableHead className="text-right">Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((s) => (
                  <TableRow key={s.date}>
                    <TableCell className="font-medium">{formatSessionDate(s.date)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatTime(s.start_time)} – {formatTime(s.end_time)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{s.present}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.late}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.early_leave}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.absent}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {s.attendance_rate != null ? `${s.attendance_rate}%` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ── Enrolled Students ────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">Enrolled Students</CardTitle>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {students.length} enrolled · click a row to open the student profile
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Select value={faceFilter} onValueChange={(v) => setFaceFilter(v as FaceFilter)}>
                <SelectTrigger size="sm" className="h-8 w-44 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All registrations</SelectItem>
                  <SelectItem value="registered">Face registered</SelectItem>
                  <SelectItem value="pending">Face pending</SelectItem>
                </SelectContent>
              </Select>
              <Button size="sm" onClick={() => { setEnrollOpen(true); setEnrollSearch('') }}>
                <Plus className="mr-2 h-4 w-4" />
                Enroll Student
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {studentsError ? (
            <p className="text-sm text-muted-foreground">
              Unable to load enrolled students. The endpoint may not be available yet.
            </p>
          ) : (
            <DataTable
              columns={studentColumns}
              data={filteredStudents}
              isLoading={studentsLoading}
              searchPlaceholder="Search by name, student ID, status..."
              globalFilter={studentSearch}
              onGlobalFilterChange={setStudentSearch}
              globalFilterFn={() => true}
              onRowClick={(row) => navigate(`/users/${row.id}`, { state: { role: 'student' } })}
            />
          )}
        </CardContent>
      </Card>

      {/* Unenroll Confirmation */}
      <AlertDialog open={!!unenrollConfirm} onOpenChange={(open) => !open && setUnenrollConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unenroll student?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove <strong>{unenrollConfirm?.name}</strong> from this schedule?
              This will remove their enrollment and any future attendance tracking.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={confirmUnenroll}
            >
              Unenroll
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reset Face Registration Confirmation */}
      <AlertDialog
        open={!!resetFaceConfirm}
        onOpenChange={(open) => !open && setResetFaceConfirm(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset face registration?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{resetFaceConfirm?.name}</strong> will need to re-register their
              face from the student app before they can be recognised again. Existing
              attendance records are preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={confirmResetFace}
              disabled={deregisterFace.isPending}
            >
              {deregisterFace.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resetting…
                </>
              ) : (
                'Reset registration'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={enrollOpen} onOpenChange={setEnrollOpen}>
        <DialogContent className="sm:max-w-md max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Enroll Student</DialogTitle>
            <DialogDescription>Search and select a student to enroll in this schedule.</DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Search by name or student ID..."
            value={enrollSearch}
            onChange={(e) => setEnrollSearch(e.target.value)}
          />
          <div className="max-h-[300px] overflow-y-auto space-y-1">
            {filteredEnrollableStudents.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                {debouncedEnrollSearch ? 'No matching students found' : 'All students are already enrolled'}
              </p>
            ) : (
              filteredEnrollableStudents.slice(0, 50).map((s) => {
                const isRegistered = !!s.user_id
                return (
                  <div
                    key={s.student_id}
                    className={`flex items-center justify-between rounded-md border px-3 py-2 ${
                      isRegistered ? 'hover:bg-accent cursor-pointer' : 'opacity-50 cursor-not-allowed'
                    }`}
                    onClick={() => isRegistered && s.user_id && handleEnroll(s.user_id, `${s.first_name} ${s.last_name}`)}
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {s.first_name} {s.last_name}
                        {!isRegistered && (
                          <span className="ml-2 text-xs text-muted-foreground">(not registered)</span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">{s.student_id}</p>
                    </div>
                    {isRegistered && <Plus className="h-4 w-4 text-muted-foreground" />}
                  </div>
                )
              })
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEnrollOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { toast } from 'sonner'
import {
  ArrowLeft,
  BookOpen,
  Download,
  Loader2,
  MoreVertical,
  Pencil,
  Plus,
  RotateCcw,
  ScanFace,
  Trash2,
  UserX,
} from 'lucide-react'

import { DataTable } from '@/components/data-tables'
import { FaceVerificationCard } from '@/components/students/FaceVerificationCard'
import { AttendanceDetailSheet } from '@/components/attendance/AttendanceDetailSheet'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useStudentRecord,
  useUpdateStudentRecord,
  useDeactivateStudentRecord,
  useUserAttendance,
  useDeregisterFace,
  useStudentEnrollments,
  useStudentEnrollmentIds,
  useEnrollStudent,
  useUnenrollStudent,
  useSchedules,
} from '@/hooks/use-queries'
import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import { useAuthedImage } from '@/hooks/use-authed-image'
import type { AttendanceRecord, StudentEnrollment } from '@/types'
import { formatStatus } from '@/types/attendance'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'

// ---------------------------------------------------------------------------
// Status taxonomy + helpers for the attendance table.
// ---------------------------------------------------------------------------

type AttendanceStatusKey = 'present' | 'late' | 'early_leave' | 'absent' | 'excused'

const STATUS_PILL_CLASS: Record<string, string> = {
  present:
    'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  late: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  early_leave:
    'border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400',
  absent: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400',
  excused: 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400',
}

const STATUS_HEATMAP_CLASS: Record<string, string> = {
  present: 'bg-emerald-500',
  late: 'bg-amber-500',
  early_leave: 'bg-orange-500',
  absent: 'bg-red-500',
  excused: 'bg-blue-500',
}

const DAY_NAMES_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function buildAttendanceHaystackForRecord(r: AttendanceRecord): string {
  return joinHaystack([
    r.student_name,
    r.subject_code,
    r.remarks,
    formatStatus(r.status),
    r.status,
    r.date,
    ...isoDateHaystackParts(r.date),
    ...isoDateHaystackParts(r.check_in_time),
    ...isoDateHaystackParts(r.check_out_time),
    `${Math.round(r.presence_score)}%`,
  ])
}

// ---------------------------------------------------------------------------
// Small presentational helpers — kept local so the rebuild stays
// self-contained. Lift into components/students/ if any are reused.
// ---------------------------------------------------------------------------

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

/**
 * Avatar that pulls the registered CENTER angle (or the first available angle)
 * via the authed image hook. Falls back to initials when the student has no
 * registration or the image fetch fails.
 */
function StudentAvatar({
  userId,
  initials,
}: {
  userId: string | null
  initials: string
}) {
  const { data: registration } = useRegisteredFaces(userId)
  const angle =
    registration.status === 'ok'
      ? registration.angles.find((a) => a.angle_label?.toLowerCase() === 'center') ??
        registration.angles[0]
      : undefined
  const { src } = useAuthedImage(angle?.image_url ?? null)

  if (src) {
    return (
      <Avatar className="h-16 w-16 text-lg ring-1 ring-border">
        {/* Selfie captures are stored un-mirrored for ArcFace; flip on display
            so the human-perceived direction matches the angle label. See the
            same comment in RegisteredFaceGallery.AngleTile. */}
        <img
          src={src}
          alt="Student"
          className="h-full w-full rounded-full object-cover -scale-x-100"
        />
      </Avatar>
    )
  }
  return (
    <Avatar className="h-16 w-16 text-lg">
      <AvatarFallback className="text-lg">{initials}</AvatarFallback>
    </Avatar>
  )
}

/**
 * Small calendar-strip showing the last `days` days. Each cell colored by the
 * student's attendance status on that date. Hover for the date + status.
 */
function AttendanceHeatmap({
  records,
  days = 30,
}: {
  records: AttendanceRecord[]
  days?: number
}) {
  // Build lookup: ISO date (YYYY-MM-DD) -> first matching record.
  const byDate = useMemo(() => {
    const map = new Map<string, AttendanceRecord>()
    for (const r of records) {
      const key = r.date?.slice(0, 10)
      if (key && !map.has(key)) map.set(key, r)
    }
    return map
  }, [records])

  const cells = useMemo(() => {
    const out: { iso: string; date: Date; record?: AttendanceRecord }[] = []
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(today.getDate() - i)
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      out.push({ iso, date: d, record: byDate.get(iso) })
    }
    return out
  }, [byDate, days])

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-2">
        <div className="flex flex-wrap gap-1">
          {cells.map((c) => {
            const cls = c.record
              ? STATUS_HEATMAP_CLASS[c.record.status] ?? 'bg-muted'
              : 'bg-muted/40'
            return (
              <Tooltip key={c.iso}>
                <TooltipTrigger asChild>
                  <div
                    className={`h-4 w-4 rounded-[3px] ${cls}`}
                    aria-label={c.iso}
                  />
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs">
                  <div className="font-medium">
                    {c.date.toLocaleDateString([], {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </div>
                  <div className="mt-0.5 text-muted-foreground">
                    {c.record
                      ? `${formatStatus(c.record.status)}${
                          c.record.subject_code ? ` · ${c.record.subject_code}` : ''
                        }`
                      : 'No class'}
                  </div>
                </TooltipContent>
              </Tooltip>
            )
          })}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          {(['present', 'late', 'early_leave', 'absent'] as AttendanceStatusKey[]).map(
            (s) => (
              <span key={s} className="inline-flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-[2px] ${STATUS_HEATMAP_CLASS[s]}`} />
                {formatStatus(s)}
              </span>
            ),
          )}
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-[2px] bg-muted/40" />
            No class
          </span>
        </div>
      </div>
    </TooltipProvider>
  )
}

// CSV export helper for the attendance table.
function exportAttendanceCsv(records: AttendanceRecord[], filename: string) {
  const header = ['Date', 'Subject', 'Status', 'Check-in', 'Check-out', 'Presence Score']
  const rows = records.map((r) => [
    r.date,
    r.subject_code ?? '',
    formatStatus(r.status),
    r.check_in_time ?? '',
    r.check_out_time ?? '',
    `${r.presence_score}%`,
  ])
  const csv = [header, ...rows]
    .map((row) =>
      row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','),
    )
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------

export default function StudentRecordDetailPage() {
  const { studentId } = useParams<{ studentId: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: student, isLoading } = useStudentRecord(studentId!)

  const fullName = student ? `${student.first_name} ${student.last_name}` : null
  usePageTitle(fullName ?? 'Student Details')

  useEffect(() => {
    if (fullName) setLabel(fullName)
    return () => setLabel(null)
  }, [fullName, setLabel])

  const { data: attendance = [], isLoading: attendanceLoading } = useUserAttendance(
    student?.user_id ?? '',
    !!student?.user_id,
  )

  const [attendanceSearch, setAttendanceSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | AttendanceStatusKey>('all')

  const filteredAttendance = useMemo(() => {
    let pool: AttendanceRecord[] = attendance
    if (statusFilter !== 'all') {
      pool = pool.filter((r) => r.status === statusFilter)
    }
    if (!attendanceSearch.trim()) return pool
    return pool.filter((r) =>
      tokenMatches(buildAttendanceHaystackForRecord(r), attendanceSearch),
    )
  }, [attendance, attendanceSearch, statusFilter])

  const [editOpen, setEditOpen] = useState(false)
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [deregisterOpen, setDeregisterOpen] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const updateMutation = useUpdateStudentRecord()
  const deactivateMutation = useDeactivateStudentRecord()
  const deregisterMutation = useDeregisterFace()
  const actionLoading = deactivateMutation.isPending || deregisterMutation.isPending

  // Enrollment management
  const {
    data: enrollmentsData,
    isLoading: enrollmentsLoading,
    fetchNextPage: fetchNextEnrollments,
    hasNextPage: hasMoreEnrollments,
    isFetchingNextPage: isFetchingMoreEnrollments,
  } = useStudentEnrollments(student?.user_id ?? '')
  const enrollments = useMemo<StudentEnrollment[]>(
    () => enrollmentsData?.pages.flatMap((p) => p.items) ?? [],
    [enrollmentsData],
  )
  const enrollmentsTotal = enrollmentsData?.pages[0]?.total ?? 0
  const { data: allSchedules = [] } = useSchedules()
  const enrollMutation = useEnrollStudent()
  const unenrollMutation = useUnenrollStudent()
  const [enrollDialogOpen, setEnrollDialogOpen] = useState(false)
  const [selectedScheduleIds, setSelectedScheduleIds] = useState<Set<string>>(new Set())
  const [bulkEnrolling, setBulkEnrolling] = useState(false)
  const [unenrollConfirm, setUnenrollConfirm] = useState<{ scheduleId: string; name: string } | null>(null)
  const [scheduleScope, setScheduleScope] = useState<'current' | 'all'>('current')

  // Lightweight enrolled-ID list for filtering the enroll dialog's available
  // schedules — only fetched when the dialog is opened so we don't pull the
  // full ID list on every student-detail page view.
  const { data: enrolledIds = [] } = useStudentEnrollmentIds(
    student?.user_id ?? '',
    enrollDialogOpen,
  )
  const enrolledScheduleIds = new Set(enrolledIds)
  const availableSchedules = allSchedules.filter(
    (s) => s.is_active && !enrolledScheduleIds.has(s.id),
  )

  // Current-term filter for the enrolled schedules list. The "current term"
  // is whichever academic_year + semester is most common across the
  // enrollment list; in test data with rolling slots that's just the active
  // semester, in production data it's the term the student is currently in.
  const currentTerm = useMemo(() => {
    if (enrollments.length === 0) return null
    const tally = new Map<string, number>()
    for (const e of enrollments) {
      const sch = e.schedule
      if (!sch) continue
      const key = `${sch.semester}|${sch.academic_year}`
      tally.set(key, (tally.get(key) ?? 0) + 1)
    }
    let topKey: string | null = null
    let topCount = 0
    for (const [k, n] of tally) {
      if (n > topCount) {
        topCount = n
        topKey = k
      }
    }
    if (!topKey) return null
    const [semester, academic_year] = topKey.split('|')
    return { semester, academic_year }
  }, [enrollments])

  const visibleEnrollments = useMemo(() => {
    if (scheduleScope === 'all' || !currentTerm) return enrollments
    return enrollments.filter(
      (e) =>
        e.schedule?.semester === currentTerm.semester &&
        e.schedule?.academic_year === currentTerm.academic_year,
    )
  }, [enrollments, scheduleScope, currentTerm])

  useEffect(() => {
    if (!enrollDialogOpen) setSelectedScheduleIds(new Set())
  }, [enrollDialogOpen])

  function toggleScheduleSelected(id: string) {
    setSelectedScheduleIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allSelected =
    availableSchedules.length > 0 &&
    availableSchedules.every((s) => selectedScheduleIds.has(s.id))
  const someSelected = selectedScheduleIds.size > 0 && !allSelected

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedScheduleIds(new Set())
    } else {
      setSelectedScheduleIds(new Set(availableSchedules.map((s) => s.id)))
    }
  }

  async function handleBulkEnroll() {
    if (!student?.user_id || selectedScheduleIds.size === 0) return
    const studentUserId = student.user_id
    const ids = Array.from(selectedScheduleIds)
    setBulkEnrolling(true)
    try {
      const results = await Promise.allSettled(
        ids.map((scheduleId) =>
          enrollMutation.mutateAsync({ scheduleId, studentUserId }),
        ),
      )
      const succeeded = results.filter((r) => r.status === 'fulfilled').length
      const failed = results.length - succeeded
      if (succeeded > 0) {
        toast.success(`Enrolled in ${succeeded} schedule${succeeded === 1 ? '' : 's'}.`)
      }
      if (failed > 0) {
        toast.error(`Failed to enroll in ${failed} schedule${failed === 1 ? '' : 's'}.`)
      }
      setSelectedScheduleIds(new Set())
      if (failed === 0) setEnrollDialogOpen(false)
    } finally {
      setBulkEnrolling(false)
    }
  }

  const [form, setForm] = useState({
    student_id: '',
    first_name: '',
    middle_name: '',
    last_name: '',
    email: '',
    course: '',
    year_level: '',
    section: '',
    birthdate: '',
    contact_number: '',
  })
  useEffect(() => {
    if (editOpen && student) {
      setForm({
        student_id: student.student_id,
        first_name: student.first_name,
        middle_name: student.middle_name ?? '',
        last_name: student.last_name,
        email: student.email ?? '',
        course: student.course ?? '',
        year_level: student.year_level ? String(student.year_level) : '',
        section: student.section ?? '',
        birthdate: student.birthdate ?? '',
        contact_number: student.contact_number ?? '',
      })
    }
  }, [editOpen, student])

  function handleChange(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!student) return
    if (!form.first_name || !form.last_name) {
      toast.error('First name and last name are required.')
      return
    }
    const trimmedStudentId = form.student_id.trim().toUpperCase()
    if (!trimmedStudentId) {
      toast.error('Student ID is required.')
      return
    }
    const idChanged = trimmedStudentId !== student.student_id
    try {
      await updateMutation.mutateAsync({
        studentId: student.student_id,
        data: {
          student_id: idChanged ? trimmedStudentId : undefined,
          first_name: form.first_name,
          middle_name: form.middle_name || undefined,
          last_name: form.last_name,
          email: form.email || undefined,
          course: form.course || undefined,
          year_level: form.year_level ? Number(form.year_level) : undefined,
          section: form.section || undefined,
          birthdate: form.birthdate || undefined,
          contact_number: form.contact_number || undefined,
        },
      })
      toast.success(`${form.first_name} ${form.last_name} has been updated.`)
      setEditOpen(false)
      if (idChanged) {
        navigate(`/students/${trimmedStudentId}`, { replace: true })
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      const msg = e?.response?.data?.detail || e?.message || 'Failed to update'
      const errorMsg = typeof msg === 'string' ? msg : JSON.stringify(msg)
      toast.error(errorMsg)
    }
  }

  const handleDeactivate = async () => {
    if (!student) return
    try {
      await deactivateMutation.mutateAsync(student.student_id)
      toast.success(`${student.first_name} ${student.last_name} has been deactivated.`)
      navigate('/students')
    } catch {
      toast.error('Failed to deactivate student record.')
    }
  }

  const handleDeregister = async () => {
    if (!student?.user_id) return
    try {
      await deregisterMutation.mutateAsync(student.user_id)
      toast.success(`Face data for ${student.first_name} ${student.last_name} has been removed.`)
      setDeregisterOpen(false)
    } catch {
      toast.error('Failed to deregister face.')
    }
  }

  // ── Term-to-date aggregates derived from the attendance list ──
  const summary = useMemo(() => {
    if (!attendance.length) {
      return {
        attendanceRate: null as number | null,
        sessionsAttended: 0,
        late: 0,
        earlyLeave: 0,
        absent: 0,
        lastAttended: null as AttendanceRecord | null,
        total: 0,
      }
    }
    let attended = 0
    let late = 0
    let earlyLeave = 0
    let absent = 0
    let lastAttended: AttendanceRecord | null = null
    for (const r of attendance) {
      if (r.status === 'present' || r.status === 'late') {
        attended += 1
        if (!lastAttended || r.date > lastAttended.date) lastAttended = r
      }
      if (r.status === 'late') late += 1
      if (r.status === 'early_leave') earlyLeave += 1
      if (r.status === 'absent') absent += 1
    }
    return {
      attendanceRate: Math.round((attended / attendance.length) * 1000) / 10,
      sessionsAttended: attended,
      late,
      earlyLeave,
      absent,
      lastAttended,
      total: attendance.length,
    }
  }, [attendance])

  const attendanceColumns: ColumnDef<AttendanceRecord>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => (
        <span className="text-sm">
          {safeFormat(row.original.date, 'MMM d, yyyy')}
        </span>
      ),
    },
    {
      accessorKey: 'subject_code',
      header: 'Subject',
      cell: ({ row }) => (
        <span className="text-sm">{row.original.subject_code ?? '—'}</span>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => (
        <span
          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
            STATUS_PILL_CLASS[row.original.status] ??
            'border-muted-foreground/30 text-muted-foreground'
          }`}
        >
          {formatStatus(row.original.status)}
        </span>
      ),
    },
    {
      accessorKey: 'check_in_time',
      header: 'Check-in Time',
      cell: ({ row }) => (
        <span className="text-sm tabular-nums">
          {safeFormat(row.original.check_in_time, 'h:mm a')}
        </span>
      ),
    },
    {
      accessorKey: 'check_out_time',
      header: 'Check-out Time',
      cell: ({ row }) => (
        <span className="text-sm tabular-nums">
          {safeFormat(row.original.check_out_time, 'h:mm a')}
        </span>
      ),
    },
    {
      accessorKey: 'presence_score',
      header: 'Presence Score',
      cell: ({ row }) => (
        <span className="font-mono text-xs tabular-nums">
          {row.original.presence_score}%
        </span>
      ),
    },
  ]

  if (isLoading) {
    // Mirror the loaded layout (Back → Header → At a glance → Profile →
    // Attendance History → Enrolled Schedules) so the cut-over to real
    // data doesn't shift the page. Each block is sized to match its
    // eventual counterpart's width, height, and rhythm.
    return (
      <div className="space-y-6">
        {/* Back to Students */}
        <Skeleton className="h-9 w-36 rounded-md" />

        {/* ── Header Card (avatar + name + 5 badges + actions) ─────── */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-4">
                <Skeleton className="h-16 w-16 shrink-0 rounded-full" />
                <div className="min-w-0 space-y-2">
                  <Skeleton className="h-7 w-64" />
                  <div className="flex flex-wrap items-center gap-2">
                    <Skeleton className="h-6 w-24 rounded-md" />
                    <Skeleton className="h-5 w-16 rounded-full" />
                    <Skeleton className="h-5 w-16 rounded-full" />
                    <Skeleton className="h-5 w-24 rounded-full" />
                    <Skeleton className="h-5 w-28 rounded-full" />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-20 rounded-md" />
                <Skeleton className="h-9 w-9 rounded-md" />
              </div>
            </div>
          </CardHeader>
        </Card>

        {/* ── At a glance — 5 OverviewStat cards ───────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="mt-1.5 h-3 w-72" />
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="space-y-1.5 rounded-md border bg-card px-4 py-3"
                >
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="mt-1 h-7 w-16" />
                  <Skeleton className="mt-1 h-3 w-20" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ── Profile (5 MetaItems in a 3-col grid) ────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-5 w-20" />
          </CardHeader>
          <Separator />
          <CardContent className="pt-6">
            <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-4 w-44" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ── Attendance History (heatmap + filter pills + table) ───── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="space-y-1.5">
                <Skeleton className="h-5 w-44" />
                <Skeleton className="h-3 w-72" />
              </div>
              <Skeleton className="h-8 w-28 rounded-md" />
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Heatmap */}
            <Skeleton className="h-12 w-full rounded-md" />

            {/* Filter chip row */}
            <div className="flex flex-wrap items-center gap-2">
              <Skeleton className="h-3 w-12" />
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-16 rounded-full" />
              ))}
            </div>

            {/* Search bar (DataTable toolbar) */}
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />

            {/* Table — borderless variant from DataTable */}
            <div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={`stud-att-skel-${String(i)}`}>
                      <TableCell>
                        <Skeleton className="h-4 w-24" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-40" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-20 rounded-full" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-12" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {/* ── Enrolled Schedules ───────────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="space-y-1.5">
                <Skeleton className="h-5 w-44" />
                <Skeleton className="h-3 w-60" />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-8 w-44 rounded-md" />
                <Skeleton className="h-8 w-40 rounded-md" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Day · Time</TableHead>
                  <TableHead>Faculty</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={`stud-enr-skel-${String(i)}`}>
                    <TableCell>
                      <Skeleton className="h-3 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-40" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Skeleton className="ml-auto h-8 w-8 rounded-md" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!student) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/students')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Students
        </Button>
        <p className="text-muted-foreground">Student record not found.</p>
      </div>
    )
  }

  const initials = `${student.first_name.charAt(0)}${student.last_name.charAt(0)}`.toUpperCase()
  const courseLine =
    [
      student.course,
      student.year_level ? `Year ${student.year_level}` : null,
      student.section ? `Section ${student.section}` : null,
    ]
      .filter(Boolean)
      .join(' · ') || '—'

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/students')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Students
      </Button>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-4">
              <StudentAvatar userId={student.user_id ?? null} initials={initials} />
              <div className="min-w-0 space-y-2">
                <CardTitle className="text-xl leading-tight">
                  {student.first_name}{' '}
                  {student.middle_name ? `${student.middle_name} ` : ''}
                  {student.last_name}
                </CardTitle>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border bg-muted/40 px-2 py-0.5 font-mono text-xs text-foreground">
                    {student.student_id}
                  </span>
                  <Badge variant="outline" className="text-muted-foreground">
                    Student
                  </Badge>
                  {student.is_active ? (
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
                  {student.is_registered ? (
                    <Badge
                      variant="outline"
                      className="border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400"
                    >
                      App Linked
                    </Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                    >
                      App Not Linked
                    </Badge>
                  )}
                  {student.has_face_registered ? (
                    <Badge
                      variant="outline"
                      className="inline-flex items-center gap-1 border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                    >
                      <ScanFace className="h-3 w-3" />
                      Face Enrolled
                    </Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                    >
                      Face Pending
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-9 w-9"
                    aria-label="More actions"
                    disabled={actionLoading}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem
                    disabled={!student.is_registered || !student.has_face_registered}
                    onClick={() => setDeregisterOpen(true)}
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Reset face registration
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    disabled={!student.is_active}
                    className="text-destructive focus:text-destructive"
                    onClick={() => setDeactivateOpen(true)}
                  >
                    <UserX className="mr-2 h-4 w-4" />
                    Deactivate student
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* ── At-a-glance Summary ──────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">At a glance</CardTitle>
          <p className="text-xs text-muted-foreground">
            Aggregated across this student's attendance records to date.
          </p>
        </CardHeader>
        <CardContent>
          {attendanceLoading && summary.total === 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-[88px] w-full" />
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
              <OverviewStat
                label="Schedules enrolled"
                value={enrollmentsTotal}
                hint={
                  currentTerm
                    ? `${currentTerm.semester} · ${currentTerm.academic_year}`
                    : undefined
                }
              />
              <OverviewStat
                label="Attendance rate"
                value={summary.attendanceRate != null ? `${summary.attendanceRate}%` : '—'}
                hint={
                  summary.total > 0
                    ? `${summary.sessionsAttended} of ${summary.total} sessions`
                    : 'No records yet'
                }
              />
              <OverviewStat
                label="Late marks"
                value={summary.late}
                hint={summary.late > 0 ? 'Counted toward attendance' : undefined}
              />
              <OverviewStat
                label="Early leaves"
                value={summary.earlyLeave}
                hint={summary.earlyLeave > 0 ? 'Left before session ended' : undefined}
              />
              <OverviewStat
                label="Last attended"
                value={
                  summary.lastAttended
                    ? safeFormat(summary.lastAttended.date, 'MMM d, yyyy')
                    : '—'
                }
                hint={summary.lastAttended?.subject_code ?? undefined}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Identity / Meta ──────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Profile</CardTitle>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetaItem
              label="Email"
              value={
                student.email ? (
                  <a
                    href={`mailto:${student.email}`}
                    className="text-foreground underline-offset-4 hover:underline"
                  >
                    {student.email}
                  </a>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )
              }
            />
            <MetaItem
              label="Contact"
              value={student.contact_number ?? <span className="text-muted-foreground">—</span>}
            />
            <MetaItem label="Course" value={courseLine} />
            <MetaItem
              label="Birthdate"
              value={
                student.birthdate ? (
                  safeFormat(student.birthdate, 'MMM d, yyyy')
                ) : (
                  <span className="text-muted-foreground">—</span>
                )
              }
            />
            <MetaItem
              label="Added to registry"
              value={safeFormat(student.created_at, 'MMM d, yyyy')}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Attendance History ──────────────────────────────────────── */}
      {student.is_registered && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base">Attendance History</CardTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Last 30 days plus the full searchable record below.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={attendance.length === 0}
                onClick={() =>
                  exportAttendanceCsv(
                    filteredAttendance,
                    `attendance-${student.student_id}.csv`,
                  )
                }
              >
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Heatmap */}
            {attendanceLoading ? (
              <Skeleton className="h-12 w-full" />
            ) : attendance.length === 0 ? null : (
              <AttendanceHeatmap records={attendance} days={30} />
            )}

            {/* Status filter */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Filter
              </span>
              {(['all', 'present', 'late', 'early_leave', 'absent'] as const).map((f) => {
                const active = statusFilter === f
                const label = f === 'all' ? 'All' : formatStatus(f)
                return (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setStatusFilter(f)}
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition ${
                      active
                        ? 'border-foreground bg-foreground text-background'
                        : 'border-border text-muted-foreground hover:bg-muted/60'
                    }`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>

            <DataTable
              columns={attendanceColumns}
              data={filteredAttendance}
              isLoading={attendanceLoading}
              searchPlaceholder="Search by subject, status, date, score..."
              globalFilter={attendanceSearch}
              onGlobalFilterChange={setAttendanceSearch}
              globalFilterFn={() => true}
              borderless
              onRowClick={(row) => {
                setSelectedRecord(row)
                setDetailOpen(true)
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* ── Face Profile ─────────────────────────────────────────────── */}
      {student.is_registered && student.has_face_registered && student.user_id && (
        <FaceVerificationCard userId={student.user_id} />
      )}

      {/* ── Enrolled Schedules ───────────────────────────────────────── */}
      {student.user_id && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BookOpen className="h-4 w-4 text-muted-foreground" />
                  Enrolled Schedules
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {scheduleScope === 'current' && currentTerm
                    ? `Showing ${visibleEnrollments.length} for ${currentTerm.semester} · ${currentTerm.academic_year}`
                    : `Showing all ${enrollmentsTotal} enrollments`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {currentTerm && (
                  <Select
                    value={scheduleScope}
                    onValueChange={(v) => setScheduleScope(v as 'current' | 'all')}
                  >
                    <SelectTrigger size="sm" className="h-8 w-44 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="current">Current term only</SelectItem>
                      <SelectItem value="all">All terms</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <Button size="sm" onClick={() => setEnrollDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Enroll in Schedule
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {enrollmentsLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : visibleEnrollments.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                {enrollmentsTotal === 0 ? (
                  'No enrollments yet.'
                ) : (
                  <>
                    No enrollments in the current term.
                    <button
                      type="button"
                      className="ml-2 underline-offset-4 hover:underline"
                      onClick={() => setScheduleScope('all')}
                    >
                      Show all terms
                    </button>
                  </>
                )}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Day · Time</TableHead>
                    <TableHead>Faculty</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleEnrollments.map((e) => {
                    const sch = e.schedule
                    const code = sch?.subject_code ?? '—'
                    const name = sch?.subject_name ?? '—'
                    const dayTime = sch
                      ? `${DAY_NAMES_SHORT[sch.day_of_week]} · ${sch.start_time?.slice(0, 5)} – ${sch.end_time?.slice(0, 5)}`
                      : '—'
                    return (
                      <TableRow
                        key={e.enrollment_id}
                        className="cursor-pointer"
                        onClick={() => sch && navigate(`/schedules/${sch.id}`)}
                      >
                        <TableCell className="font-mono text-xs">{code}</TableCell>
                        <TableCell className="font-medium">{name}</TableCell>
                        <TableCell className="text-muted-foreground">{dayTime}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {sch?.faculty_name ?? '—'}
                        </TableCell>
                        <TableCell
                          className="text-right"
                          onClick={(ev) => ev.stopPropagation()}
                        >
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                aria-label={`Actions for ${code}`}
                              >
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-44">
                              <DropdownMenuItem
                                onClick={() => sch && navigate(`/schedules/${sch.id}`)}
                              >
                                View schedule
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onClick={() =>
                                  setUnenrollConfirm({
                                    scheduleId: e.schedule_id,
                                    name: `${code} – ${name}`,
                                  })
                                }
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Unenroll
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
            {scheduleScope === 'all' && hasMoreEnrollments && (
              <div className="flex flex-col items-center gap-1 border-t px-4 py-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchNextEnrollments()}
                  disabled={isFetchingMoreEnrollments}
                >
                  {isFetchingMoreEnrollments ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    'Load more'
                  )}
                </Button>
                <p className="text-xs text-muted-foreground">
                  Showing {enrollments.length} of {enrollmentsTotal}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Deactivate Confirmation */}
      <AlertDialog open={deactivateOpen} onOpenChange={setDeactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate student?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate {student.first_name}{' '}
              {student.last_name}? They will be removed from the active registry.
              Existing attendance records are preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeactivate}
              disabled={actionLoading}
            >
              {actionLoading ? 'Deactivating…' : 'Deactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reset Face Registration Confirmation */}
      <AlertDialog open={deregisterOpen} onOpenChange={setDeregisterOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset face registration?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{student.first_name} {student.last_name}</strong> will need to
              re-register their face from the student app before they can be recognised
              again. Existing attendance records are preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeregister}
              disabled={actionLoading}
            >
              {actionLoading ? 'Resetting…' : 'Reset registration'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Unenroll Confirmation */}
      <AlertDialog open={!!unenrollConfirm} onOpenChange={(open) => !open && setUnenrollConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unenroll from schedule?</AlertDialogTitle>
            <AlertDialogDescription>
              Remove {student.first_name} from <strong>{unenrollConfirm?.name}</strong>?
              This will remove their enrollment and any future attendance tracking for
              this schedule.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (unenrollConfirm && student.user_id) {
                  unenrollMutation.mutate(
                    { scheduleId: unenrollConfirm.scheduleId, studentUserId: student.user_id },
                    { onSuccess: () => { toast.success('Unenrolled successfully'); setUnenrollConfirm(null) } }
                  )
                }
              }}
            >
              Unenroll
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Enroll in Schedule Dialog */}
      <Dialog open={enrollDialogOpen} onOpenChange={setEnrollDialogOpen}>
        <DialogContent className="sm:max-w-md max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Enroll in Schedule</DialogTitle>
            <DialogDescription>
              Select one or more schedules to enroll {student.first_name} in.
            </DialogDescription>
          </DialogHeader>
          {availableSchedules.length > 0 && (
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <Checkbox
                  checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                  onCheckedChange={toggleSelectAll}
                  aria-label="Select all schedules"
                />
                <span className="text-sm font-medium">
                  {allSelected ? 'Deselect all' : 'Select all'}
                </span>
              </label>
              <span className="text-xs text-muted-foreground">
                {selectedScheduleIds.size} of {availableSchedules.length} selected
              </span>
            </div>
          )}
          <div className="max-h-[300px] overflow-y-auto space-y-1">
            {availableSchedules.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                {enrollmentsTotal > 0 ? 'Enrolled in all available schedules.' : 'No active schedules available.'}
              </p>
            ) : (
              availableSchedules.map((s) => {
                const checked = selectedScheduleIds.has(s.id)
                return (
                  <label
                    key={s.id}
                    className="flex items-center gap-3 rounded-md border px-3 py-2 hover:bg-accent cursor-pointer"
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => toggleScheduleSelected(s.id)}
                      aria-label={`Select ${s.subject_code}`}
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{s.subject_code} - {s.subject_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {DAY_NAMES_SHORT[s.day_of_week]} {s.start_time?.slice(0,5)} - {s.end_time?.slice(0,5)}
                        {s.faculty_name ? ` · ${s.faculty_name}` : ''}
                      </p>
                    </div>
                  </label>
                )
              })
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEnrollDialogOpen(false)}
              disabled={bulkEnrolling}
            >
              Cancel
            </Button>
            <Button
              onClick={handleBulkEnroll}
              disabled={selectedScheduleIds.size === 0 || bulkEnrolling}
            >
              {bulkEnrolling ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enrolling...
                </>
              ) : (
                `Enroll Selected${selectedScheduleIds.size > 0 ? ` (${selectedScheduleIds.size})` : ''}`
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AttendanceDetailSheet
        record={selectedRecord}
        studentId={student.user_id ?? null}
        studentName={fullName ?? undefined}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Edit Student</DialogTitle>
            <DialogDescription>
              Update the details for {student.first_name} {student.last_name}.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleEditSubmit} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit_student_id">Student ID *</Label>
              <Input
                id="edit_student_id"
                placeholder="21-A-012345"
                value={form.student_id}
                onChange={(e) => handleChange('student_id', e.target.value)}
              />
              {student.is_registered && form.student_id.trim().toUpperCase() !== student.student_id && (
                <p className="text-xs text-muted-foreground">
                  This student has an app account. Renaming will also update the linked user.
                </p>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_first_name">First Name *</Label>
                <Input
                  id="edit_first_name"
                  placeholder="Juan"
                  value={form.first_name}
                  onChange={(e) => handleChange('first_name', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_middle_name">Middle Name</Label>
                <Input
                  id="edit_middle_name"
                  placeholder="Santos"
                  value={form.middle_name}
                  onChange={(e) => handleChange('middle_name', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_last_name">Last Name *</Label>
                <Input
                  id="edit_last_name"
                  placeholder="Dela Cruz"
                  value={form.last_name}
                  onChange={(e) => handleChange('last_name', e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_email">Email</Label>
                <Input
                  id="edit_email"
                  type="email"
                  placeholder="juan@jrmsu.edu.ph"
                  value={form.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_birthdate">Birthdate</Label>
                <Input
                  id="edit_birthdate"
                  type="date"
                  value={form.birthdate}
                  onChange={(e) => handleChange('birthdate', e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_course">Course</Label>
                <Input
                  id="edit_course"
                  placeholder="BSCPE"
                  value={form.course}
                  onChange={(e) => handleChange('course', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_year_level">Year Level</Label>
                <Select
                  value={form.year_level}
                  onValueChange={(v) => handleChange('year_level', v)}
                >
                  <SelectTrigger id="edit_year_level">
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_section">Section</Label>
                <Input
                  id="edit_section"
                  placeholder="A"
                  value={form.section}
                  onChange={(e) => handleChange('section', e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit_contact_number">Contact Number</Label>
              <Input
                id="edit_contact_number"
                placeholder="09xxxxxxxxx"
                value={form.contact_number}
                onChange={(e) => handleChange('contact_number', e.target.value)}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditOpen(false)}
                disabled={updateMutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? (
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

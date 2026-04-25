import { useEffect, useMemo, useState, useTransition } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { formatTimestamp, formatFullDatetime, formatDateOnly } from '@/lib/format-time'
import {
  Activity as ActivityIcon,
  ArrowLeft,
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  Loader2,
  MoreVertical,
  Pencil,
  ScanFace,
  UserCheck,
  UserX,
} from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useUser,
  useUserAttendance,
  useDeactivateUser,
  useReactivateUser,
  useDeregisterFace,
  useSchedules,
  useActivityEvents,
} from '@/hooks/use-queries'
import type {
  UserRole,
  AttendanceRecord,
  ScheduleResponse,
  ActivityEvent,
  ActivitySeverity,
} from '@/types'
import { formatStatus } from '@/types/attendance'
import { EditUserDialog } from './edit-user-dialog'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'

const DAY_NAMES_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const roleBackRoutes: Record<string, { path: string; label: string }> = {
  student: { path: '/students', label: 'Back to Students' },
  faculty: { path: '/faculty', label: 'Back to Faculty' },
  admin: { path: '/admins', label: 'Back to Admins' },
}

const roleChipClass: Record<UserRole, string> = {
  student: 'border-muted-foreground/30 text-muted-foreground',
  faculty: 'border-muted-foreground/30 text-muted-foreground',
  admin: 'border-muted-foreground/30 text-muted-foreground',
}

const STATUS_PILL_CLASS: Record<string, string> = {
  present:
    'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  late: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  early_leave:
    'border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400',
  absent: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400',
  excused: 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400',
}

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
// Local presentational helpers — same families used on the schedule, student,
// and live-feed redesigns. Lift to components/users/ if any get reused.
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
 * UUID display + click-to-copy. Used for the admin's account ID — the
 * piece of data support tickets always need but operators have to dig
 * the URL bar for. The copy state flips for ~1.5 s to give clear
 * feedback without a toast (toast usage is reserved for actions that
 * change server state).
 */
function AccountIdField({ id }: { id: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy to clipboard')
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="group inline-flex items-center gap-1.5 rounded-md border bg-muted/40 px-2 py-1 font-mono text-xs text-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label="Copy account ID"
      title="Copy to clipboard"
    >
      <span className="truncate">{id}</span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0 text-emerald-500" />
      ) : (
        <Copy className="h-3 w-3 shrink-0 text-muted-foreground transition group-hover:text-foreground" />
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Admin activity helpers — all client-side derivations from the
// `/api/v1/activity/events` endpoint with `actor_id={admin}` filter.
// ---------------------------------------------------------------------------

const SEVERITY_DOT_CLASS: Record<ActivitySeverity, string> = {
  info: 'bg-muted-foreground/60',
  success: 'bg-emerald-500',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
}

/**
 * Map a backend `event_type` constant to a friendly past-tense verb
 * suitable for the admin activity feed. Falls back to a sentence-cased
 * version of the raw type so a new event_type added server-side doesn't
 * crash the page — it just reads "User created" / "Some new event" until
 * we extend the dictionary.
 */
const EVENT_TYPE_LABEL: Record<string, string> = {
  ADMIN_LOGIN: 'Signed in',
  FACULTY_LOGIN: 'Signed in',
  STUDENT_LOGIN: 'Signed in',
  USER_CREATED: 'Created user',
  USER_UPDATED: 'Updated user',
  USER_DELETED: 'Deactivated user',
  FACE_REGISTRATION_APPROVED: 'Approved face registration',
  SETTINGS_CHANGED: 'Updated settings',
  SCHEDULE_CREATED: 'Created schedule',
  SCHEDULE_UPDATED: 'Updated schedule',
  SCHEDULE_DELETED: 'Deleted schedule',
  ENROLLMENT_ADDED: 'Enrolled student',
  ENROLLMENT_REMOVED: 'Unenrolled student',
  SESSION_STARTED_MANUAL: 'Started session',
  SESSION_ENDED_MANUAL: 'Ended session',
  SESSION_STARTED_AUTO: 'Session auto-started',
  SESSION_ENDED_AUTO: 'Session auto-ended',
}

function formatEventLabel(eventType: string): string {
  if (EVENT_TYPE_LABEL[eventType]) return EVENT_TYPE_LABEL[eventType]
  // Fallback: SCREAMING_SNAKE_CASE -> "Sentence case"
  const lower = eventType.toLowerCase().replace(/_/g, ' ')
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}

const LOGIN_EVENT_TYPES = 'ADMIN_LOGIN,FACULTY_LOGIN,STUDENT_LOGIN'
const SCHEDULE_EVENT_TYPES = 'SCHEDULE_CREATED,SCHEDULE_UPDATED,SCHEDULE_DELETED'

/**
 * Pick the most operationally-useful target string for an event row.
 * Examples:
 *   USER_CREATED       → subject_user_name
 *   SCHEDULE_UPDATED   → subject_schedule_subject
 *   ENROLLMENT_ADDED   → "{student} → {schedule}"
 *   ADMIN_LOGIN        → "" (the actor is the subject)
 */
function describeTarget(ev: ActivityEvent): string {
  if (ev.event_type.endsWith('_LOGIN')) return ''
  if (ev.event_type.startsWith('ENROLLMENT_')) {
    const parts: string[] = []
    if (ev.subject_user_name) parts.push(ev.subject_user_name)
    if (ev.subject_schedule_subject) parts.push(ev.subject_schedule_subject)
    return parts.join(' → ')
  }
  if (ev.subject_user_name) return ev.subject_user_name
  if (ev.subject_schedule_subject) return ev.subject_schedule_subject
  return ''
}

/**
 * Renders the admin's 30-day activity stats + recent activity feed.
 * Mounted only when `user.role === 'admin'`.
 */
function AdminActivitySection({
  adminId,
  navigateToActivity,
}: {
  adminId: string
  navigateToActivity: () => void
}) {
  // 30-day audit-event window for stats + feed.
  // 30 days = 30 * 24 * 60 * 60 * 1000 ms. We snapshot at mount via lazy
  // useState init so the value is stable across re-renders (calling
  // Date.now() inside useMemo is flagged as impure). If the page sits
  // open for hours the window drifts slightly — fine for an aggregate
  // view; the operator can navigate away and back to refresh.
  const [since] = useState(() =>
    new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
  )

  // 30-day audit slice for this admin — feeds both the stats card and the
  // recent activity feed below. limit=200 covers most active admins for
  // a month; if next_cursor is non-null we surface "200+" rather than
  // misleading the operator with a precise count.
  const { data: auditData, isLoading: auditLoading } = useActivityEvents({
    actor_id: adminId,
    category: 'audit',
    since,
    limit: 200,
  })
  // Last sign-in — separate, tiny query so it isn't capped by the audit
  // window. Login events are technically `audit` category too, but
  // surfacing the most-recent one as its own metric is clearer than
  // making operators scroll the feed.
  const { data: loginData } = useActivityEvents({
    actor_id: adminId,
    event_type: LOGIN_EVENT_TYPES,
    limit: 1,
  })

  const events = useMemo<ActivityEvent[]>(
    () => auditData?.items ?? [],
    [auditData],
  )
  const hasMore = !!auditData?.next_cursor

  const stats = useMemo(() => {
    let userCreated = 0
    let scheduleTouched = 0
    const scheduleEventSet = new Set(SCHEDULE_EVENT_TYPES.split(','))
    for (const e of events) {
      if (e.event_type === 'USER_CREATED') userCreated += 1
      if (scheduleEventSet.has(e.event_type)) scheduleTouched += 1
    }
    return { userCreated, scheduleTouched, total: events.length }
  }, [events])

  const lastLogin = loginData?.items?.[0]?.created_at ?? null

  // The recent feed is the same data as stats, just trimmed to the most
  // recent N. Keeping it derived (instead of a second fetch with limit=20)
  // means the two sections stay consistent even when paginating later.
  const feed = events.slice(0, 20)

  return (
    <div className="space-y-6">
      {/* ── Activity stats ─────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Admin activity</CardTitle>
          <p className="text-xs text-muted-foreground">
            Last 30 days of audit events attributed to this account.
          </p>
        </CardHeader>
        <CardContent>
          {auditLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-[88px] w-full" />
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
              <OverviewStat
                label="Actions (30d)"
                value={hasMore ? `${stats.total}+` : stats.total}
                hint={
                  stats.total === 0
                    ? 'No audit events recorded'
                    : hasMore
                      ? 'Showing first 200'
                      : undefined
                }
              />
              <OverviewStat
                label="Users provisioned"
                value={stats.userCreated}
                hint={stats.userCreated === 1 ? '1 user record' : 'distinct user records'}
              />
              <OverviewStat
                label="Schedules touched"
                value={stats.scheduleTouched}
                hint="created · updated · deleted"
              />
              <OverviewStat
                label="Last sign-in"
                value={lastLogin ? formatDateOnly(lastLogin) : '—'}
                hint={lastLogin ? formatTimestamp(lastLogin) : 'No login events recorded'}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Recent activity feed ───────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <ActivityIcon className="h-4 w-4 text-muted-foreground" />
                Recent activity
              </CardTitle>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {auditLoading
                  ? 'Loading…'
                  : feed.length === 0
                    ? 'No audit events for this admin in the last 30 days'
                    : `Showing ${feed.length} most recent · newest first`}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={navigateToActivity}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Full activity log
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {auditLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : feed.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-muted-foreground">
              Nothing to show here yet. Audit events appear when this admin creates
              users, edits schedules, manually starts/ends sessions, or changes
              settings.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-44">When</TableHead>
                  <TableHead className="w-56">Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Summary</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {feed.map((ev) => {
                  const target = describeTarget(ev)
                  return (
                    <TableRow key={ev.event_id}>
                      <TableCell
                        className="font-mono text-xs text-muted-foreground"
                        title={formatFullDatetime(ev.created_at)}
                      >
                        {formatTimestamp(ev.created_at)}
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-2">
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT_CLASS[ev.severity] ?? SEVERITY_DOT_CLASS.info}`}
                            aria-hidden
                          />
                          <span className="text-sm font-medium">
                            {formatEventLabel(ev.event_type)}
                          </span>
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-foreground">
                        {target || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                        {ev.summary || <span>—</span>}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const stateRole = (location.state as { role?: string })?.role
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: user, isLoading } = useUser(id!)

  const fullName = user ? `${user.first_name} ${user.last_name}` : null
  usePageTitle(fullName ?? 'User Details')

  useEffect(() => {
    if (fullName) setLabel(fullName)
    return () => setLabel(null)
  }, [fullName, setLabel])

  const { data: attendance = [], isLoading: attendanceLoading } = useUserAttendance(
    id!,
    !!user && user.role === 'student',
  )

  const [attendanceSearch, setAttendanceSearch] = useState('')
  const [, startAttendanceSearchTransition] = useTransition()
  const filteredAttendance = useMemo(() => {
    if (!attendanceSearch.trim()) return attendance
    return attendance.filter((r: AttendanceRecord) =>
      tokenMatches(buildAttendanceHaystackForRecord(r), attendanceSearch),
    )
  }, [attendance, attendanceSearch])

  const { data: allSchedules = [], isLoading: schedulesLoading } = useSchedules()
  const facultySchedules = useMemo<ScheduleResponse[]>(
    () =>
      user?.role === 'faculty'
        ? allSchedules.filter((s) => s.faculty_id === user.id)
        : [],
    [allSchedules, user],
  )

  // Detect the dominant (semester, academic_year) across the faculty's
  // schedules so the table can default to "current term only" — matching
  // the student detail page redesign. With test fixtures this collapses
  // 35 rows down to a sensible handful.
  const currentTerm = useMemo(() => {
    if (facultySchedules.length === 0) return null
    const tally = new Map<string, number>()
    for (const s of facultySchedules) {
      const key = `${s.semester}|${s.academic_year}`
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
  }, [facultySchedules])

  const [scheduleScope, setScheduleScope] = useState<'current' | 'all'>('current')
  const visibleSchedules = useMemo(() => {
    if (scheduleScope === 'all' || !currentTerm) return facultySchedules
    return facultySchedules.filter(
      (s) =>
        s.semester === currentTerm.semester &&
        s.academic_year === currentTerm.academic_year,
    )
  }, [facultySchedules, scheduleScope, currentTerm])

  // Sort by day-of-week then start time so the table reads chronologically.
  const sortedSchedules = useMemo(() => {
    return [...visibleSchedules].sort((a, b) => {
      if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week
      return (a.start_time ?? '').localeCompare(b.start_time ?? '')
    })
  }, [visibleSchedules])

  // ── Teaching summary aggregates (faculty only). All client-side from
  // the schedules list — no backend changes required. ──
  const teachingStats = useMemo(() => {
    const list = facultySchedules
    const subjects = new Set(list.map((s) => s.subject_code))
    const days = new Set(list.map((s) => s.day_of_week))
    const rooms = new Set(list.map((s) => s.room?.id ?? s.room_id).filter(Boolean))
    return {
      schedules: list.length,
      subjects: subjects.size,
      days: days.size,
      rooms: rooms.size,
    }
  }, [facultySchedules])

  const [editOpen, setEditOpen] = useState(false)
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [reactivateOpen, setReactivateOpen] = useState(false)
  const [deregisterOpen, setDeregisterOpen] = useState(false)

  const deactivateMutation = useDeactivateUser()
  const reactivateMutation = useReactivateUser()
  const deregisterMutation = useDeregisterFace()
  const actionLoading =
    deactivateMutation.isPending ||
    reactivateMutation.isPending ||
    deregisterMutation.isPending

  const handleDeactivate = async () => {
    if (!user) return
    try {
      await deactivateMutation.mutateAsync(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been deactivated.`)
    } catch {
      toast.error('Failed to deactivate user.')
    } finally {
      setDeactivateOpen(false)
    }
  }

  const handleReactivate = async () => {
    if (!user) return
    try {
      await reactivateMutation.mutateAsync(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been reactivated.`)
    } catch {
      toast.error('Failed to reactivate user.')
    } finally {
      setReactivateOpen(false)
    }
  }

  const handleDeregister = async () => {
    if (!user) return
    try {
      await deregisterMutation.mutateAsync(user.id)
      toast.success(`Face data for ${user.first_name} ${user.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    } finally {
      setDeregisterOpen(false)
    }
  }

  const attendanceColumns: ColumnDef<AttendanceRecord>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => (
        <span className="text-sm">{safeFormat(row.original.date, 'MMM d, yyyy')}</span>
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
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const backRoute = roleBackRoutes[user?.role ?? stateRole ?? 'student'] ?? roleBackRoutes.student

  if (!user) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate(backRoute.path)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {backRoute.label}
        </Button>
        <p className="text-muted-foreground">User not found.</p>
      </div>
    )
  }

  const initials = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase()
  const roleLabel = user.role.charAt(0).toUpperCase() + user.role.slice(1)

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate(backRoute.path)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {backRoute.label}
      </Button>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-4">
              <Avatar className="h-16 w-16 text-lg">
                <AvatarFallback className="text-lg">{initials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 space-y-2">
                <CardTitle className="text-xl leading-tight">
                  {user.first_name} {user.last_name}
                </CardTitle>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className={roleChipClass[user.role]}>
                    {roleLabel}
                  </Badge>
                  {user.is_active ? (
                    <Badge
                      variant="outline"
                      className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                    >
                      Active
                    </Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-muted-foreground/30 text-muted-foreground"
                    >
                      Inactive
                    </Badge>
                  )}
                  {user.email_verified ? (
                    <Badge
                      variant="outline"
                      className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                    >
                      Email verified
                    </Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                    >
                      Email not verified
                    </Badge>
                  )}
                  {user.role === 'student' && user.student_id && (
                    <span className="rounded-md border bg-muted/40 px-2 py-0.5 font-mono text-xs text-foreground">
                      {user.student_id}
                    </span>
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
                  {user.role === 'admin' && (
                    <>
                      <DropdownMenuItem
                        onClick={() => navigate(`/activity?actor_id=${user.id}`)}
                      >
                        <ExternalLink className="mr-2 h-4 w-4" />
                        View activity log
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(user.id)
                            toast.success('Account ID copied to clipboard')
                          } catch {
                            toast.error('Could not copy to clipboard')
                          }
                        }}
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Copy account ID
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  {user.role === 'student' && (
                    <>
                      <DropdownMenuItem onClick={() => setDeregisterOpen(true)}>
                        <ScanFace className="mr-2 h-4 w-4" />
                        Reset face registration
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  {user.is_active ? (
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeactivateOpen(true)}
                    >
                      <UserX className="mr-2 h-4 w-4" />
                      Deactivate {roleLabel.toLowerCase()}
                    </DropdownMenuItem>
                  ) : (
                    <DropdownMenuItem onClick={() => setReactivateOpen(true)}>
                      <UserCheck className="mr-2 h-4 w-4" />
                      Reactivate {roleLabel.toLowerCase()}
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* ── Admin activity (admin only) ─────────────────────────────── */}
      {user.role === 'admin' && (
        <AdminActivitySection
          adminId={user.id}
          navigateToActivity={() => navigate(`/activity?actor_id=${user.id}`)}
        />
      )}

      {/* ── Teaching summary (faculty only) ─────────────────────────── */}
      {user.role === 'faculty' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Teaching summary</CardTitle>
            <p className="text-xs text-muted-foreground">
              Aggregated across {teachingStats.schedules}{' '}
              {teachingStats.schedules === 1 ? 'schedule' : 'schedules'} assigned to
              this faculty.
            </p>
          </CardHeader>
          <CardContent>
            {schedulesLoading ? (
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-[88px] w-full" />
                ))}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
                <OverviewStat label="Schedules" value={teachingStats.schedules} />
                <OverviewStat
                  label="Subjects"
                  value={teachingStats.subjects}
                  hint={teachingStats.subjects === 1 ? 'Distinct course' : 'Distinct courses'}
                />
                <OverviewStat
                  label="Days active"
                  value={teachingStats.days}
                  hint={`${teachingStats.days} of 7 days/week`}
                />
                <OverviewStat
                  label="Rooms"
                  value={teachingStats.rooms}
                  hint={teachingStats.rooms === 1 ? 'Distinct room' : 'Distinct rooms'}
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Profile / Meta ───────────────────────────────────────────── */}
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
                user.email ? (
                  <a
                    href={`mailto:${user.email}`}
                    className="text-foreground underline-offset-4 hover:underline"
                  >
                    {user.email}
                  </a>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )
              }
            />
            <MetaItem
              label="Phone"
              value={
                user.phone ? (
                  <a
                    href={`tel:${user.phone}`}
                    className="text-foreground underline-offset-4 hover:underline"
                  >
                    {user.phone}
                  </a>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )
              }
            />
            {user.role === 'student' && user.student_id && (
              <MetaItem label="Student ID" value={<span className="font-mono">{user.student_id}</span>} />
            )}
            <MetaItem
              label={user.role === 'faculty' ? 'Joined faculty' : 'Joined'}
              value={safeFormat(user.created_at, 'MMM d, yyyy')}
            />
            <MetaItem label="Account ID" value={<AccountIdField id={user.id} />} />
          </div>
        </CardContent>
      </Card>

      {/* ── Handled Schedules (faculty) ──────────────────────────────── */}
      {user.role === 'faculty' && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BookOpen className="h-4 w-4 text-muted-foreground" />
                  Handled Schedules
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {scheduleScope === 'current' && currentTerm
                    ? `Showing ${sortedSchedules.length} for ${currentTerm.semester} · ${currentTerm.academic_year}`
                    : `Showing all ${facultySchedules.length} schedules`}
                </p>
              </div>
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
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {schedulesLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : sortedSchedules.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                {facultySchedules.length === 0 ? (
                  'No schedules assigned to this faculty.'
                ) : (
                  <>
                    No schedules in the current term.
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
                    <TableHead>Day</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>Room</TableHead>
                    <TableHead className="w-12 text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedSchedules.map((s) => (
                    <TableRow
                      key={s.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/schedules/${s.id}`)}
                    >
                      <TableCell className="font-mono text-xs">{s.subject_code}</TableCell>
                      <TableCell className="font-medium">{s.subject_name}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {DAY_NAMES_SHORT[s.day_of_week]}
                      </TableCell>
                      <TableCell className="text-muted-foreground tabular-nums">
                        {s.start_time?.slice(0, 5)} – {s.end_time?.slice(0, 5)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {s.room?.name ?? '—'}
                      </TableCell>
                      <TableCell className="text-right">
                        {s.is_active ? (
                          <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full border border-muted-foreground/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            Inactive
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Attendance History (student) ─────────────────────────────── */}
      {user.role === 'student' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Attendance History</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">
              For richer per-student tooling open the Student record page.
            </p>
          </CardHeader>
          <CardContent>
            <DataTable
              columns={attendanceColumns}
              data={filteredAttendance}
              isLoading={attendanceLoading}
              searchPlaceholder="Search by subject, status, date, score..."
              globalFilter={attendanceSearch}
              onGlobalFilterChange={(v) =>
                startAttendanceSearchTransition(() => setAttendanceSearch(v))
              }
              globalFilterFn={() => true}
              borderless
            />
          </CardContent>
        </Card>
      )}

      {/* ── Confirmation dialogs ─────────────────────────────────────── */}
      <AlertDialog open={deactivateOpen} onOpenChange={setDeactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate {roleLabel.toLowerCase()}?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate {user.first_name} {user.last_name}?
              They will no longer be able to access the system. Existing records are
              preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault()
                void handleDeactivate()
              }}
              disabled={actionLoading}
            >
              {actionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deactivating…
                </>
              ) : (
                'Deactivate'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={reactivateOpen} onOpenChange={setReactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reactivate {roleLabel.toLowerCase()}?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to reactivate {user.first_name} {user.last_name}?
              They will regain access to the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleReactivate()
              }}
              disabled={actionLoading}
            >
              {actionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Reactivating…
                </>
              ) : (
                'Reactivate'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deregisterOpen} onOpenChange={setDeregisterOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset face registration?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{user.first_name} {user.last_name}</strong> will need to
              re-register their face from the student app before they can be
              recognised again. Existing attendance records are preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault()
                void handleDeregister()
              }}
              disabled={actionLoading}
            >
              {actionLoading ? (
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

      <EditUserDialog user={user} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  )
}

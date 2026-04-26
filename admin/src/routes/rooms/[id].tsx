import { useState, useEffect, useMemo, useTransition } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  ArrowLeft,
  Check,
  Copy,
  Loader2,
  MoreVertical,
  Pencil,
  Play,
  Trash2,
  Video,
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
  useRoom,
  useSchedules,
  useUpdateRoom,
  useDeleteRoom,
} from '@/hooks/use-queries'
import type { ScheduleResponse, ScheduleRuntimeStatus } from '@/types'
import { tokenMatches, joinHaystack, formatTime12h, DAY_NAMES_MON_FIRST } from '@/lib/search'

function buildScheduleHaystackForRoom(s: ScheduleResponse): string {
  return joinHaystack([
    s.subject_code,
    s.subject_name,
    s.faculty ? `${s.faculty.first_name} ${s.faculty.last_name}` : 'Unassigned',
    s.faculty?.first_name,
    s.faculty?.last_name,
    s.faculty_name,
    DAY_NAMES_MON_FIRST[s.day_of_week],
    s.start_time,
    s.end_time,
    formatTime12h(s.start_time),
    formatTime12h(s.end_time),
    `${formatTime12h(s.start_time)} - ${formatTime12h(s.end_time)}`,
    s.is_active ? 'Active' : 'Inactive',
    s.runtime_status,
    s.semester,
    s.academic_year,
    s.target_course,
    s.target_year_level != null ? `Year ${s.target_year_level}` : null,
  ])
}

const DAY_NAMES_FULL = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const DAY_FILTER_OPTIONS: { value: number; label: string }[] = DAY_NAMES_FULL.map((label, i) => ({
  value: i,
  label: label.slice(0, 3),
}))

function formatTime(time: string): string {
  if (!time) return ''
  const [hours, minutes] = time.split(':')
  const h = parseInt(hours, 10)
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${String(h12)}:${minutes} ${ampm}`
}

const editFormSchema = z.object({
  name: z.string().min(1, 'Room name is required'),
  building: z.string().optional(),
  capacity: z.string().optional(),
  camera_endpoint: z.string().optional(),
})

type EditFormValues = z.infer<typeof editFormSchema>

// ---------------------------------------------------------------------------
// Local helpers — `OverviewStat`, `MetaItem`, `RuntimeStatusPill` mirror
// the components used on the schedule / faculty / student / admin redesigns
// for cross-page visual consistency.
// ---------------------------------------------------------------------------

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
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-foreground">
      <span className="relative flex h-1.5 w-1.5">
        {cfg.pulse && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full ${cfg.dot} opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      </span>
      {cfg.label}
    </span>
  )
}

/**
 * RTSP / HTTP URL display + click-to-copy. Same UX family as the
 * AccountIdField on the user-detail page — operators want the URL for
 * debugging but rarely want to retype it. The 1.5 s green check is
 * inline (no toast for read-only copy).
 */
function CopyableEndpoint({ value, ariaLabel }: { value: string; ariaLabel: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value)
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
      className="group inline-flex max-w-full items-center gap-1.5 rounded-md border bg-muted/40 px-2 py-1 font-mono text-xs text-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={ariaLabel}
      title="Copy to clipboard"
    >
      <span className="truncate">{value}</span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0 text-emerald-500" />
      ) : (
        <Copy className="h-3 w-3 shrink-0 text-muted-foreground transition group-hover:text-foreground" />
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------

export default function RoomDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: room, isLoading } = useRoom(id!)

  const roomName = room?.name ?? null
  usePageTitle(roomName ?? 'Room Details')

  useEffect(() => {
    if (roomName) setLabel(roomName)
    return () => setLabel(null)
  }, [roomName, setLabel])
  const { data: allSchedules = [] } = useSchedules()
  const updateRoom = useUpdateRoom()
  const deleteRoom = useDeleteRoom()

  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const form = useForm<EditFormValues>({
    resolver: zodResolver(editFormSchema),
    defaultValues: { name: '', building: '', capacity: '', camera_endpoint: '' },
  })

  useEffect(() => {
    if (room && editOpen) {
      form.reset({
        name: room.name,
        building: room.building ?? '',
        capacity: room.capacity != null ? String(room.capacity) : '',
        camera_endpoint: room.camera_endpoint ?? '',
      })
    }
  }, [room, editOpen, form])

  const roomSchedules = useMemo(
    () => allSchedules.filter((s: ScheduleResponse) => s.room_id === id),
    [allSchedules, id],
  )

  // Schedule-table filter state — day-of-week chips + faculty dropdown.
  // Both stack with the existing search box.
  const [dayFilter, setDayFilter] = useState<Set<number>>(new Set())
  const [facultyFilter, setFacultyFilter] = useState<string>('all')
  const [scheduleSearch, setScheduleSearch] = useState('')
  const [, startScheduleSearchTransition] = useTransition()

  // Distinct faculty list for the dropdown — sorted by full name. Built
  // from the room's schedules so we never offer a faculty option that
  // would yield zero rows.
  const facultyOptions = useMemo(() => {
    const map = new Map<string, string>()
    for (const s of roomSchedules) {
      if (s.faculty) {
        const id = s.faculty.id
        const name = `${s.faculty.first_name} ${s.faculty.last_name}`
        if (!map.has(id)) map.set(id, name)
      }
    }
    return Array.from(map.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [roomSchedules])

  const filteredRoomSchedules = useMemo(() => {
    let pool = roomSchedules
    if (dayFilter.size > 0) {
      pool = pool.filter((s) => dayFilter.has(s.day_of_week))
    }
    if (facultyFilter !== 'all') {
      pool = pool.filter((s) => s.faculty?.id === facultyFilter)
    }
    if (!scheduleSearch.trim()) return pool
    return pool.filter((s) =>
      tokenMatches(buildScheduleHaystackForRoom(s), scheduleSearch),
    )
  }, [roomSchedules, scheduleSearch, dayFilter, facultyFilter])

  function toggleDayFilter(day: number) {
    setDayFilter((prev) => {
      const next = new Set(prev)
      if (next.has(day)) next.delete(day)
      else next.add(day)
      return next
    })
  }

  // ── Utilization aggregates — pure client-side derivations ──
  const utilization = useMemo(() => {
    const subjects = new Set(roomSchedules.map((s) => s.subject_code))
    const days = new Set(roomSchedules.map((s) => s.day_of_week))
    const facultyIds = new Set(
      roomSchedules.map((s) => s.faculty?.id).filter(Boolean) as string[],
    )
    return {
      schedules: roomSchedules.length,
      faculty: facultyIds.size,
      subjects: subjects.size,
      days: days.size,
    }
  }, [roomSchedules])

  // ── Live-now detection — first schedule in this room currently running.
  // Used both for the LIVE pill in the header and the "Open live session"
  // dropdown item.
  const liveSchedule = useMemo(
    () => roomSchedules.find((s) => s.runtime_status === 'live'),
    [roomSchedules],
  )

  const onSubmit = async (values: EditFormValues) => {
    if (!room) return
    try {
      await updateRoom.mutateAsync({
        id: room.id,
        data: {
          name: values.name,
          building: values.building || undefined,
          capacity: values.capacity ? Number(values.capacity) : undefined,
          camera_endpoint: values.camera_endpoint || undefined,
        },
      })
      toast.success(`Room "${values.name}" has been updated.`)
      setEditOpen(false)
    } catch {
      toast.error('Failed to update room.')
    }
  }

  const handleDelete = async () => {
    if (!room) return
    try {
      await deleteRoom.mutateAsync(room.id)
      toast.success(`Room "${room.name}" has been deactivated.`)
      navigate('/rooms')
    } catch {
      toast.error('Failed to delete room.')
    }
  }

  const scheduleColumns: ColumnDef<ScheduleResponse>[] = [
    {
      accessorKey: 'subject_name',
      header: 'Subject',
      cell: ({ row }) => (
        <div>
          <div className="font-mono text-xs text-muted-foreground">
            {row.original.subject_code}
          </div>
          <div className="text-sm font-medium">{row.original.subject_name}</div>
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
            : <span className="text-muted-foreground">Unassigned</span>}
        </span>
      ),
    },
    {
      accessorKey: 'day_of_week',
      header: 'Day',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {DAY_NAMES_FULL[row.original.day_of_week]}
        </span>
      ),
    },
    {
      id: 'time',
      header: 'Time',
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-sm tabular-nums text-muted-foreground">
          {formatTime(row.original.start_time)} – {formatTime(row.original.end_time)}
        </span>
      ),
    },
    {
      accessorKey: 'runtime_status',
      header: 'Runtime',
      cell: ({ row }) => (
        <RuntimeStatusPill
          status={(row.original.runtime_status as ScheduleRuntimeStatus) ?? 'scheduled'}
        />
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

  if (!room) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/rooms')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Rooms
        </Button>
        <p className="text-muted-foreground">Room not found.</p>
      </div>
    )
  }

  // Stream key is sometimes derivable from camera_endpoint when the
  // backend hasn't populated it yet. Pattern: rtsp://host:port/{key}
  const derivedStreamKey =
    room.stream_key ??
    (room.camera_endpoint
      ? room.camera_endpoint.match(/\/([^/]+)(?:\?.*)?$/)?.[1] ?? null
      : null)

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/rooms')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Rooms
      </Button>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-2">
              <CardTitle className="text-xl leading-tight">{room.name}</CardTitle>
              {(room.building || room.capacity != null) && (
                <p className="text-sm text-muted-foreground">
                  {room.building ?? 'Unknown building'}
                  {room.capacity != null && (
                    <>
                      <span className="text-muted-foreground/60"> · </span>
                      {room.capacity} seats
                    </>
                  )}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-2">
                {room.is_active ? (
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
                {liveSchedule && (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    </span>
                    Live now
                  </span>
                )}
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
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem
                    disabled={!liveSchedule}
                    onClick={() =>
                      liveSchedule && navigate(`/schedules/${liveSchedule.id}/live`)
                    }
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Open live session
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    disabled={!room.camera_endpoint}
                    onClick={async () => {
                      if (!room.camera_endpoint) return
                      try {
                        await navigator.clipboard.writeText(room.camera_endpoint)
                        toast.success('Camera endpoint copied to clipboard')
                      } catch {
                        toast.error('Could not copy to clipboard')
                      }
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Copy camera endpoint
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    disabled={!room.is_active}
                    onClick={() => setDeleteOpen(true)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete room
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* ── Utilization summary ─────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Room utilization</CardTitle>
          <p className="text-xs text-muted-foreground">
            Aggregated across {utilization.schedules}{' '}
            {utilization.schedules === 1 ? 'schedule' : 'schedules'} assigned to this
            room.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            <OverviewStat label="Schedules" value={utilization.schedules} />
            <OverviewStat
              label="Faculty"
              value={utilization.faculty}
              hint={utilization.faculty === 1 ? 'Distinct instructor' : 'Distinct instructors'}
            />
            <OverviewStat
              label="Subjects"
              value={utilization.subjects}
              hint={utilization.subjects === 1 ? 'Distinct course' : 'Distinct courses'}
            />
            <OverviewStat
              label="Days in use"
              value={utilization.days}
              hint={`${utilization.days} of 7 days/week`}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Profile (building + capacity + camera) ────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Profile</CardTitle>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetaItem
              label="Building"
              value={room.building ?? <span className="text-muted-foreground">—</span>}
            />
            <MetaItem
              label="Capacity"
              value={
                room.capacity != null ? (
                  <span>
                    {room.capacity}{' '}
                    <span className="text-xs font-normal text-muted-foreground">seats</span>
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )
              }
            />
            <MetaItem
              label="Stream key"
              value={
                derivedStreamKey ? (
                  <span className="font-mono text-xs">{derivedStreamKey}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )
              }
            />
            <div className="space-y-0.5 sm:col-span-2 lg:col-span-3">
              <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Camera endpoint
              </div>
              <div>
                {room.camera_endpoint ? (
                  <CopyableEndpoint
                    value={room.camera_endpoint}
                    ariaLabel="Copy camera endpoint"
                  />
                ) : (
                  <span className="text-sm text-muted-foreground">Not configured</span>
                )}
              </div>
              <p className="pt-1 text-[11px] text-muted-foreground">
                The RTSP/HTTP URL the room's camera streams to. Used by the always-on
                FrameGrabber and the WHEP relay; edit via the Edit button above.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Schedules in this Room ──────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Video className="h-4 w-4 text-muted-foreground" />
                Schedules in this Room
              </CardTitle>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {filteredRoomSchedules.length === roomSchedules.length
                  ? `Showing all ${roomSchedules.length} schedules`
                  : `Showing ${filteredRoomSchedules.length} of ${roomSchedules.length} schedules`}
              </p>
            </div>
            {facultyOptions.length > 0 && (
              <Select
                value={facultyFilter}
                onValueChange={(v) => setFacultyFilter(v)}
              >
                <SelectTrigger size="sm" className="h-8 w-56 text-xs">
                  <SelectValue placeholder="All faculty" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All faculty</SelectItem>
                  {facultyOptions.map((f) => (
                    <SelectItem key={f.id} value={f.id}>
                      {f.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Day-of-week filter chips */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Day
            </span>
            {DAY_FILTER_OPTIONS.map((opt) => {
              const active = dayFilter.has(opt.value)
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggleDayFilter(opt.value)}
                  className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition ${
                    active
                      ? 'border-foreground bg-foreground text-background'
                      : 'border-border text-muted-foreground hover:bg-muted/60'
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
            {(dayFilter.size > 0 || facultyFilter !== 'all') && (
              <button
                type="button"
                onClick={() => {
                  setDayFilter(new Set())
                  setFacultyFilter('all')
                }}
                className="ml-1 text-[11px] font-medium text-muted-foreground underline-offset-4 hover:underline"
              >
                Clear filters
              </button>
            )}
          </div>

          <DataTable
            columns={scheduleColumns}
            data={filteredRoomSchedules}
            searchPlaceholder="Search by subject, faculty, day, time, status..."
            globalFilter={scheduleSearch}
            onGlobalFilterChange={(v) =>
              startScheduleSearchTransition(() => setScheduleSearch(v))
            }
            globalFilterFn={() => true}
            onRowClick={(row) => navigate(`/schedules/${row.id}`)}
          />
        </CardContent>
      </Card>

      {/* ── Delete confirmation ─────────────────────────────────────── */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete room?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{room.name}</strong> will be deactivated. Existing schedules
              that point at this room will keep their assignment but the room will
              no longer appear in active lists. Attendance records and history are
              preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteRoom.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault()
                void handleDelete()
              }}
              disabled={deleteRoom.isPending}
            >
              {deleteRoom.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : (
                'Delete room'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── Edit dialog ─────────────────────────────────────────────── */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Room</DialogTitle>
            <DialogDescription>Update the room details below.</DialogDescription>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name *</Label>
              <Input id="name" placeholder="e.g. Room 101" {...form.register('name')} />
              {form.formState.errors.name && (
                <p className="text-sm text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="building">Building</Label>
              <Input id="building" placeholder="e.g. Main Building" {...form.register('building')} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="capacity">Capacity</Label>
              <Input id="capacity" type="number" placeholder="e.g. 40" {...form.register('capacity')} />
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
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={updateRoom.isPending}>
                {updateRoom.isPending ? (
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

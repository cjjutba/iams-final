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
  PlayCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
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
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useSchedules, useCreateSchedule, useUpdateSchedule, useDeleteSchedule, useUsers, useRooms } from '@/hooks/use-queries'
import type { ScheduleResponse, ScheduleRuntimeStatus } from '@/types'
import { tokenMatches, joinHaystack, formatTime12h, DAY_NAMES_MON_FIRST } from '@/lib/search'
import { RuntimeStatusPill } from '@/components/shared/status-pills'

// Runtime status labels — kept here only for the search haystack so
// operators can type "live" / "upcoming" / "ended" and have it match. The
// rendered pill comes from the shared `RuntimeStatusPill` component.
const RUNTIME_STATUS_LABEL: Record<ScheduleRuntimeStatus, string> = {
  live: 'Live',
  upcoming: 'Upcoming',
  ended: 'Ended today',
  scheduled: 'Scheduled',
  disabled: 'Disabled',
}

// Indexed Monday-first to match the backend's `day_of_week` convention
// (0=Mon..6=Sun — see backend/scripts/seed_data.py). Do not reorder without
// also fixing the todayIdx remap below and the Day column in the table.
const DAY_NAMES = DAY_NAMES_MON_FIRST

type StatusFilter = 'all' | 'active' | 'inactive'
type DayFilter = 'all' | '0' | '1' | '2' | '3' | '4' | '5' | '6'

// ---------------------------------------------------------------------------
// Filter persistence (per-tab session)
//
// "Back to Schedules" on the detail page is a hard navigate('/schedules'),
// not navigate(-1), so router-history alone won't keep the user's day
// selection. We mirror filters into sessionStorage on every change and
// hydrate them on mount — fresh tab still defaults to today + active.
// ---------------------------------------------------------------------------

const STORAGE_PREFIX = 'iams.schedules.filter.'

function isStatusFilter(v: string): v is StatusFilter {
  return v === 'all' || v === 'active' || v === 'inactive'
}

function isDayFilter(v: string): v is DayFilter {
  return (
    v === 'all' ||
    v === '0' ||
    v === '1' ||
    v === '2' ||
    v === '3' ||
    v === '4' ||
    v === '5' ||
    v === '6'
  )
}

function readStoredFilter<T extends string>(
  key: string,
  guard: (v: string) => v is T,
  fallback: T,
): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.sessionStorage.getItem(STORAGE_PREFIX + key)
    if (raw && guard(raw)) return raw
  } catch {
    // SessionStorage can throw in private mode / iframe sandboxes —
    // fall through to the default.
  }
  return fallback
}

function readStoredString(key: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.sessionStorage.getItem(STORAGE_PREFIX + key)
    if (raw !== null) return raw
  } catch {
    // ignore
  }
  return fallback
}

function writeStoredFilter(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem(STORAGE_PREFIX + key, value)
  } catch {
    // Quota exceeded / disabled storage — silently degrade. The page
    // still works; the filter just won't survive navigation.
  }
}

function writeStoredString(key: string, value: string): void {
  writeStoredFilter(key, value)
}

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

const scheduleFormSchema = z
  .object({
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
  // String compare on "HH:MM" 24-hour values is correctness-equivalent to
  // numeric compare and avoids round-tripping through Date (which would
  // implicitly involve the browser timezone — see PHT note in the form).
  .refine((v) => !v.start_time || !v.end_time || v.start_time < v.end_time, {
    message: 'End time must be after start time',
    path: ['end_time'],
  })

function formatTime(time: string): string {
  return formatTime12h(time)
}

function buildScheduleHaystack(s: ScheduleResponse): string {
  return joinHaystack([
    s.subject_code,
    s.subject_name,
    s.faculty ? `${s.faculty.first_name} ${s.faculty.last_name}` : 'Unassigned',
    s.faculty?.first_name,
    s.faculty?.last_name,
    s.faculty_name,
    s.room?.name ?? 'Unassigned',
    s.room?.building,
    s.room_name,
    DAY_NAMES[s.day_of_week],
    // Match both 24h "HH:MM" and 12h "7:30 AM" so either typing style hits.
    s.start_time,
    s.end_time,
    formatTime12h(s.start_time),
    formatTime12h(s.end_time),
    `${formatTime12h(s.start_time)} - ${formatTime12h(s.end_time)}`,
    // is_active still in the haystack so the legacy "Active"/"Inactive"
    // search vocabulary keeps working. The runtime_status label is added
    // alongside so operators can also search "live", "upcoming", etc.
    s.is_active ? 'Active' : 'Inactive',
    RUNTIME_STATUS_LABEL[s.runtime_status],
    s.semester,
    s.academic_year,
    s.target_course,
    s.target_year_level != null ? `Year ${s.target_year_level}` : null,
  ])
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
        <DropdownMenuItem onClick={() => navigate(`/schedules/${schedule.id}/live`)}>
          <PlayCircle className="mr-2 h-4 w-4" />
          Watch Live
        </DropdownMenuItem>
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

  // JS Date.getDay() returns 0=Sunday..6=Saturday. Our DAY_NAMES constant
  // lives at index 0=Monday..6=Sunday, so remap: Sun(0) -> 6, Mon..Sat -> n-1.
  const todayIdx = useMemo(() => {
    const jsDay = new Date().getDay()
    return jsDay === 0 ? 6 : jsDay - 1
  }, [])

  // Persist filter selections per browser tab so navigating into a
  // schedule's detail page and clicking "Back to Schedules" (which is a
  // hard navigate('/schedules'), NOT navigate(-1)) doesn't snap the day
  // back to today. Stored in sessionStorage so a fresh tab still opens
  // on today, which is what the page is best at showing.
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    () => readStoredFilter('status', isStatusFilter, 'all'),
  )
  // Default to TODAY + active so the page opens on what matters most —
  // "classes happening today, earliest to latest." User can flip to
  // "All Days" or "All Status" if they want the full list.
  const [dayFilter, setDayFilter] = useState<DayFilter>(
    () => readStoredFilter('day', isDayFilter, String(todayIdx) as DayFilter),
  )
  const [searchQuery, setSearchQuery] = useState<string>(
    () => readStoredString('q', ''),
  )
  const [isPending, startTransition] = useTransition()

  // Persist on change. Wrapping the original setter keeps the type
  // signature identical so the existing handleFilterChange / clearFilters
  // helpers work without modification.
  const persistedSetStatusFilter = (v: StatusFilter) => {
    writeStoredFilter('status', v)
    setStatusFilter(v)
  }
  const persistedSetDayFilter = (v: DayFilter) => {
    writeStoredFilter('day', v)
    setDayFilter(v)
  }
  const persistedSetSearchQuery = (v: string) => {
    writeStoredString('q', v)
    setSearchQuery(v)
  }

  const filtered = useMemo(() => {
    let result = schedules
    if (statusFilter === 'active') result = result.filter((s) => s.is_active)
    else if (statusFilter === 'inactive') result = result.filter((s) => !s.is_active)

    if (dayFilter !== 'all') result = result.filter((s) => s.day_of_week === parseInt(dayFilter, 10))

    // Multi-field search: matches against subject code/name, faculty,
    // room, day name, formatted time, status, semester, academic year,
    // and target course/year. See buildScheduleHaystack().
    if (searchQuery.trim()) {
      result = result.filter((s) => tokenMatches(buildScheduleHaystack(s), searchQuery))
    }

    // Sort morning -> evening: by (day_of_week, start_time). When viewing
    // "All Days" this groups days together; when filtered to one day this
    // is just chronological order.
    result = [...result].sort((a, b) => {
      if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week
      return (a.start_time ?? '').localeCompare(b.start_time ?? '')
    })

    return result
  }, [schedules, statusFilter, dayFilter, searchQuery])

  // "Anything other than fully unfiltered counts as filtered." Today-first
  // is still the fresh-mount default (useState initialiser above), but it's
  // a *filter* in the user's mental model — the page literally hides ~88
  // rows when it's set. So the Clear button shows by default and drops the
  // user into the wide-open list; today is one click away in the day picker.
  const hasFilters =
    statusFilter !== 'all' ||
    dayFilter !== 'all' ||
    searchQuery.trim().length > 0

  // Human-readable description of the active filters, rendered under the
  // count heading so a user landing on the page immediately knows what's
  // narrowing the visible rows. Empty string when fully unfiltered.
  const filterDescription = useMemo(() => {
    const parts: string[] = []
    if (dayFilter !== 'all') {
      parts.push(DAY_NAMES[parseInt(dayFilter, 10)])
    }
    if (statusFilter !== 'all') {
      parts.push(statusFilter === 'active' ? 'Enabled only' : 'Disabled only')
    }
    const q = searchQuery.trim()
    if (q) {
      parts.push(`matching "${q}"`)
    }
    return parts.join(' · ')
  }, [dayFilter, statusFilter, searchQuery])

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    // "Clear" means clear — wide-open list (all days + all status + no
    // search). Today is reachable from the day picker if the user wants
    // it back. Previous behaviour ("clear" → today) confused operators
    // who expected the label to do what it says. Persisted setters keep
    // sessionStorage in lockstep so this also resets what we hydrate
    // next mount.
    startTransition(() => {
      persistedSetStatusFilter('all')
      persistedSetDayFilter('all')
      persistedSetSearchQuery('')
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
      accessorKey: 'runtime_status',
      header: 'Status',
      // Sort by runtime priority instead of alphabetical so clicking the
      // header surfaces "what's running now" first. Order: live → upcoming
      // → ended → scheduled → disabled. Reverse sort flips it.
      sortingFn: (a, b) => {
        const order: Record<ScheduleRuntimeStatus, number> = {
          live: 0,
          upcoming: 1,
          ended: 2,
          scheduled: 3,
          disabled: 4,
        }
        return order[a.original.runtime_status] - order[b.original.runtime_status]
      },
      cell: ({ row }) => (
        <RuntimeStatusPill
          status={
            (row.original.runtime_status as ScheduleRuntimeStatus) ?? 'scheduled'
          }
        />
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

  if (isLoading) {
    // Mirror the loaded layout (header + toolbar + table + pagination) so
    // the cut-over to real data doesn't shift the page. Each skeleton
    // block is sized to match its eventual counterpart's width, height,
    // and rhythm. Used only on first fetch — `isPending` (filter
    // transitions) keeps the toolbar interactive and shows the
    // DataTable's own row-level skeleton instead.
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-9 w-40 rounded-md" />
        </div>

        <div>
          {/* Toolbar */}
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[140px] rounded-md" />
              <Skeleton className="h-9 w-[130px] rounded-md" />
            </div>
          </div>

          {/* Table — render real header so column proportions match. */}
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject</TableHead>
                  <TableHead>Faculty</TableHead>
                  <TableHead>Room</TableHead>
                  <TableHead>Day</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`schedules-skel-${String(i)}`}>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-4 w-28" />
                        <Skeleton className="h-3 w-48" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-20" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-6 w-24 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="ml-auto h-8 w-8 rounded-md" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-2 py-4">
            <Skeleton className="h-4 w-44" />
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-[70px] rounded-md" />
              </div>
              <div className="flex items-center gap-1">
                <Skeleton className="h-8 w-8 rounded-md" />
                <Skeleton className="h-8 w-8 rounded-md" />
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Schedule Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {hasFilters
              ? `${filtered.length} of ${schedules.length} schedules`
              : `${schedules.length} schedule${schedules.length !== 1 ? 's' : ''}`}
          </p>
          {filterDescription && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Showing {filterDescription}
            </p>
          )}
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
        // Multi-field search lives in this component (filtered useMemo
        // above). The DataTable's globalFilter wiring is purely for the
        // input's controlled state; the noop globalFilterFn ensures
        // TanStack does not re-filter the rows we already pre-filtered.
        globalFilter={searchQuery}
        onGlobalFilterChange={persistedSetSearchQuery}
        globalFilterFn={() => true}
        searchPlaceholder="Search by subject, faculty, room, day, time, status..."
        toolbar={
          <>
            <Select value={dayFilter} onValueChange={handleFilterChange(persistedSetDayFilter)}>
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

            <Select value={statusFilter} onValueChange={handleFilterChange(persistedSetStatusFilter)}>
              <SelectTrigger className="w-[130px] h-9">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {/* Filter values map to `is_active` (enable/archive flag),
                    NOT the runtime_status badge in the table. The labels
                    were renamed from "Active/Inactive" to "Enabled/Disabled"
                    so they don't read as "currently running" — that
                    information lives in the Status column badge now. */}
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Enabled</SelectItem>
                <SelectItem value="inactive">Disabled</SelectItem>
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
                : 'Fill in the details to create a new schedule.'}{' '}
              Fields marked with <span className="text-destructive">*</span> are required.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            {/*
              Time handling note: the <input type="time"> elements below
              return literal "HH:MM" wall-clock strings (24-hour) with NO
              timezone conversion. The backend container runs in
              Asia/Manila (TZ env in deploy/docker-compose.onprem.yml) and
              persists start_time/end_time as bare `time` columns, so the
              value an admin types here IS the Philippine wall-clock time
              the session-lifecycle scheduler will compare against. Do not
              wrap these values in `new Date(...)` before submit — that
              would round-trip through UTC and corrupt the saved time.
            */}
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="subject_code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Subject Code <span className="text-destructive">*</span>
                      </FormLabel>
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
                      <FormLabel>
                        Subject Name <span className="text-destructive">*</span>
                      </FormLabel>
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
                      <FormLabel>
                        Faculty <span className="text-destructive">*</span>
                      </FormLabel>
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
                      <FormLabel>
                        Room <span className="text-destructive">*</span>
                      </FormLabel>
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

              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Times are entered in <span className="font-medium">Philippine Time (PHT, UTC+8)</span>.
                  The value you type is saved exactly — no timezone conversion is applied.
                </p>
                <div className="grid gap-4 sm:grid-cols-3">
                  <FormField
                    control={form.control}
                    name="day_of_week"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          Day <span className="text-destructive">*</span>
                        </FormLabel>
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
                        <FormLabel>
                          Start Time <span className="text-destructive">*</span>
                        </FormLabel>
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
                        <FormLabel>
                          End Time <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input type="time" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="semester"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Semester <span className="text-destructive">*</span>
                      </FormLabel>
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
                      <FormLabel>
                        Academic Year <span className="text-destructive">*</span>
                      </FormLabel>
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

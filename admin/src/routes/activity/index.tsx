import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { formatTimestamp, formatFullDatetime } from '@/lib/format-time'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BookmarkMinus,
  BookmarkPlus,
  CalendarCog,
  CalendarPlus,
  CalendarX,
  Camera,
  CameraOff,
  CheckCircle2,
  Download,
  FileJson,
  LogIn,
  LogOut,
  Pause,
  Play,
  PlayCircle,
  Replace,
  ScanFace,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  StopCircle,
  UserCheck,
  UserCog,
  UserMinus,
  UserPlus,
  Wifi,
  WifiOff,
  X,
  XCircle,
  type LucideIcon,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useActivityEvents } from '@/hooks/use-queries'
import { useActivityWs } from '@/hooks/use-activity-ws'
import { usePageTitle } from '@/hooks/use-page-title'
import { cn } from '@/lib/utils'
import { formatEventSummary } from '@/lib/activity-format'
import { activityService } from '@/services/activity.service'
import type {
  ActivityCategory,
  ActivityEvent,
  ActivityListFilters,
  ActivitySeverity,
} from '@/types'

import { EventDetailSheet } from './event-detail-sheet'

// Keep at most this many events in the live stream list. Older events are
// dropped; they remain accessible via the CSV/JSON export which hits the
// DB directly, not the in-memory buffer.
const MAX_BUFFER = 5000
// Display at most this many rows; the rest are still in the buffer for
// "N buffered events" affordance.
const MAX_VISIBLE = 500

const CATEGORIES: ActivityCategory[] = [
  'attendance',
  'session',
  'recognition',
  'system',
  'audit',
]
const SEVERITIES: ActivitySeverity[] = ['info', 'success', 'warn', 'error']

// Severity-first color vocabulary.
// ─────────────────────────────────
// Severity drives BOTH the icon stroke and the event-type chip so the
// page reads as a health scan: emerald = good, neutral = background
// traffic, amber = look here, red = act now. Category lives only in the
// leading dot inside the chip — a quiet secondary signal for grouping
// without competing with severity for the eye.
//
// Why this trumps category-driven coloring: on a busy stream the most
// frequent rows are RECOGNITION_MISS (info) interleaved with
// RECOGNITION_MATCH (success). Coloring by category made both teal and
// indistinguishable on a fast scroll. Coloring by severity makes the
// match rows pop emerald against the neutral miss rows so "students
// being recognized" is visible from across the room.
const severityRailClass: Record<ActivitySeverity, string> = {
  info: 'bg-muted-foreground/25',
  success: 'bg-emerald-500',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
}

// Faint full-row wash on warn/error only. Info/success stay clean so the
// stream doesn't feel like a Christmas tree; the wash is reserved for
// "you should look at this" rows.
const severityTintClass: Record<ActivitySeverity, string> = {
  info: '',
  success: '',
  warn: 'bg-amber-50/50 dark:bg-amber-950/20',
  error: 'bg-red-50/60 dark:bg-red-950/25',
}

// Icon stroke color — mirrors the chip so the row reads as one gestalt.
const severityIconClass: Record<ActivitySeverity, string> = {
  info: 'text-muted-foreground',
  success: 'text-emerald-600 dark:text-emerald-400',
  warn: 'text-amber-600 dark:text-amber-400',
  error: 'text-red-600 dark:text-red-400',
}

// Event-type chip background + text. The chip is the most visible token
// on a row, so this is where the severity signal pays off most.
const severityChipClass: Record<ActivitySeverity, string> = {
  info: 'bg-muted/60 text-foreground/75 border-border',
  success:
    'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:border-emerald-900',
  warn: 'bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-900',
  error:
    'bg-red-50 text-red-900 border-red-200 dark:bg-red-950/40 dark:text-red-200 dark:border-red-900',
}

// Category dot — kept as a quiet secondary grouping signal inside the
// chip. The dot remains visible against any severity-tinted chip
// background because it's a saturated solid against a light tint.
const categoryDotClass: Record<ActivityCategory, string> = {
  attendance: 'bg-blue-500',
  session: 'bg-purple-500',
  recognition: 'bg-teal-500',
  system: 'bg-slate-500',
  audit: 'bg-indigo-500',
}

// Per-event-type icon. The category accent colors the stroke; the icon
// shape itself is the at-a-glance identity (UserCheck != ScanFace even
// though both are "recognition"). Anything not listed falls back to
// Activity so a new EventType added on the backend keeps rendering.
const eventTypeIcon: Record<string, LucideIcon> = {
  // attendance
  MARKED_PRESENT: CheckCircle2,
  MARKED_LATE: AlertCircle,
  MARKED_ABSENT: XCircle,
  EARLY_LEAVE_FLAGGED: LogOut,
  EARLY_LEAVE_RETURNED: LogIn,
  // session + pipeline lifecycle (same shapes; different category)
  SESSION_STARTED_AUTO: PlayCircle,
  SESSION_STARTED_MANUAL: PlayCircle,
  SESSION_ENDED_AUTO: StopCircle,
  SESSION_ENDED_MANUAL: StopCircle,
  PIPELINE_STARTED: PlayCircle,
  PIPELINE_STOPPED: StopCircle,
  PIPELINE_CAMERA_SWAPPED: Replace,
  // recognition
  RECOGNITION_MATCH: UserCheck,
  RECOGNITION_MISS: ScanFace,
  // system / camera health
  CAMERA_OFFLINE: CameraOff,
  CAMERA_ONLINE: Camera,
  // audit
  ADMIN_LOGIN: ShieldCheck,
  FACULTY_LOGIN: LogIn,
  STUDENT_LOGIN: LogIn,
  USER_CREATED: UserPlus,
  USER_UPDATED: UserCog,
  USER_DELETED: UserMinus,
  FACE_REGISTRATION_APPROVED: ShieldCheck,
  SETTINGS_CHANGED: SettingsIcon,
  SCHEDULE_CREATED: CalendarPlus,
  SCHEDULE_UPDATED: CalendarCog,
  SCHEDULE_DELETED: CalendarX,
  ENROLLMENT_ADDED: BookmarkPlus,
  ENROLLMENT_REMOVED: BookmarkMinus,
}

function isoMinutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

export default function ActivityPage() {
  usePageTitle('System Activity')

  const [searchParams, setSearchParams] = useSearchParams()

  // Filters parsed from URL — shareable, deep-linkable. Single-value to
  // mirror the dropdown UX of the Students/Faculty/Admins registries; if
  // a deep-link arrives with a comma list (legacy), we honor only the
  // first entry for the dropdown display while still passing the raw
  // string through to the REST/WS filters so the backend behaves
  // identically.
  const categoryFilter = (searchParams.get('category') ?? '').split(',')[0] as
    | ActivityCategory
    | ''
  const severityFilter = (searchParams.get('severity') ?? '').split(',')[0] as
    | ActivitySeverity
    | ''

  const scheduleFilter = searchParams.get('schedule_id') ?? ''
  const studentFilter = searchParams.get('student_id') ?? ''
  // `actor_id` is set when the operator deep-links from a user-detail page
  // (e.g. /users/:id "View activity log" item). It scopes the feed to
  // events that user authored. There's no UI control to set it from this
  // page — only the deep-link, plus a chip below that clears it.
  const actorFilter = searchParams.get('actor_id') ?? ''

  const [studentInput, setStudentInput] = useState(studentFilter)
  const [scheduleInput, setScheduleInput] = useState(scheduleFilter)

  // Live pause — when paused, WS events accumulate into a buffer instead of
  // merging into the visible list.
  const [paused, setPaused] = useState(false)
  const [bufferedCount, setBufferedCount] = useState(0)
  const bufferRef = useRef<ActivityEvent[]>([])

  // The visible event list — prepended as live events arrive.
  const [liveEvents, setLiveEvents] = useState<ActivityEvent[]>([])

  // Event detail side sheet.
  const [selectedEvent, setSelectedEvent] = useState<ActivityEvent | null>(null)

  // Build filters object for REST + WS.
  const restFilters: ActivityListFilters = useMemo(() => {
    const out: ActivityListFilters = {
      since: isoMinutesAgo(15),
      limit: 200,
    }
    if (categoryFilter) out.category = categoryFilter
    if (severityFilter) out.severity = severityFilter
    if (scheduleFilter) out.schedule_id = scheduleFilter
    if (studentFilter) out.student_id = studentFilter
    if (actorFilter) out.actor_id = actorFilter
    return out
  }, [categoryFilter, severityFilter, scheduleFilter, studentFilter, actorFilter])

  // Initial 15-min replay so the page isn't empty on mount.
  const { data: initialData, isLoading: isInitialLoading } = useActivityEvents(restFilters)

  // Seed the live list with the initial REST page exactly once per filter
  // change. The WS hook then prepends future events on top.
  useEffect(() => {
    if (initialData?.items) {
      setLiveEvents(initialData.items)
      bufferRef.current = []
      setBufferedCount(0)
    }
  }, [initialData])

  // Attach WS stream — filters are snapshotted at connect time; changing
  // them re-subscribes automatically.
  const { isConnected } = useActivityWs({
    enabled: true,
    filters: {
      category: restFilters.category,
      severity: restFilters.severity,
      schedule_id: restFilters.schedule_id,
      student_id: restFilters.student_id,
    },
    onEvent: useCallback(
      (ev: ActivityEvent) => {
        // Client-side actor filter: the WS hook subscribes by category /
        // severity / schedule / student but not actor_id, so when the URL
        // pins an actor we drop incoming events that don't match. Without
        // this, deep-linking to /activity?actor_id=X would mix that
        // admin's events with everyone else's as new ones streamed in.
        if (actorFilter && ev.actor_id !== actorFilter) return

        if (paused) {
          bufferRef.current = [ev, ...bufferRef.current].slice(0, MAX_BUFFER)
          setBufferedCount(bufferRef.current.length)
          return
        }
        setLiveEvents((prev) => {
          // Dedupe by event_id in case WS and REST racing delivers the
          // same row twice.
          if (prev.some((e) => e.event_id === ev.event_id)) return prev
          return [ev, ...prev].slice(0, MAX_BUFFER)
        })
      },
      [paused, actorFilter],
    ),
  })

  // Resume — flush buffer into the visible list.
  const resume = () => {
    setLiveEvents((prev) => {
      const merged = [...bufferRef.current, ...prev]
      // Dedupe by event_id, preserving order.
      const seen = new Set<string>()
      const out: ActivityEvent[] = []
      for (const e of merged) {
        if (seen.has(e.event_id)) continue
        seen.add(e.event_id)
        out.push(e)
      }
      return out.slice(0, MAX_BUFFER)
    })
    bufferRef.current = []
    setBufferedCount(0)
    setPaused(false)
  }

  // Select handlers — `'all'` is the sentinel value the dropdown emits
  // when the user clears the choice. We translate it to "drop the URL
  // param" so a clean URL means no filter, matching how the Students
  // registry reads its dropdown state.
  const setCategoryFilter = (value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value || value === 'all') next.delete('category')
    else next.set('category', value)
    setSearchParams(next)
  }

  const setSeverityFilter = (value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value || value === 'all') next.delete('severity')
    else next.set('severity', value)
    setSearchParams(next)
  }

  const applyTextFilters = () => {
    const next = new URLSearchParams(searchParams)
    if (studentInput.trim()) next.set('student_id', studentInput.trim())
    else next.delete('student_id')
    if (scheduleInput.trim()) next.set('schedule_id', scheduleInput.trim())
    else next.delete('schedule_id')
    setSearchParams(next)
  }

  const clearAllFilters = () => {
    setStudentInput('')
    setScheduleInput('')
    setSearchParams(new URLSearchParams())
  }

  // Targeted clear for the actor pin (deep-link from a user-detail page).
  // Operators usually want to drop just this and keep their other filters.
  const clearActorFilter = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('actor_id')
    setSearchParams(next)
  }

  const visibleEvents = liveEvents.slice(0, MAX_VISIBLE)
  const hiddenInBuffer = liveEvents.length - visibleEvents.length

  // Tally of warn/error in the visible window so the stream header can
  // surface them as a one-glance health indicator.
  const visibleSeverityCounts = useMemo(() => {
    let warn = 0
    let error = 0
    for (const ev of visibleEvents) {
      if (ev.severity === 'warn') warn += 1
      else if (ev.severity === 'error') error += 1
    }
    return { warn, error }
  }, [visibleEvents])

  if (isInitialLoading && liveEvents.length === 0) {
    // Mirror the loaded layout (header + filters card + event stream card)
    // so the cut-over to real data doesn't shift the page. Used only on
    // first fetch before any WS events have streamed in.
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="space-y-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-[28rem] max-w-full" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-9 w-24 rounded-md" />
            <Skeleton className="h-9 w-20 rounded-md" />
            <Skeleton className="h-9 w-20 rounded-md" />
          </div>
        </div>

        {/* Filters card */}
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-4 w-16" />
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-3 w-16" />
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-7 w-24 rounded-md" />
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Skeleton className="h-3 w-16" />
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-7 w-20 rounded-md" />
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-9 w-full rounded-md" />
              </div>
              <div className="flex flex-col gap-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-9 w-full rounded-md" />
              </div>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <Skeleton className="h-9 w-20 rounded-md" />
              <Skeleton className="h-9 w-24 rounded-md" />
            </div>
          </CardContent>
        </Card>

        {/* Event stream card */}
        <Card className="overflow-hidden">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-20" />
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="p-0">
            <div className="divide-y divide-border/60">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={`event-skel-${String(i)}`}
                  className="flex items-start gap-3 px-4 py-3"
                >
                  {/* Severity rail */}
                  <Skeleton className="mt-1 h-12 w-0.5 rounded-full" />
                  {/* Icon */}
                  <Skeleton className="mt-0.5 h-5 w-5 rounded-sm" />
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-3 w-32" />
                      <Skeleton className="h-3 w-24" />
                      <Skeleton className="h-3 w-20" />
                    </div>
                    <Skeleton className="h-4 w-3/4 max-w-md" />
                  </div>
                  <Skeleton className="h-3 w-16" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header — title on the left, all controls (filters + live + exports)
          right-aligned in one cluster. Single row at desktop widths so the
          page header looks like a proper toolbar; flex-wrap lets it spill
          gracefully onto a second line on narrower viewports. The visual
          divider between the filter group and the live/export group keeps
          "what to show" and "what to do with it" readable as two intents. */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">System Activity</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Live tail + historical search of every event the system emits.
            Thesis-grade evidence; admin-only.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <FilterToolbar
            categoryFilter={categoryFilter}
            severityFilter={severityFilter}
            onCategoryChange={setCategoryFilter}
            onSeverityChange={setSeverityFilter}
            scheduleInput={scheduleInput}
            studentInput={studentInput}
            scheduleFilter={scheduleFilter}
            studentFilter={studentFilter}
            onScheduleInputChange={setScheduleInput}
            onStudentInputChange={setStudentInput}
            onApplyTextFilters={applyTextFilters}
            onClearAll={clearAllFilters}
          />

          <Separator orientation="vertical" className="mx-1 h-9" />

          <LiveIndicator connected={isConnected} paused={paused} />
          {paused ? (
            <Button onClick={resume} variant="default" size="sm" className="h-9">
              <Play className="h-4 w-4 mr-2" />
              Resume
              {bufferedCount > 0 && (
                <Badge variant="secondary" className="ml-2">
                  +{bufferedCount}
                </Badge>
              )}
            </Button>
          ) : (
            <Button onClick={() => setPaused(true)} variant="outline" size="sm" className="h-9">
              <Pause className="h-4 w-4 mr-2" />
              Pause
            </Button>
          )}
          <Button asChild variant="outline" size="sm" className="h-9">
            <a
              href={activityService.exportCsvUrl(restFilters)}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-4 w-4 mr-2" />
              CSV
            </a>
          </Button>
          <Button asChild variant="outline" size="sm" className="h-9">
            <a
              href={activityService.exportJsonUrl(restFilters)}
              target="_blank"
              rel="noreferrer"
            >
              <FileJson className="h-4 w-4 mr-2" />
              JSON
            </a>
          </Button>
        </div>
      </div>

      {/* Actor pin breadcrumb — only rendered when deep-linked from a
          user-detail page. Lives outside the toolbar cluster because it's
          a one-line context affordance, not a control. */}
      {actorFilter && (
        <ActorPin actorId={actorFilter} onClear={clearActorFilter} />
      )}

      {/* Live stream */}
      <Card className="overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Event stream
            </CardTitle>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              {liveEvents.length > 0 ? (
                <>
                  {visibleSeverityCounts.error > 0 && (
                    <span className="inline-flex items-center gap-1 font-medium text-red-700 dark:text-red-300">
                      <XCircle className="h-3.5 w-3.5" />
                      {visibleSeverityCounts.error}
                    </span>
                  )}
                  {visibleSeverityCounts.warn > 0 && (
                    <span className="inline-flex items-center gap-1 font-medium text-amber-700 dark:text-amber-300">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      {visibleSeverityCounts.warn}
                    </span>
                  )}
                  <span>
                    {visibleEvents.length} shown
                    {hiddenInBuffer > 0 && ` · ${hiddenInBuffer} older buffered`}
                  </span>
                </>
              ) : isInitialLoading ? (
                'Loading…'
              ) : (
                'No events match the current filters yet.'
              )}
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="p-0">
          {/* Height is intentionally generous: when the user has scrolled
              past the filter card, the EVENT STREAM card sits near the
              viewport top and we want it to claim almost everything down
              to the bottom of the screen. The 100vh − 220px reserves
              just enough for the page header + EVENT STREAM card header
              + a little breathing room. ``min-h`` keeps the stream
              usable on shorter laptop displays where viewport math
              would otherwise produce a tiny box. */}
          <ScrollArea className="h-[calc(100vh-220px)] min-h-[560px]">
            <div className="divide-y divide-border/60">
              {visibleEvents.map((ev) => (
                <EventRow
                  key={ev.event_id}
                  event={ev}
                  onClick={() => setSelectedEvent(ev)}
                />
              ))}
              {visibleEvents.length === 0 && !isInitialLoading && (
                <div className="p-10 text-center text-sm text-muted-foreground">
                  Waiting for events…
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <EventDetailSheet
        event={selectedEvent}
        open={selectedEvent !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedEvent(null)
        }}
      />
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────

function LiveIndicator({
  connected,
  paused,
}: {
  connected: boolean
  paused: boolean
}) {
  if (paused) {
    return (
      <span className="inline-flex items-center gap-2 text-xs font-medium text-amber-700 dark:text-amber-300">
        <span className="h-2 w-2 rounded-full bg-amber-500" />
        PAUSED
      </span>
    )
  }
  if (connected) {
    return (
      <span className="inline-flex items-center gap-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">
        <Wifi className="h-3.5 w-3.5" />
        LIVE
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
      <WifiOff className="h-3.5 w-3.5" />
      Disconnected
    </span>
  )
}

/**
 * Filter toolbar — Select-dropdown cluster matching the Students /
 * Faculty / Admins registries.
 *
 * Layout: [Category ▾] [Severity ▾] [More ▾] [Clear]
 *
 * Why dropdowns instead of toggle chips:
 *   - Visual consistency with the rest of the admin portal: every
 *     other registry-style page filters via 130–150px-wide Select
 *     triggers, so this page now looks like it belongs.
 *   - Single-value semantics fit how operators actually filter here
 *     ("show me only errors", "only attendance events"). Multi-select
 *     was supported by the old chip UI but no caller ever generated
 *     deep-links that used it.
 *   - The Schedule / Student UUID inputs stay behind a "More" popover
 *     because they're deep-link affordances rarely typed by hand —
 *     the Students page has no equivalent so there's no consistent
 *     analogue to copy; a popover keeps the toolbar height identical
 *     to other pages while preserving the capability.
 *
 * The actor-pin breadcrumb (when deep-linked from a user-detail page)
 * is rendered separately below the header — it's a context affordance,
 * not a control, and folding it into the toolbar would crowd the row.
 */
function FilterToolbar({
  categoryFilter,
  severityFilter,
  onCategoryChange,
  onSeverityChange,
  scheduleInput,
  studentInput,
  scheduleFilter,
  studentFilter,
  onScheduleInputChange,
  onStudentInputChange,
  onApplyTextFilters,
  onClearAll,
}: {
  categoryFilter: ActivityCategory | ''
  severityFilter: ActivitySeverity | ''
  onCategoryChange: (value: string) => void
  onSeverityChange: (value: string) => void
  scheduleInput: string
  studentInput: string
  scheduleFilter: string
  studentFilter: string
  onScheduleInputChange: (v: string) => void
  onStudentInputChange: (v: string) => void
  onApplyTextFilters: () => void
  onClearAll: () => void
}) {
  const idFilterCount = (scheduleFilter ? 1 : 0) + (studentFilter ? 1 : 0)
  const hasAnyFilter =
    !!categoryFilter ||
    !!severityFilter ||
    !!scheduleFilter ||
    !!studentFilter

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        value={categoryFilter || 'all'}
        onValueChange={onCategoryChange}
      >
        <SelectTrigger className="w-[170px] h-9">
          <SelectValue placeholder="Category" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All categories</SelectItem>
          {CATEGORIES.map((cat) => (
            <SelectItem key={cat} value={cat} className="capitalize">
              {cat}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={severityFilter || 'all'}
        onValueChange={onSeverityChange}
      >
        <SelectTrigger className="w-[160px] h-9">
          <SelectValue placeholder="Severity" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All severities</SelectItem>
          {SEVERITIES.map((sev) => (
            <SelectItem key={sev} value={sev} className="capitalize">
              {sev}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" className="h-9">
            <SlidersHorizontal className="h-3.5 w-3.5 mr-1.5" />
            More
            {idFilterCount > 0 && (
              <Badge variant="secondary" className="ml-1.5 h-4 px-1">
                {idFilterCount}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-80 space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">
              Schedule ID
            </label>
            <Input
              value={scheduleInput}
              onChange={(e) => onScheduleInputChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onApplyTextFilters()}
              placeholder="UUID"
              className="h-8 font-mono text-xs"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">
              Student ID
            </label>
            <Input
              value={studentInput}
              onChange={(e) => onStudentInputChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onApplyTextFilters()}
              placeholder="UUID"
              className="h-8 font-mono text-xs"
            />
          </div>
          <Button onClick={onApplyTextFilters} size="sm" className="w-full">
            Apply
          </Button>
        </PopoverContent>
      </Popover>

      {hasAnyFilter && (
        <Button
          onClick={onClearAll}
          variant="ghost"
          size="sm"
          className="h-9 px-2 text-muted-foreground"
        >
          Clear
        </Button>
      )}
    </div>
  )
}

function ActorPin({
  actorId,
  onClear,
}: {
  actorId: string
  onClear: () => void
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs">
      <span className="font-medium text-blue-700 dark:text-blue-400">
        Pinned to actor
      </span>
      <span className="font-mono text-[11px] text-foreground">
        {actorId.slice(0, 8)}…{actorId.slice(-4)}
      </span>
      <button
        type="button"
        onClick={onClear}
        className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium text-blue-700 transition hover:bg-blue-500/20 dark:text-blue-400"
        aria-label="Clear actor filter"
      >
        <X className="h-3 w-3" />
        Clear
      </button>
    </div>
  )
}

/**
 * One row of the live event stream.
 *
 * Anatomy (left → right):
 *   1. Severity rail (4px, full row height) — the at-a-glance "any red?".
 *   2. Per-event-type icon, colored by category — instant identity
 *      without reading the chip text.
 *   3. Metadata chips (timestamp, category-dotted event_type, schedule
 *      code, subject name).
 *   4. Summary line (one truncated line, slightly stronger weight than
 *      the metadata so the eye lands on "what happened" first).
 *
 * Background:
 *   - info / success: transparent at rest, muted hover.
 *   - warn / error: faint amber/red wash at rest so triage rows stand
 *     out from the firehose, slightly darker hover.
 */
function EventRow({
  event,
  onClick,
}: {
  event: ActivityEvent
  onClick: () => void
}) {
  const Icon = eventTypeIcon[event.event_type] ?? Activity
  const tint = severityTintClass[event.severity]
  const iconAccent = severityIconClass[event.severity]
  const chipClass = severityChipClass[event.severity]
  const isAlert = event.severity === 'warn' || event.severity === 'error'

  return (
    <button
      onClick={onClick}
      className={cn(
        'group w-full text-left flex items-stretch gap-0 transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40',
        tint,
        isAlert
          ? 'hover:bg-muted/40 focus-visible:bg-muted/40'
          : 'hover:bg-muted/40 focus-visible:bg-muted/40',
      )}
    >
      {/* Severity rail */}
      <div
        className={cn(
          'w-1 shrink-0 transition-colors',
          severityRailClass[event.severity],
          // Visual feedback on hover — subtle width-feel by going opaque.
          'group-hover:opacity-100',
          event.severity === 'info' && 'group-hover:bg-foreground/30',
        )}
        aria-hidden
      />

      {/* Icon column. Fixed width so chips below align across rows. */}
      <div className="shrink-0 w-10 flex items-start justify-center pt-3">
        <Icon
          className={cn('h-[18px] w-[18px]', iconAccent)}
          strokeWidth={2.25}
          aria-hidden
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pr-4 py-2.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Unified timestamp via @/lib/format-time. Same MMM d HH:mm:ss
              format used by DetectionHistoryList, RecognitionPanel,
              MatchEvidence, and the recognition/audit tables — operators
              can correlate events across views by glancing at the time. */}
          <span
            className="font-mono text-[11px] tabular-nums text-muted-foreground shrink-0"
            title={formatFullDatetime(event.created_at)}
          >
            {formatTimestamp(event.created_at)}
          </span>

          {/* Event type chip — severity-tinted background carries the
              "is this good/neutral/bad?" signal at a glance. The leading
              category dot is the secondary "what bucket" hint; small on
              purpose so it doesn't compete with severity. */}
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded border px-1.5 py-[1px]',
              'font-mono text-[10px] font-semibold uppercase tracking-wider',
              chipClass,
            )}
          >
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full shrink-0',
                categoryDotClass[event.category],
              )}
              aria-hidden
            />
            {event.event_type}
          </span>

          {event.subject_schedule_subject && (
            <span className="inline-flex items-center rounded border border-dashed border-border px-1.5 py-[1px] font-mono text-[10px] text-muted-foreground">
              {event.subject_schedule_subject}
            </span>
          )}

          {event.subject_user_name && (
            <span className="text-xs font-medium text-foreground/80 truncate">
              {event.subject_user_name}
            </span>
          )}
        </div>

        <p className="text-sm mt-1 leading-snug text-foreground/90 truncate">
          {formatEventSummary(event)}
        </p>
      </div>
    </button>
  )
}

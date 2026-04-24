import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { format } from 'date-fns'
import {
  Activity,
  Download,
  FileJson,
  Pause,
  Play,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { useActivityEvents, useActivityStats } from '@/hooks/use-queries'
import { useActivityWs } from '@/hooks/use-activity-ws'
import { usePageTitle } from '@/hooks/use-page-title'
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

const severityRailClass: Record<ActivitySeverity, string> = {
  info: 'bg-muted-foreground/30',
  success: 'bg-emerald-500',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
}

const categoryBadgeClass: Record<ActivityCategory, string> = {
  attendance: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200',
  session: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200',
  recognition:
    'bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200',
  system: 'bg-slate-100 text-slate-800 dark:bg-slate-900 dark:text-slate-200',
  audit: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200',
}

function isoMinutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

export default function ActivityPage() {
  usePageTitle('System Activity')

  const [searchParams, setSearchParams] = useSearchParams()

  // Filters parsed from URL — shareable, deep-linkable.
  const selectedCategories = useMemo(() => {
    const raw = searchParams.get('category')
    if (!raw) return new Set<ActivityCategory>()
    return new Set(
      raw.split(',').filter(Boolean) as ActivityCategory[],
    )
  }, [searchParams])

  const selectedSeverities = useMemo(() => {
    const raw = searchParams.get('severity')
    if (!raw) return new Set<ActivitySeverity>()
    return new Set(raw.split(',').filter(Boolean) as ActivitySeverity[])
  }, [searchParams])

  const scheduleFilter = searchParams.get('schedule_id') ?? ''
  const studentFilter = searchParams.get('student_id') ?? ''

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
    if (selectedCategories.size)
      out.category = Array.from(selectedCategories).join(',')
    if (selectedSeverities.size)
      out.severity = Array.from(selectedSeverities).join(',')
    if (scheduleFilter) out.schedule_id = scheduleFilter
    if (studentFilter) out.student_id = studentFilter
    return out
  }, [selectedCategories, selectedSeverities, scheduleFilter, studentFilter])

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

  // Stats for the top strip.
  const { data: stats } = useActivityStats(15)

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
      [paused],
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

  const toggleCategory = (cat: ActivityCategory) => {
    const next = new URLSearchParams(searchParams)
    const current = new Set(selectedCategories)
    if (current.has(cat)) current.delete(cat)
    else current.add(cat)
    if (current.size === 0) next.delete('category')
    else next.set('category', Array.from(current).join(','))
    setSearchParams(next)
  }

  const toggleSeverity = (sev: ActivitySeverity) => {
    const next = new URLSearchParams(searchParams)
    const current = new Set(selectedSeverities)
    if (current.has(sev)) current.delete(sev)
    else current.add(sev)
    if (current.size === 0) next.delete('severity')
    else next.set('severity', Array.from(current).join(','))
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

  const visibleEvents = liveEvents.slice(0, MAX_VISIBLE)
  const hiddenInBuffer = liveEvents.length - visibleEvents.length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Activity className="h-5 w-5 text-muted-foreground" />
            System Activity
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Live tail + historical search of every event the system emits.
            Thesis-grade evidence; admin-only.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LiveIndicator connected={isConnected} paused={paused} />
          {paused ? (
            <Button onClick={resume} variant="default" size="sm">
              <Play className="h-4 w-4 mr-2" />
              Resume
              {bufferedCount > 0 && (
                <Badge variant="secondary" className="ml-2">
                  +{bufferedCount}
                </Badge>
              )}
            </Button>
          ) : (
            <Button onClick={() => setPaused(true)} variant="outline" size="sm">
              <Pause className="h-4 w-4 mr-2" />
              Pause
            </Button>
          )}
          <Button asChild variant="outline" size="sm">
            <a
              href={activityService.exportCsvUrl(restFilters)}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-4 w-4 mr-2" />
              CSV
            </a>
          </Button>
          <Button asChild variant="outline" size="sm">
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

      {/* Live counters strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Metric
          label="Events / min"
          value={stats ? stats.events_per_minute.toFixed(1) : '—'}
        />
        <Metric
          label="Active sessions"
          value={stats ? String(stats.active_session_count) : '—'}
        />
        <Metric
          label="Attendance"
          value={stats ? String(stats.by_category.attendance) : '—'}
          hint="last 15 min"
        />
        <Metric
          label="Recognition"
          value={stats ? String(stats.by_category.recognition) : '—'}
          hint="last 15 min"
        />
        <Metric
          label="Warnings"
          value={stats ? String(stats.by_severity.warn) : '—'}
          hint="last 15 min"
          emphasis={stats && stats.by_severity.warn > 0 ? 'warn' : undefined}
        />
        <Metric
          label="Errors"
          value={stats ? String(stats.by_severity.error) : '—'}
          hint="last 15 min"
          emphasis={stats && stats.by_severity.error > 0 ? 'error' : undefined}
        />
      </div>

      {/* Filter bar */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2">
            <label className="text-xs text-muted-foreground">Category</label>
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((cat) => {
                const active = selectedCategories.has(cat)
                return (
                  <Button
                    key={cat}
                    size="sm"
                    variant={active ? 'default' : 'outline'}
                    onClick={() => toggleCategory(cat)}
                    className="h-7 capitalize"
                  >
                    {cat}
                  </Button>
                )
              })}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs text-muted-foreground">Severity</label>
            <div className="flex flex-wrap gap-2">
              {SEVERITIES.map((sev) => {
                const active = selectedSeverities.has(sev)
                return (
                  <Button
                    key={sev}
                    size="sm"
                    variant={active ? 'default' : 'outline'}
                    onClick={() => toggleSeverity(sev)}
                    className="h-7 capitalize"
                  >
                    {sev}
                  </Button>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">
                Schedule ID
              </label>
              <Input
                value={scheduleInput}
                onChange={(e) => setScheduleInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && applyTextFilters()}
                placeholder="UUID"
                className="h-9 font-mono text-xs"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">
                Student ID
              </label>
              <Input
                value={studentInput}
                onChange={(e) => setStudentInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && applyTextFilters()}
                placeholder="UUID"
                className="h-9 font-mono text-xs"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Button onClick={applyTextFilters} size="sm">
              Apply
            </Button>
            <Button
              onClick={clearAllFilters}
              size="sm"
              variant="ghost"
              disabled={
                selectedCategories.size === 0 &&
                selectedSeverities.size === 0 &&
                !scheduleFilter &&
                !studentFilter
              }
            >
              <X className="h-4 w-4 mr-1" />
              Clear all
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Live stream */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Event stream
            </CardTitle>
            <div className="text-xs text-muted-foreground">
              {liveEvents.length > 0
                ? `${visibleEvents.length} shown${
                    hiddenInBuffer > 0 ? ` · ${hiddenInBuffer} older buffered` : ''
                  }`
                : isInitialLoading
                  ? 'Loading…'
                  : 'No events match the current filters yet.'}
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-480px)] min-h-[300px]">
            <div className="divide-y">
              {visibleEvents.map((ev) => (
                <EventRow
                  key={ev.event_id}
                  event={ev}
                  onClick={() => setSelectedEvent(ev)}
                />
              ))}
              {visibleEvents.length === 0 && !isInitialLoading && (
                <div className="p-8 text-center text-sm text-muted-foreground">
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

function Metric({
  label,
  value,
  hint,
  emphasis,
}: {
  label: string
  value: string
  hint?: string
  emphasis?: 'warn' | 'error'
}) {
  const valueClass =
    emphasis === 'error'
      ? 'text-red-700 dark:text-red-300'
      : emphasis === 'warn'
        ? 'text-amber-700 dark:text-amber-300'
        : ''
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`text-xl font-semibold mt-0.5 ${valueClass}`}>{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

function EventRow({
  event,
  onClick,
}: {
  event: ActivityEvent
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-stretch gap-0 hover:bg-muted/50 transition-colors focus:outline-none focus:bg-muted/50"
    >
      {/* Severity rail */}
      <div className={`w-[3px] ${severityRailClass[event.severity]}`} />
      <div className="flex-1 px-4 py-2.5 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[11px] text-muted-foreground shrink-0">
            {format(new Date(event.created_at), 'HH:mm:ss')}
          </span>
          <Badge
            variant="outline"
            className={`${categoryBadgeClass[event.category]} text-[10px] uppercase`}
          >
            {event.event_type}
          </Badge>
          {event.subject_schedule_subject && (
            <Badge variant="secondary" className="text-[10px]">
              {event.subject_schedule_subject}
            </Badge>
          )}
          {event.subject_user_name && (
            <span className="text-xs text-muted-foreground truncate">
              {event.subject_user_name}
            </span>
          )}
        </div>
        <p className="text-sm mt-1 truncate">{event.summary}</p>
      </div>
    </button>
  )
}

import { useEffect, useState } from 'react'

import type { AttendanceSummaryMessage, AttendanceStatusEntry } from '@/hooks/use-attendance-ws'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'

interface AttendancePanelProps {
  summary: AttendanceSummaryMessage | null
  isConnected: boolean
  /**
   * Called when a student row is clicked. When undefined the rows render
   * as plain `<div>`s; when defined they become focusable `<button>`s that
   * open the TrackDetailSheet.
   */
  onSelect?: (userId: string) => void
}

type StatusKey = 'present' | 'late' | 'early_leave' | 'early_leave_returned' | 'absent'

type StatusConfig = {
  key: StatusKey
  countKey: keyof Pick<
    AttendanceSummaryMessage,
    'present_count' | 'late_count' | 'absent_count' | 'early_leave_count' | 'early_leave_returned_count'
  >
  label: string
  /** Tailwind background for the segmented progress bar slice. */
  segment: string
  /** Tailwind classes for the per-row status pill. */
  pillClass: string
  /** Whether to surface check-in / early-leave timestamps on rows. */
  show: 'check_in' | 'early_leave' | null
}

// Listed in attendance order — present/in-class students first so the
// operator confirms who's accounted for, then late, early-leave, returned,
// and finally absent (the residual).
const STATUSES: StatusConfig[] = [
  {
    key: 'present',
    countKey: 'present_count',
    label: 'On Time',
    segment: 'bg-emerald-500',
    pillClass: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    show: 'check_in',
  },
  {
    key: 'late',
    countKey: 'late_count',
    label: 'Late',
    segment: 'bg-amber-500',
    pillClass: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
    show: 'check_in',
  },
  {
    key: 'early_leave',
    countKey: 'early_leave_count',
    label: 'Early Leave',
    segment: 'bg-orange-500',
    pillClass: 'border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400',
    show: 'early_leave',
  },
  {
    key: 'early_leave_returned',
    countKey: 'early_leave_returned_count',
    label: 'Returned',
    segment: 'bg-blue-500',
    pillClass: 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400',
    // Returned students are currently in class — surface their original
    // check-in time, not the early-leave timestamp, since the row's
    // pre-incident `was on time` / `was late` hint already supplies the
    // status context. (Their early-leave timestamp lives on the
    // attendance record for analytics and the EarlyLeaveEvent table.)
    show: 'check_in',
  },
  {
    key: 'absent',
    countKey: 'absent_count',
    label: 'Absent',
    segment: 'bg-red-500',
    pillClass: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400',
    show: null,
  },
]

function formatTime(iso?: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

/** Compact "Hh Mm Ss" duration; drops zero-leading components for readability. */
function formatDuration(seconds: number): string {
  if (seconds < 1) return '0s'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const remM = m % 60
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`
}

/**
 * Below this delta we don't render a "missing" indicator on present/late
 * rows — keeps the UI stable for trivial frame-to-frame gaps that the
 * backend hasn't flagged yet (60s scan interval + ByteTrack noise can
 * easily produce 1-3s gaps even for a perfectly stationary student).
 */
const MISSING_FLOOR_SECONDS = 5

/**
 * Map progress-toward-threshold to color escalation. The thresholds are
 * intentionally biased to leave the row mostly muted at the start of an
 * absence and only escalate as the student approaches the early-leave
 * cutoff; this stops a 5s blip from turning the panel into a wall of red.
 */
function escalationClass(pct: number): {
  text: string
  bar: string
  bg: string
  ariaSeverity: 'low' | 'medium' | 'high' | 'critical'
} {
  if (pct < 33) {
    return {
      text: 'text-muted-foreground',
      bar: 'bg-muted-foreground/50',
      bg: '',
      ariaSeverity: 'low',
    }
  }
  if (pct < 66) {
    return {
      text: 'text-amber-600 dark:text-amber-400',
      bar: 'bg-amber-500',
      bg: 'bg-amber-500/[0.04]',
      ariaSeverity: 'medium',
    }
  }
  if (pct < 100) {
    return {
      text: 'text-orange-600 dark:text-orange-400',
      bar: 'bg-orange-500',
      bg: 'bg-orange-500/[0.06]',
      ariaSeverity: 'high',
    }
  }
  return {
    text: 'text-red-600 dark:text-red-400',
    bar: 'bg-red-500',
    bg: 'bg-red-500/[0.08]',
    ariaSeverity: 'critical',
  }
}

interface MissingState {
  /** Seconds since the student was last detected on camera. */
  secondsAway: number
  /** Per-schedule early-leave threshold. `null` when the backend doesn't
   *  send one — the duration text still renders, but no progress bar. */
  thresholdSec: number | null
  /**
   * `true` for rows already in the early_leave bucket — the duration
   * keeps counting up but the progress bar pegs at 100% (red) since
   * they've already crossed the cutoff. Visual signal for "they walked
   * out and haven't come back yet".
   */
  isEarlyLeave: boolean
}

function StudentRow({
  entry,
  pillLabel,
  pillClass,
  meta,
  hint,
  missing,
  onSelect,
}: {
  entry: AttendanceStatusEntry
  pillLabel: string
  pillClass: string
  meta: string
  /**
   * Optional pre-meta annotation rendered in the same muted subtitle
   * line. Used today to carry the "was on time" / "was late" context
   * for returned students so the row stays informative without a
   * second pill. Plain text (no mono font) so it doesn't read like a
   * timestamp.
   */
  hint?: string
  /** When provided, renders the off-camera duration + progress bar. */
  missing: MissingState | null
  onSelect?: (userId: string) => void
}) {
  // Early-leavers peg at 100% (already crossed the cutoff); everyone else
  // races their secondsAway against the threshold. When the threshold is
  // unknown we fall back to muted styling — the duration still renders,
  // but with no "you're approaching the limit" cue.
  const pct =
    missing && missing.thresholdSec != null
      ? Math.min(100, (missing.secondsAway / missing.thresholdSec) * 100)
      : 0
  const colors = missing
    ? escalationClass(missing.isEarlyLeave ? 100 : pct)
    : null

  const durationLabel = missing
    ? missing.isEarlyLeave
      ? `gone ${formatDuration(missing.secondsAway)}`
      : `missing ${formatDuration(missing.secondsAway)}`
    : null

  const Inner = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className="truncate text-sm font-medium">{entry.name}</div>
          {durationLabel && colors && (
            <span
              className={`shrink-0 font-mono text-[11px] font-medium tabular-nums ${colors.text}`}
              aria-label={`Off camera for ${formatDuration(missing!.secondsAway)}`}
              data-severity={colors.ariaSeverity}
            >
              {durationLabel}
            </span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
          {entry.student_id && <span className="font-mono">{entry.student_id}</span>}
          {hint && (
            <>
              {entry.student_id && <span className="opacity-50">·</span>}
              <span>{hint}</span>
            </>
          )}
          {meta && (
            <>
              {(entry.student_id || hint) && <span className="opacity-50">·</span>}
              <span className="font-mono tabular-nums">{meta}</span>
            </>
          )}
        </div>
        {missing && missing.thresholdSec != null && colors && (
          <div
            className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted/70"
            role="progressbar"
            aria-valuenow={Math.round(pct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Time off-camera vs early-leave threshold`}
          >
            <div
              className={`h-full ${colors.bar} transition-[width] duration-700 ease-linear`}
              style={{ width: `${Math.max(2, pct)}%` }}
            />
          </div>
        )}
      </div>
      <span
        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${pillClass}`}
      >
        {pillLabel}
      </span>
    </>
  )

  const tintClass = colors?.bg ?? ''

  if (!onSelect) {
    return (
      <div className={`flex items-center gap-3 rounded-md px-2 py-2 transition-colors ${tintClass}`}>
        {Inner}
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={() => onSelect(entry.user_id)}
      aria-label={`Inspect ${entry.name}`}
      className={`flex w-full cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-left transition hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${tintClass}`}
    >
      {Inner}
    </button>
  )
}

/**
 * Right-rail attendance summary for the live feed page. Replaces the prior
 * 5-card stat grid with a single segmented progress bar (proportions of
 * each status against total enrolled) plus a flat priority-ordered roster
 * grouped by status. Color is reserved for the bar slices and the row
 * pills — group headers stay monochrome so the eye reads the data, not
 * the chrome.
 *
 * The roster also surfaces a live "off-camera duration" inline on
 * present/late rows the moment a student walks out of frame, racing the
 * elapsed seconds against the schedule's early-leave threshold via a
 * thin escalating progress bar. The timer ticks locally at 1 Hz against
 * the backend's last_seen_at so it stays smooth between the ~2s
 * attendance_summary broadcasts.
 */
export function AttendancePanel({ summary, isConnected, onSelect }: AttendancePanelProps) {
  // Tick `nowMs` every 1s so the missing-timers count up smoothly between
  // backend broadcasts (~2s + on-event). The whole panel re-renders, but
  // the roster is small (~30 rows max in classroom-scale schedules) so
  // the cost is negligible vs. running N intervals — one per row.
  const [nowMs, setNowMs] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  // Client-vs-server clock origin, captured the instant a new summary
  // arrives. Without this, a browser whose wall-clock is even a few
  // minutes off (common on personal laptops without NTP) would render
  // bogus durations — possibly negative, possibly hours-long. RTT is
  // ignored: at 1 Hz tick resolution the residual error is invisible,
  // and the alternative (round-trip ping) doesn't pay off.
  //
  // We store BOTH halves of the pair (server timestamp + the local
  // Date.now() captured the moment we received it) so the live
  // serverNowMs derivation below stays pure — it only uses props and
  // state, never calls Date.now() during render.
  //
  // The eslint-disable matches the pattern in use-attendance-ws.ts:
  // a setState in an effect is acceptable when the effect has a
  // primitive dep that genuinely changes only when an external event
  // fires (here, a new attendance_summary broadcast every ~2 s).
  const [clockOrigin, setClockOrigin] = useState<{ server: number; client: number } | null>(null)
  useEffect(() => {
    if (summary?.server_time_ms == null) return
    /* eslint-disable react-hooks/set-state-in-effect */
    setClockOrigin({ server: summary.server_time_ms, client: Date.now() })
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [summary?.server_time_ms])
  const serverNowMs = clockOrigin
    ? clockOrigin.server + (nowMs - clockOrigin.client)
    : nowMs

  if (!summary) {
    return (
      <Card className="flex h-full flex-col">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Attendance</CardTitle>
            <span
              className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-muted-foreground/40'}`}
              aria-label={isConnected ? 'Connected' : 'Connecting'}
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {isConnected ? 'Waiting for first summary…' : 'Connecting…'}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-2 w-full rounded-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="space-y-2 pt-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  const total = Math.max(summary.total_enrolled || 0, 1)
  // "In class" = currently visible in the room. Returned students are
  // back on camera, so they count too. The bucket counts are now
  // mutually exclusive (no student appears in more than one) so this
  // sum is honest — no double-counting like the previous
  // `present_count + late_count` formula, which silently inflated the
  // total whenever a student walked out and came back.
  const inClass =
    summary.present_count + summary.late_count + summary.early_leave_returned_count
  const thresholdSec = summary.early_leave_threshold_seconds ?? null

  // Compute the missing-state for one row. Returns null when the row
  // shouldn't render a duration — either no last_seen_at, or the gap is
  // too small to be worth surfacing. Early-leavers always render
  // (no floor), since they're definitionally off-camera and the badge
  // is the whole point.
  const computeMissing = (
    entry: AttendanceStatusEntry,
    isEarlyLeave: boolean,
  ): MissingState | null => {
    if (!entry.last_seen_at) return null
    const lastSeenMs = new Date(entry.last_seen_at).getTime()
    if (Number.isNaN(lastSeenMs)) return null
    const secondsAway = Math.max(0, Math.floor((serverNowMs - lastSeenMs) / 1000))
    if (!isEarlyLeave && secondsAway < MISSING_FLOOR_SECONDS) return null
    return { secondsAway, thresholdSec, isEarlyLeave }
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Attendance</CardTitle>
          <span
            className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-muted-foreground/40'}`}
            aria-label={isConnected ? 'Connected' : 'Connecting'}
          />
        </div>
        <div className="flex items-baseline gap-1.5 text-xs text-muted-foreground">
          <span className="text-base font-semibold tabular-nums text-foreground">
            {inClass}
          </span>
          <span>in class of</span>
          <span className="font-medium tabular-nums text-foreground">
            {summary.total_enrolled}
          </span>
          <span>enrolled</span>
        </div>

        {/* Segmented progress bar — proportions out of total enrolled. */}
        <div
          className="mt-3 flex h-1.5 w-full overflow-hidden rounded-full bg-muted"
          role="img"
          aria-label="Attendance breakdown"
        >
          {STATUSES.map((s) => {
            const count = summary[s.countKey] ?? 0
            if (count === 0) return null
            const pct = (count / total) * 100
            return (
              <div
                key={s.key}
                className={s.segment}
                style={{ width: `${pct}%` }}
                title={`${s.label}: ${count}`}
              />
            )
          })}
        </div>

        {/* Compact counter strip — single row, reads left-to-right. */}
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
          {STATUSES.map((s) => {
            const count = summary[s.countKey] ?? 0
            return (
              <div key={s.key} className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${s.segment}`} />
                <span className="font-semibold tabular-nums text-foreground">
                  {count}
                </span>
                <span className="text-muted-foreground">{s.label}</span>
              </div>
            )
          })}
        </div>

        {thresholdSec != null && (
          <div className="mt-2 text-[10px] text-muted-foreground">
            Early-leave cutoff{' '}
            <span className="font-mono tabular-nums text-foreground/80">
              {formatDuration(Math.round(thresholdSec))}
            </span>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full">
          <div className="space-y-4 px-4 py-3">
            {STATUSES.map((s) => {
              const list = summary[s.key] ?? []
              if (list.length === 0) return null
              return (
                <div key={s.key} className="space-y-0.5">
                  <div className="mb-1 flex items-center gap-2 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    <span>{s.label}</span>
                    <span className="text-muted-foreground/60">·</span>
                    <span className="tabular-nums">{list.length}</span>
                  </div>
                  {list.map((entry) => {
                    const meta =
                      s.show === 'check_in'
                        ? formatTime(entry.check_in_time)
                        : s.show === 'early_leave'
                          ? formatTime(entry.early_leave_time)
                          : ''
                    // For returned students, surface the pre-incident
                    // status as a quiet "was on time" / "was late" hint
                    // so the operator can still see what the student's
                    // status was BEFORE they walked out. Returned rows
                    // no longer also appear under On Time / Late, so
                    // this is the single place that context lives.
                    const hint =
                      s.key === 'early_leave_returned' && entry.underlying_status
                        ? entry.underlying_status === 'late'
                          ? 'was late'
                          : 'was on time'
                        : undefined
                    // Missing-timer applies to:
                    //  - present / late students currently off-camera
                    //    (delta >= MISSING_FLOOR_SECONDS)
                    //  - early_leave (always — they're flagged because
                    //    they crossed the threshold and the duration is
                    //    the whole point of the row)
                    const showMissing =
                      s.key === 'present' || s.key === 'late' || s.key === 'early_leave'
                    const missing = showMissing
                      ? computeMissing(entry, s.key === 'early_leave')
                      : null
                    return (
                      <StudentRow
                        key={entry.user_id}
                        entry={entry}
                        pillLabel={s.label}
                        pillClass={s.pillClass}
                        meta={meta}
                        hint={hint}
                        missing={missing}
                        onSelect={onSelect}
                      />
                    )
                  })}
                </div>
              )
            })}

            {STATUSES.every((s) => (summary[s.key] ?? []).length === 0) && (
              <div className="px-2 py-8 text-center text-xs text-muted-foreground">
                No attendance activity yet.
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

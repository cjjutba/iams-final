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

// Listed in display priority — items needing attention first, then on-time
// last so the operator's eye lands on the actionable rows immediately.
const STATUSES: StatusConfig[] = [
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
    key: 'absent',
    countKey: 'absent_count',
    label: 'Absent',
    segment: 'bg-red-500',
    pillClass: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400',
    show: null,
  },
  {
    key: 'early_leave_returned',
    countKey: 'early_leave_returned_count',
    label: 'Returned',
    segment: 'bg-blue-500',
    pillClass: 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400',
    show: 'early_leave',
  },
  {
    key: 'present',
    countKey: 'present_count',
    label: 'On Time',
    segment: 'bg-emerald-500',
    pillClass: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    show: 'check_in',
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

function StudentRow({
  entry,
  pillLabel,
  pillClass,
  meta,
  onSelect,
}: {
  entry: AttendanceStatusEntry
  pillLabel: string
  pillClass: string
  meta: string
  onSelect?: (userId: string) => void
}) {
  const Inner = (
    <>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{entry.name}</div>
        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
          {entry.student_id && <span className="font-mono">{entry.student_id}</span>}
          {meta && (
            <>
              {entry.student_id && <span className="opacity-50">·</span>}
              <span className="font-mono tabular-nums">{meta}</span>
            </>
          )}
        </div>
      </div>
      <span
        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${pillClass}`}
      >
        {pillLabel}
      </span>
    </>
  )

  if (!onSelect) {
    return (
      <div className="flex items-center gap-3 rounded-md px-2 py-2">{Inner}</div>
    )
  }
  return (
    <button
      type="button"
      onClick={() => onSelect(entry.user_id)}
      aria-label={`Inspect ${entry.name}`}
      className="flex w-full cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-left transition hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
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
 */
export function AttendancePanel({ summary, isConnected, onSelect }: AttendancePanelProps) {
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
  const inClass = summary.present_count + summary.late_count

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
                    return (
                      <StudentRow
                        key={entry.user_id}
                        entry={entry}
                        pillLabel={s.label}
                        pillClass={s.pillClass}
                        meta={meta}
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

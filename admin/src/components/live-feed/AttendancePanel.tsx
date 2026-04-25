import { CheckCircle2, Clock, DoorOpen, UserX, RotateCcw } from 'lucide-react'
import type { AttendanceSummaryMessage, AttendanceStatusEntry } from '@/hooks/use-attendance-ws'
import { Badge } from '@/components/ui/badge'
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

type StatusConfig = {
  key: keyof Pick<
    AttendanceSummaryMessage,
    'present' | 'late' | 'absent' | 'early_leave' | 'early_leave_returned'
  >
  countKey: keyof Pick<
    AttendanceSummaryMessage,
    'present_count' | 'late_count' | 'absent_count' | 'early_leave_count' | 'early_leave_returned_count'
  >
  label: string
  icon: typeof CheckCircle2
  badgeClass: string
}

const STATUSES: StatusConfig[] = [
  {
    key: 'present',
    countKey: 'present_count',
    label: 'On Time',
    icon: CheckCircle2,
    badgeClass: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  },
  {
    key: 'late',
    countKey: 'late_count',
    label: 'Late',
    icon: Clock,
    badgeClass: 'bg-slate-500/10 text-slate-600 border-slate-500/20',
  },
  {
    key: 'early_leave',
    countKey: 'early_leave_count',
    label: 'Early Leave',
    icon: DoorOpen,
    badgeClass: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  },
  {
    key: 'early_leave_returned',
    countKey: 'early_leave_returned_count',
    label: 'Returned',
    icon: RotateCcw,
    badgeClass: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  },
  {
    key: 'absent',
    countKey: 'absent_count',
    label: 'Absent',
    icon: UserX,
    badgeClass: 'bg-red-500/10 text-red-600 border-red-500/20',
  },
]

function formatTime(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function StudentRow({
  entry,
  showCheckIn = false,
  showEarlyLeave = false,
  onSelect,
}: {
  entry: AttendanceStatusEntry
  showCheckIn?: boolean
  showEarlyLeave?: boolean
  onSelect?: (userId: string) => void
}) {
  const content = (
    <>
      <span className="truncate font-medium">{entry.name}</span>
      <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
        {entry.student_id && <span className="font-mono">{entry.student_id}</span>}
        {showCheckIn && entry.check_in_time && <span>{formatTime(entry.check_in_time)}</span>}
        {showEarlyLeave && entry.early_leave_time && <span>{formatTime(entry.early_leave_time)}</span>}
      </div>
    </>
  )

  if (!onSelect) {
    return (
      <div className="flex items-center justify-between gap-2 py-1.5 text-sm">{content}</div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(entry.user_id)}
      aria-label={`Inspect ${entry.name}`}
      className="flex w-full cursor-pointer items-center justify-between gap-2 rounded px-1 py-1.5 text-left text-sm transition hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {content}
    </button>
  )
}

/**
 * Right-side panel for the admin live-feed page. Shows running counts +
 * per-status student lists from the attendance_summary WebSocket message.
 */
export function AttendancePanel({ summary, isConnected, onSelect }: AttendancePanelProps) {
  if (!summary) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-base">Attendance</CardTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-muted-foreground'}`} />
            {isConnected ? 'Connected — waiting for first summary…' : 'Connecting…'}
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-6 w-full" />
          ))}
        </CardContent>
      </Card>
    )
  }

  const totalEnrolled = summary.total_enrolled || 0

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Attendance</CardTitle>
          <span className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-muted-foreground'}`} />
        </div>
        <div className="text-xs text-muted-foreground">
          {summary.present_count + summary.late_count} in class / {totalEnrolled} enrolled
        </div>
      </CardHeader>

      <CardContent className="flex-1 space-y-4 overflow-hidden">
        {/* Compact counts grid */}
        <div className="grid grid-cols-5 gap-2">
          {STATUSES.map((s) => {
            const Icon = s.icon
            return (
              <div
                key={s.key}
                className="flex flex-col items-center gap-1 rounded-md border bg-card p-2"
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span className="text-lg font-semibold leading-none">{summary[s.countKey]}</span>
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{s.label}</span>
              </div>
            )
          })}
        </div>

        {/* Per-status student lists */}
        <ScrollArea className="h-[calc(100%-6rem)]">
          <div className="space-y-4 pr-3">
            {STATUSES.map((s) => {
              const list = summary[s.key] ?? []
              if (list.length === 0) return null
              return (
                <div key={s.key}>
                  <div className="mb-1 flex items-center gap-2">
                    <Badge variant="outline" className={s.badgeClass}>
                      {s.label} · {list.length}
                    </Badge>
                  </div>
                  <div className="divide-y">
                    {list.map((entry) => (
                      <StudentRow
                        key={entry.user_id}
                        entry={entry}
                        showCheckIn={s.key === 'present' || s.key === 'late'}
                        showEarlyLeave={s.key === 'early_leave' || s.key === 'early_leave_returned'}
                        onSelect={onSelect}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

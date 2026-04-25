import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import {
  AlertTriangle,
  BookOpen,
  Camera,
  CheckCircle2,
  Copy,
  ExternalLink,
  Info,
  X,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { formatTimestampWithMs } from '@/lib/format-time'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  formatEventSummary,
  methodologyFor,
} from '@/lib/activity-format'
import type { ActivityEvent, ActivitySeverity } from '@/types'

interface EventDetailSheetProps {
  event: ActivityEvent | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Color tokens matching the event-row severity rail in the list view.
// Keeping these in lockstep with index.tsx is intentional — the sheet is
// the click-through detail of a row, so the same severity should look
// identical on both surfaces.
const severityBadgeClass: Record<ActivitySeverity, string> = {
  info: 'bg-muted text-foreground',
  success:
    'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
  warn: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200',
  error: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
}

const severityRailClass: Record<ActivitySeverity, string> = {
  info: 'bg-border',
  success: 'bg-emerald-500',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
}

const severityIcon: Record<ActivitySeverity, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  warn: AlertTriangle,
  error: XCircle,
}

/**
 * Side sheet showing the full payload of one activity event plus
 * context-aware drilldown links into related admin pages.
 *
 * UX principles:
 * - Severity rail + icon mirror the list row so navigating in/out feels
 *   continuous.
 * - Every UUID is copyable in one click — they're useless to read but
 *   essential to paste into another admin tool or a SQL console.
 * - Drilldowns are prominent (above the JSON dump) so the typical
 *   triage flow is one click away.
 * - The JSON payload is collapsible-by-truncation rather than
 *   collapsible-by-toggle: anything beyond 40vh scrolls in place,
 *   keeping the rest of the sheet anchored.
 */
export function EventDetailSheet({
  event,
  open,
  onOpenChange,
}: EventDetailSheetProps) {
  if (!event) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="sm:max-w-xl" />
      </Sheet>
    )
  }

  const SeverityIcon = severityIcon[event.severity]
  const drilldowns = computeDrilldowns(event)
  const created = new Date(event.created_at)
  const methodology = methodologyFor(event.event_type)
  const displaySummary = formatEventSummary(event)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-xl overflow-y-auto p-0">
        {/* Severity rail + header. Rail mirrors the list-view rail so
            clicking through an event feels like a focus zoom, not a
            context switch. */}
        <div className="flex items-stretch">
          <div
            className={`w-1 shrink-0 ${severityRailClass[event.severity]}`}
          />
          <div className="flex-1 px-6 pt-6 pb-4">
            <SheetHeader className="space-y-2 p-0 text-left">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <SeverityIcon
                      className={`h-4 w-4 shrink-0 ${
                        event.severity === 'error'
                          ? 'text-red-600 dark:text-red-400'
                          : event.severity === 'warn'
                            ? 'text-amber-600 dark:text-amber-400'
                            : event.severity === 'success'
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : 'text-muted-foreground'
                      }`}
                    />
                    <SheetTitle className="truncate font-mono text-sm tracking-wide">
                      {event.event_type}
                    </SheetTitle>
                  </div>
                  <SheetDescription className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span className="font-mono tabular-nums">
                      {formatTimestampWithMs(created)}
                    </span>
                    <span className="text-muted-foreground/70">·</span>
                    <span className="text-muted-foreground/80">
                      {formatDistanceToNow(created, { addSuffix: true })}
                    </span>
                  </SheetDescription>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0"
                  onClick={() => onOpenChange(false)}
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                <Badge variant="outline" className="capitalize">
                  {event.category}
                </Badge>
                <Badge className={severityBadgeClass[event.severity]}>
                  {event.severity}
                </Badge>
                <Badge variant="secondary" className="font-mono text-[10px]">
                  actor: {event.actor_type}
                </Badge>
              </div>
            </SheetHeader>
          </div>
        </div>

        <div className="px-6 pb-8 space-y-5">
          <Section title="Summary">
            <p className="text-sm leading-relaxed">{displaySummary}</p>
          </Section>

          {methodology && (
            <Section
              title={
                <span className="inline-flex items-center gap-1.5">
                  <BookOpen className="h-3 w-3" />
                  Methodology
                </span>
              }
            >
              <div className="rounded-md border bg-muted/40 p-3 space-y-2 text-sm">
                <p className="font-medium">{methodology.title}</p>
                {methodology.body.map((para, i) => (
                  <p
                    key={i}
                    className="text-muted-foreground leading-relaxed"
                  >
                    {para}
                  </p>
                ))}
                {methodology.formula && (
                  <pre className="bg-background border rounded p-2 text-xs font-mono whitespace-pre-wrap break-words">
                    {methodology.formula}
                  </pre>
                )}
              </div>
            </Section>
          )}

          {(event.actor_name ||
            event.subject_user_name ||
            event.subject_schedule_subject ||
            event.camera_id) && (
            <Section title="Context">
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
                {event.actor_name && (
                  <>
                    <dt className="text-muted-foreground">Actor</dt>
                    <dd>{event.actor_name}</dd>
                  </>
                )}
                {event.subject_user_name && (
                  <>
                    <dt className="text-muted-foreground">Subject</dt>
                    <dd>{event.subject_user_name}</dd>
                  </>
                )}
                {event.subject_schedule_subject && (
                  <>
                    <dt className="text-muted-foreground">Schedule</dt>
                    <dd>{event.subject_schedule_subject}</dd>
                  </>
                )}
                {event.camera_id && (
                  <>
                    <dt className="text-muted-foreground">Camera</dt>
                    <dd className="inline-flex items-center gap-1.5 font-mono text-xs">
                      <Camera className="h-3 w-3 shrink-0 text-muted-foreground" />
                      {event.camera_id}
                    </dd>
                  </>
                )}
              </dl>
            </Section>
          )}

          {drilldowns.length > 0 && (
            <Section title="Drill-down">
              <div className="flex flex-col gap-1">
                {drilldowns.map((d) => (
                  <Link
                    key={d.href}
                    to={d.href}
                    className="inline-flex items-center gap-2 rounded px-2 py-1 -mx-2 text-sm text-primary hover:bg-muted hover:underline"
                    onClick={() => onOpenChange(false)}
                  >
                    <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                    {d.label}
                  </Link>
                ))}
              </div>
            </Section>
          )}

          {event.payload && Object.keys(event.payload).length > 0 && (
            <Section
              title="Payload"
              right={
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => copyJson(event.payload)}
                >
                  <Copy className="h-3 w-3 mr-1" />
                  Copy JSON
                </Button>
              }
            >
              <pre className="bg-muted rounded-md p-3 text-xs overflow-auto max-h-[40vh] whitespace-pre-wrap break-all">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </Section>
          )}

          <Section title="Identifiers">
            <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-xs">
              <IdRow label="event_id" value={event.event_id} />
              {event.actor_id && (
                <IdRow label="actor_id" value={event.actor_id} />
              )}
              {event.subject_user_id && (
                <IdRow
                  label="subject_user_id"
                  value={event.subject_user_id}
                />
              )}
              {event.subject_schedule_id && (
                <IdRow
                  label="subject_schedule_id"
                  value={event.subject_schedule_id}
                />
              )}
              {event.subject_room_id && (
                <IdRow
                  label="subject_room_id"
                  value={event.subject_room_id}
                />
              )}
              {event.ref_attendance_id && (
                <IdRow
                  label="ref_attendance_id"
                  value={event.ref_attendance_id}
                />
              )}
              {event.ref_early_leave_id && (
                <IdRow
                  label="ref_early_leave_id"
                  value={event.ref_early_leave_id}
                />
              )}
              {event.ref_recognition_event_id && (
                <IdRow
                  label="ref_recognition"
                  value={event.ref_recognition_event_id}
                />
              )}
            </dl>
          </Section>
        </div>
      </SheetContent>
    </Sheet>
  )
}

// ── Sub-components ────────────────────────────────────────────

function Section({
  title,
  right,
  children,
}: {
  title: React.ReactNode
  right?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h3>
        {right}
      </div>
      {children}
    </section>
  )
}

/**
 * One row of the identifier grid. The full UUID is shown in monospace,
 * with a single-click copy button that shows a brief toast confirmation.
 * Hover reveals the button so the row is visually quiet at rest.
 */
function IdRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="font-mono text-muted-foreground self-center">{label}</dt>
      <dd className="group flex items-center gap-2 min-w-0">
        <span className="font-mono break-all text-foreground/90">{value}</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={() => copyText(value, label)}
          aria-label={`Copy ${label}`}
        >
          <Copy className="h-3 w-3" />
        </Button>
      </dd>
    </>
  )
}

// ── Helpers ──────────────────────────────────────────────────

async function copyText(value: string, label: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    toast.success(`Copied ${label}`)
  } catch {
    // navigator.clipboard can fail on http://LAN origins without TLS
    // — the live admin runs over plain HTTP on IAMS-Net, so fall back
    // to the legacy execCommand path before giving up entirely.
    const ok = legacyCopy(value)
    if (ok) toast.success(`Copied ${label}`)
    else toast.error(`Couldn't copy ${label}`)
  }
}

async function copyJson(payload: Record<string, unknown> | null): Promise<void> {
  if (!payload) return
  const text = JSON.stringify(payload, null, 2)
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Payload copied')
  } catch {
    if (legacyCopy(text)) toast.success('Payload copied')
    else toast.error("Couldn't copy payload")
  }
}

function legacyCopy(value: string): boolean {
  try {
    const ta = document.createElement('textarea')
    ta.value = value
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

function computeDrilldowns(
  event: ActivityEvent,
): { href: string; label: string }[] {
  const out: { href: string; label: string }[] = []

  // The student detail route at ``/students/:studentId`` looks up by
  // the human-facing student record number (``User.student_id``, e.g.
  // "JR-2024-001234"), NOT the user UUID. Older events that don't carry
  // ``subject_user_student_id`` would 404 with a UUID. Drop the link
  // entirely in that case rather than producing a known-broken URL.
  if (event.subject_user_student_id) {
    out.push({
      href: `/students/${event.subject_user_student_id}`,
      label: `View student${event.subject_user_name ? ` (${event.subject_user_name})` : ''}`,
    })
  }
  if (event.subject_schedule_id) {
    out.push({
      href: `/schedules/${event.subject_schedule_id}`,
      label: `View schedule${event.subject_schedule_subject ? ` (${event.subject_schedule_subject})` : ''}`,
    })
  }
  if (event.ref_attendance_id && event.subject_schedule_id) {
    out.push({
      href: `/attendance?schedule_id=${event.subject_schedule_id}`,
      label: 'View attendance records',
    })
  }
  if (event.ref_early_leave_id) {
    const params = new URLSearchParams()
    if (event.subject_schedule_id)
      params.set('schedule_id', event.subject_schedule_id)
    if (event.subject_user_id) params.set('student_id', event.subject_user_id)
    const qs = params.toString()
    out.push({
      href: `/early-leaves${qs ? `?${qs}` : ''}`,
      label: 'View early-leave alert',
    })
  }
  if (event.ref_recognition_event_id) {
    const params = new URLSearchParams()
    if (event.subject_user_id) params.set('student_id', event.subject_user_id)
    if (event.subject_schedule_id)
      params.set('schedule_id', event.subject_schedule_id)
    const qs = params.toString()
    out.push({
      href: `/recognitions${qs ? `?${qs}` : ''}`,
      label: 'View recognition evidence',
    })
  }

  return out
}

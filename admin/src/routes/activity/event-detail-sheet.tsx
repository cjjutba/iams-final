import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { ExternalLink, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import type { ActivityEvent } from '@/types'

interface EventDetailSheetProps {
  event: ActivityEvent | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const severityColor = {
  info: 'bg-muted text-foreground',
  success: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
  warn: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200',
  error: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
} as const

/**
 * Side sheet showing the full payload of one activity event plus
 * context-aware drilldown links into related admin pages.
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

  const drilldowns = computeDrilldowns(event)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-xl overflow-y-auto">
        <SheetHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate">{event.event_type}</SheetTitle>
              <SheetDescription className="mt-1">
                {format(
                  new Date(event.created_at),
                  "EEE MMM d, yyyy · h:mm:ss.SSS a",
                )}
              </SheetDescription>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </SheetHeader>

        <div className="mt-6 space-y-5">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{event.category}</Badge>
            <Badge className={severityColor[event.severity]}>
              {event.severity}
            </Badge>
            <Badge variant="secondary">actor: {event.actor_type}</Badge>
          </div>

          <section>
            <h3 className="text-sm font-semibold text-muted-foreground mb-2">
              Summary
            </h3>
            <p className="text-sm leading-relaxed">{event.summary}</p>
          </section>

          {(event.actor_name || event.subject_user_name || event.subject_schedule_subject) && (
            <section>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                Context
              </h3>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
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
                    <dd className="font-mono text-xs">{event.camera_id}</dd>
                  </>
                )}
              </dl>
            </section>
          )}

          {drilldowns.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                Drill-down
              </h3>
              <div className="flex flex-col gap-1">
                {drilldowns.map((d) => (
                  <Link
                    key={d.href}
                    to={d.href}
                    className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
                    onClick={() => onOpenChange(false)}
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    {d.label}
                  </Link>
                ))}
              </div>
            </section>
          )}

          {event.payload && Object.keys(event.payload).length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                Payload
              </h3>
              <pre className="bg-muted rounded-md p-3 text-xs overflow-auto max-h-[40vh] whitespace-pre-wrap break-all">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </section>
          )}

          <section>
            <h3 className="text-sm font-semibold text-muted-foreground mb-2">
              Identifiers
            </h3>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs font-mono">
              <dt className="text-muted-foreground">event_id</dt>
              <dd className="break-all">{event.event_id}</dd>
              {event.actor_id && (
                <>
                  <dt className="text-muted-foreground">actor_id</dt>
                  <dd className="break-all">{event.actor_id}</dd>
                </>
              )}
              {event.subject_user_id && (
                <>
                  <dt className="text-muted-foreground">subject_user_id</dt>
                  <dd className="break-all">{event.subject_user_id}</dd>
                </>
              )}
              {event.subject_schedule_id && (
                <>
                  <dt className="text-muted-foreground">subject_schedule_id</dt>
                  <dd className="break-all">{event.subject_schedule_id}</dd>
                </>
              )}
              {event.ref_attendance_id && (
                <>
                  <dt className="text-muted-foreground">ref_attendance_id</dt>
                  <dd className="break-all">{event.ref_attendance_id}</dd>
                </>
              )}
              {event.ref_recognition_event_id && (
                <>
                  <dt className="text-muted-foreground">ref_recognition</dt>
                  <dd className="break-all">{event.ref_recognition_event_id}</dd>
                </>
              )}
            </dl>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function computeDrilldowns(
  event: ActivityEvent,
): { href: string; label: string }[] {
  const out: { href: string; label: string }[] = []

  if (event.subject_user_id) {
    out.push({
      href: `/students/${event.subject_user_id}`,
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

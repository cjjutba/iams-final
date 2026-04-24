import { Calendar, Clock, MapPin } from 'lucide-react'
import { format } from 'date-fns'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { formatStatus } from '@/types/attendance'
import type { AttendanceRecord } from '@/types'
import { MatchEvidence } from './MatchEvidence'

interface Props {
  record: AttendanceRecord | null
  studentId: string | null
  studentName?: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const statusVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  present: 'default',
  late: 'secondary',
  absent: 'destructive',
  excused: 'outline',
  early_leave: 'destructive',
}

/**
 * Slide-up details sheet for one attendance record.
 *
 * The top half shows the attendance metadata (status, check-in time,
 * presence score, subject). The bottom half renders <MatchEvidence /> —
 * the full face-recognition evidence trail for that student in that
 * session. Serves as the "why was this marked PRESENT?" answer for
 * admins and parents alike.
 */
export function AttendanceDetailSheet({
  record,
  studentId,
  studentName,
  open,
  onOpenChange,
}: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-xl overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {record ? (record.subject_code ?? 'Attendance') : 'Attendance'}
            {record && (
              <Badge variant={statusVariant[record.status] ?? 'outline'}>
                {formatStatus(record.status)}
              </Badge>
            )}
          </SheetTitle>
          <SheetDescription>
            Recognition evidence for this session.
          </SheetDescription>
        </SheetHeader>

        {record ? (
          <div className="mt-6 space-y-6">
            <MetadataGrid record={record} />

            <Separator />

            <section>
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">
                Face recognition evidence
              </h3>
              {studentId ? (
                <MatchEvidence
                  studentId={studentId}
                  scheduleId={record.schedule_id}
                  studentName={studentName}
                />
              ) : (
                <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
                  Student record has no linked user id — evidence trail unavailable.
                </div>
              )}
            </section>
          </div>
        ) : (
          <div className="mt-6 text-center text-sm text-muted-foreground">
            Select a row to inspect.
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

function MetadataGrid({ record }: { record: AttendanceRecord }) {
  const dateLabel = record.check_in_time
    ? format(new Date(record.check_in_time), 'EEEE, MMM d yyyy')
    : '—'
  const timeLabel = record.check_in_time
    ? format(new Date(record.check_in_time), 'h:mm a')
    : '—'
  const score =
    typeof (record as { presence_score?: number }).presence_score === 'number'
      ? ((record as { presence_score: number }).presence_score * 100).toFixed(1) + '%'
      : '—'

  return (
    <div className="grid grid-cols-2 gap-4">
      <InfoItem icon={Calendar} label="Date" value={dateLabel} />
      <InfoItem icon={Clock} label="Check-in" value={timeLabel} />
      <InfoItem
        icon={MapPin}
        label="Subject"
        value={record.subject_code ?? '—'}
      />
      <InfoItem icon={Clock} label="Presence score" value={score} />
    </div>
  )
}

function InfoItem({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Calendar
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="mt-0.5 h-4 w-4 text-muted-foreground" aria-hidden />
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div className="text-sm font-medium truncate">{value}</div>
      </div>
    </div>
  )
}

import { useMemo } from 'react'
import { format } from 'date-fns'
import { AlertCircle, CheckCircle2, Clock, ImageOff, Loader2 } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router-dom'
import { useRecognitionSummary, useRecognitions } from '@/hooks/use-queries'
import { useAuthedImage } from '@/hooks/use-authed-image'
import type { RecognitionEvent } from '@/types'

interface Props {
  studentId: string
  scheduleId: string
  studentName?: string
}

/**
 * Per-session evidence trail for one student. Renders inside
 * AttendanceDetailSheet to answer the question "why was this person marked
 * PRESENT / LATE / EARLY_LEAVE?" with:
 *
 * - A one-sentence narrative ("Matched 42 times between 1:40pm and 2:15pm,
 *   peak similarity 0.78, threshold 0.30").
 * - The best-match live+registered crop pair.
 * - A 20-bucket histogram over similarity scores for the session.
 * - A minute-by-minute density sparkline so an admin can see where matches
 *   clustered or dropped off.
 *
 * Signatures on the /recognitions audit page for deep-dives.
 */
export function MatchEvidence({ studentId, scheduleId, studentName }: Props) {
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
  } = useRecognitionSummary(studentId, scheduleId)

  // One extra call for the best-match row so we can render the crop pair.
  const bestEventId = summary?.best_match?.event_id
  const { data: bestEvent } = useRecognitions({
    student_id: studentId,
    schedule_id: scheduleId,
    limit: 1,
    matched: true,
  })
  const bestEventFromList = bestEvent?.items?.[0] ?? null
  // Prefer summary-reported best — fall back to list top.
  const featuredEvent = useMemo<RecognitionEvent | null>(() => {
    if (!bestEventId) return bestEventFromList
    return bestEventFromList
  }, [bestEventId, bestEventFromList])

  if (summaryLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  if (summaryError) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed border-amber-500/40 p-4 text-sm text-amber-600 dark:text-amber-500">
        <AlertCircle className="h-4 w-4" aria-hidden />
        Failed to load match evidence.
      </div>
    )
  }

  if (!summary || summary.match_count + summary.miss_count === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
        <Clock className="h-6 w-6" aria-hidden />
        <span>No recognition events recorded for this session</span>
        <span className="text-xs">
          Either the pipeline was not running, or retention pruned the evidence.
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <Narrative summary={summary} studentName={studentName} />

      {featuredEvent && <PeakEvidence event={featuredEvent} />}

      <Histogram
        buckets={summary.histogram}
        threshold={summary.threshold_at_session}
      />

      {summary.timeline.length > 1 && <Timeline buckets={summary.timeline} />}

      <div className="flex justify-end">
        <Link
          to={`/recognitions?student_id=${studentId}&schedule_id=${scheduleId}`}
        >
          <Button variant="outline" size="sm">
            See all matches
          </Button>
        </Link>
      </div>
    </div>
  )
}

function Narrative({
  summary,
  studentName,
}: {
  summary: NonNullable<ReturnType<typeof useRecognitionSummary>['data']>
  studentName?: string
}) {
  const who = studentName || 'Student'
  const first = summary.first_match?.timestamp
    ? format(new Date(summary.first_match.timestamp), 'h:mm a')
    : null
  const last = summary.last_match?.timestamp
    ? format(new Date(summary.last_match.timestamp), 'h:mm a')
    : null
  const peak = summary.best_match?.similarity
  const threshold = summary.threshold_at_session
  return (
    <div className="flex items-start gap-2 rounded-md border bg-muted/30 p-3 text-sm">
      <CheckCircle2 className="h-4 w-4 text-green-600 mt-0.5" aria-hidden />
      <div className="flex-1">
        <p>
          <span className="font-medium">{who}</span> matched{' '}
          <span className="font-mono">{summary.match_count}</span> time
          {summary.match_count === 1 ? '' : 's'}
          {first && last ? (
            <>
              {' '}between <span className="font-mono">{first}</span> and{' '}
              <span className="font-mono">{last}</span>
            </>
          ) : null}
          {peak !== undefined && peak !== null ? (
            <>
              . Peak similarity{' '}
              <span className="font-mono">{(peak * 100).toFixed(1)}%</span>
            </>
          ) : null}
          {threshold !== null && threshold !== undefined ? (
            <>
              {' '}(threshold{' '}
              <span className="font-mono">{(threshold * 100).toFixed(0)}%</span>)
            </>
          ) : null}
          .
        </p>
        {summary.miss_count > 0 && (
          <p className="mt-1 text-xs text-muted-foreground">
            {summary.miss_count} miss{summary.miss_count === 1 ? '' : 'es'} also recorded.
          </p>
        )}
      </div>
    </div>
  )
}

function PeakEvidence({ event }: { event: RecognitionEvent }) {
  const similarity = Math.max(0, Math.min(1, event.similarity))
  const threshold = Math.max(0, Math.min(1, event.threshold_used))
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium">Peak match</span>
        <Badge variant={event.matched ? 'default' : 'secondary'}>
          sim {(similarity * 100).toFixed(1)}%
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <CropPane
          url={event.crop_urls.live}
          label="Captured from camera"
          emptyLabel="Live crop not on disk"
        />
        <CropPane
          url={event.crop_urls.registered}
          label="Registered angle"
          emptyLabel="No registered crop yet"
        />
      </div>
      <div className="mt-3 text-xs text-muted-foreground">
        {event.camera_id} · {format(new Date(event.created_at), 'MMM d, h:mm:ss a')} · model {event.model_name}
      </div>
      <ScoreBar score={similarity} threshold={threshold} matched={event.matched} />
    </div>
  )
}

function CropPane({
  url,
  label,
  emptyLabel,
}: {
  url: string | null
  label: string
  emptyLabel: string
}) {
  const { src, loading, error } = useAuthedImage(url)

  if (!url) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-1 rounded border border-dashed text-center text-xs text-muted-foreground">
        <span>{emptyLabel}</span>
      </div>
    )
  }

  return (
    <figure className="flex flex-col gap-1">
      <div className="relative h-40 overflow-hidden rounded border bg-muted/30">
        {error && (
          <div
            className="flex h-full w-full items-center justify-center text-muted-foreground"
            title={error.message}
          >
            <ImageOff className="h-6 w-6" aria-hidden />
          </div>
        )}
        {!error && (loading || !src) && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          </div>
        )}
        {!error && src && (
          <img
            src={src}
            alt={label}
            className="h-full w-full object-contain"
          />
        )}
      </div>
      <figcaption className="text-[11px] text-muted-foreground text-center">
        {label}
      </figcaption>
    </figure>
  )
}

function ScoreBar({
  score,
  threshold,
  matched,
}: {
  score: number
  threshold: number
  matched: boolean
}) {
  const color = matched ? 'bg-green-500' : 'bg-orange-400'
  return (
    <div className="mt-2 relative h-2 w-full overflow-hidden rounded bg-muted">
      <div className={`h-full ${color}`} style={{ width: `${score * 100}%` }} />
      <div
        className="absolute top-0 h-full w-px bg-foreground/80"
        style={{ left: `${threshold * 100}%` }}
      />
    </div>
  )
}

function Histogram({
  buckets,
  threshold,
}: {
  buckets: number[]
  threshold: number | null
}) {
  const max = Math.max(1, ...buckets)
  const thresholdBucket =
    threshold !== null && threshold !== undefined
      ? Math.max(0, Math.min(buckets.length - 1, Math.floor(threshold * buckets.length)))
      : null
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium">Similarity distribution</span>
        {threshold !== null && threshold !== undefined && (
          <span className="text-[11px] text-muted-foreground">
            Threshold line at {(threshold * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div className="flex h-20 items-end gap-[2px]">
        {buckets.map((count, i) => {
          const h = Math.max(2, (count / max) * 80)
          const isThresholdBucket = i === thresholdBucket
          return (
            <div
              key={i}
              className={`flex-1 ${isThresholdBucket ? 'bg-foreground/70' : 'bg-primary/70'}`}
              style={{ height: `${h}px` }}
              title={`Bucket ${(i / buckets.length).toFixed(2)}–${((i + 1) / buckets.length).toFixed(2)}: ${count}`}
            />
          )
        })}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>0.0</span>
        <span>1.0</span>
      </div>
    </div>
  )
}

function Timeline({
  buckets,
}: {
  buckets: { minute: string; matches: number; misses: number }[]
}) {
  const maxTotal = Math.max(1, ...buckets.map((b) => b.matches + b.misses))
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium">Match density (per minute)</span>
      </div>
      <div className="flex h-12 items-end gap-[1px]">
        {buckets.map((b, i) => {
          const total = b.matches + b.misses
          const h = Math.max(1, (total / maxTotal) * 48)
          const matchRatio = total ? b.matches / total : 0
          return (
            <div
              key={i}
              className="flex-1 overflow-hidden bg-muted"
              style={{ height: `${h}px` }}
              title={`${b.minute}: ${b.matches} matches, ${b.misses} misses`}
            >
              <div
                className="bg-green-500"
                style={{ height: `${matchRatio * 100}%` }}
              />
            </div>
          )
        })}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>{buckets[0]?.minute ? format(new Date(buckets[0].minute), 'h:mm a') : '—'}</span>
        <span>{buckets[buckets.length - 1]?.minute ? format(new Date(buckets[buckets.length - 1].minute), 'h:mm a') : '—'}</span>
      </div>
    </div>
  )
}

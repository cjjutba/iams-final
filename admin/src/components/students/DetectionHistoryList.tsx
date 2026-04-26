import { useState } from 'react'
import { formatTimestamp, formatFullDatetime } from '@/lib/format-time'
import { AlertTriangle, Clock, ImageOff, Loader2, Radio } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthedImage } from '@/hooks/use-authed-image'
import { useStudentRecognitionWs } from '@/hooks/use-student-recognition-ws'
import { cn } from '@/lib/utils'
import type { RecognitionEvent } from '@/types'

interface Props {
  studentId: string
  /** Visible row cap. Older events stay in the underlying buffer. */
  limit?: number
}

/**
 * Per-student "Recent Detections" column rendered inside the Face
 * Verification card on the Student Record Detail page.
 *
 * Data source is the realtime per-student WebSocket — see
 * `useStudentRecognitionWs` for REST backfill + WS push + dedup details.
 * The list updates live as the pipeline fires new recognition events for
 * this student, no polling and no page refresh required.
 *
 * Each row shows the live probe crop, a score bar with the threshold
 * marker, and the timestamp/subject/camera. Matched events link their
 * registered-angle crop so the admin can visually confirm similarity.
 */
export function DetectionHistoryList({ studentId, limit = 10 }: Props) {
  const [showMore, setShowMore] = useState(false)
  const { events, isConnected, isLoading, error } =
    useStudentRecognitionWs(studentId)

  if (isLoading && events.length === 0) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    )
  }

  if (error && events.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-amber-500/40 p-6 text-center text-sm text-amber-600 dark:text-amber-500">
        <AlertTriangle className="h-6 w-6" aria-hidden />
        <span>Failed to load detection history</span>
        <span className="text-xs text-muted-foreground">{error.message}</span>
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
        <Clock className="h-6 w-6" aria-hidden />
        <span>No detections yet</span>
        <span className="text-xs">
          Events will appear as the pipeline recognizes this student in class.
        </span>
        <ConnectionDot isConnected={isConnected} />
      </div>
    )
  }

  // The WS buffer holds up to 200 events; show `limit` by default then let
  // the user expand inline up to the full buffer. Older events fall off the
  // back as new ones arrive — that's acceptable for a "recent" view.
  const expandedCap = Math.min(events.length, Math.max(50, limit * 5))
  const visibleCount = showMore ? expandedCap : Math.min(limit, events.length)
  const visible = events.slice(0, visibleCount)
  const canExpand = !showMore && events.length > visibleCount

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <ConnectionDot isConnected={isConnected} />
        <span className="text-[11px] text-muted-foreground">
          {visible.length} of {events.length}
        </span>
      </div>
      <ul className="flex flex-col gap-2 max-h-[480px] overflow-y-auto pr-1">
        {visible.map((event) => (
          <DetectionRow key={event.event_id} event={event} />
        ))}
      </ul>
      {canExpand && (
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => setShowMore(true)}
        >
          Show more
        </Button>
      )}
      {showMore && events.length >= expandedCap && (
        <div className="text-center text-[11px] text-muted-foreground">
          Showing {visible.length} recent detections — open the audit page for full history.
        </div>
      )}
    </div>
  )
}

function ConnectionDot({ isConnected }: { isConnected: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-[11px]',
        isConnected ? 'text-emerald-600 dark:text-emerald-500' : 'text-muted-foreground',
      )}
      title={isConnected ? 'Live — updates in real time' : 'Disconnected — showing cached results'}
    >
      <Radio className={cn('h-3 w-3', isConnected && 'animate-pulse')} aria-hidden />
      {isConnected ? 'Live' : 'Offline'}
    </span>
  )
}

function DetectionRow({ event }: { event: RecognitionEvent }) {
  const score = Math.max(0, Math.min(1, event.similarity))
  const threshold = Math.max(0, Math.min(1, event.threshold_used))
  const matched = event.matched

  return (
    <li className="flex gap-3 rounded-md border bg-muted/10 p-2">
      <CropThumbnail url={event.crop_urls.live} alt="Live capture" />
      <div className="flex flex-1 flex-col justify-between gap-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium">
            {event.schedule_subject ?? 'Schedule'}
            <span className="ml-1 text-muted-foreground">· {event.camera_id}</span>
          </span>
          <MatchBadge matched={matched} ambiguous={event.is_ambiguous} />
        </div>
        <ScoreBar score={score} threshold={threshold} matched={matched} />
        <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
          <span
            title={formatFullDatetime(event.created_at)}
            className="font-mono tabular-nums"
          >
            {formatTimestamp(event.created_at)}
          </span>
          <span className="font-mono">
            sim {(score * 100).toFixed(1)}% / thr {(threshold * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </li>
  )
}

function CropThumbnail({ url, alt }: { url: string; alt: string }) {
  // The crop endpoint is Bearer-auth protected; a plain <img> cannot send
  // the Authorization header. useAuthedImage fetches through Axios and
  // hands us a same-origin blob URL to display.
  const { src, loading, error } = useAuthedImage(url)

  if (error) {
    return (
      <div
        className="flex h-16 w-16 items-center justify-center rounded border bg-muted text-muted-foreground"
        title={`Failed to load crop: ${error.message}`}
      >
        <ImageOff className="h-4 w-4" aria-hidden />
      </div>
    )
  }

  return (
    <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded border bg-muted/50">
      {(loading || !src) && (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        </div>
      )}
      {src && (
        <img
          src={src}
          alt={alt}
          className="h-full w-full object-cover"
        />
      )}
    </div>
  )
}

function MatchBadge({ matched, ambiguous }: { matched: boolean; ambiguous: boolean }) {
  if (ambiguous) return <Badge variant="outline" className="text-amber-600">Ambiguous</Badge>
  if (matched) return <Badge variant="default">Match</Badge>
  return <Badge variant="secondary">Miss</Badge>
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
  const fillColor = matched ? 'bg-green-500' : 'bg-orange-400'
  return (
    <div className="relative h-2 w-full overflow-hidden rounded bg-muted">
      <div
        className={`h-full ${fillColor}`}
        style={{ width: `${score * 100}%` }}
      />
      <div
        className="absolute top-0 h-full w-px bg-foreground/80"
        style={{ left: `${threshold * 100}%` }}
        title={`Threshold ${(threshold * 100).toFixed(0)}%`}
      />
    </div>
  )
}

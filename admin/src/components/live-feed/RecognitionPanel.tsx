import { useEffect, useMemo, useRef, useState } from 'react'
import { Pause, Play, ScanSearch } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuthedImage } from '@/hooks/use-authed-image'
import { formatTimestamp, formatFullDatetime } from '@/lib/format-time'
import type { RecognitionEventMessage } from '@/hooks/use-attendance-ws'

type Filter = 'all' | 'matched' | 'missed' | 'ambiguous'

interface Props {
  events: RecognitionEventMessage[]
  scheduleId: string
}

/**
 * Live-streaming view of every FAISS decision for the current schedule.
 *
 * Mounted on /schedules/:id/live next to the video. Subscribes to the
 * attendance WS channel's `recognition_event` messages via the parent's
 * useAttendanceWs hook. The panel keeps its own paused-buffer so an
 * admin can freeze the stream to point at a frame during a demo.
 *
 * Rows render:
 * - live crop thumbnail
 * - student name / "Unknown" / "Ambiguous" badge
 * - similarity score bar with threshold marker
 * - track id, camera, relative timestamp
 */
export function RecognitionPanel({ events, scheduleId: _scheduleId }: Props) {
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [minSim, setMinSim] = useState(0)
  // When paused, we snapshot the events array so new incoming events don't
  // drift the list under the admin's eyes.
  const snapshotRef = useRef<RecognitionEventMessage[]>([])

  useEffect(() => {
    if (!paused) {
      snapshotRef.current = events
    }
  }, [events, paused])

  const visible = useMemo(() => {
    const source = paused ? snapshotRef.current : events
    return source.filter((e) => {
      if (filter === 'matched' && !e.matched) return false
      if (filter === 'missed' && e.matched) return false
      if (filter === 'ambiguous' && !e.is_ambiguous) return false
      if (e.similarity < minSim) return false
      return true
    })
  }, [events, paused, filter, minSim])

  const total = events.length
  const filteredCount = visible.length

  return (
    <div className="flex h-full flex-col rounded-md border bg-card">
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <ScanSearch className="h-4 w-4 text-muted-foreground" aria-hidden />
        <h3 className="text-sm font-medium">Recognition stream</h3>
        <span className="ml-auto text-[11px] text-muted-foreground">
          {filteredCount} / {total}
        </span>
      </header>

      <div className="flex items-center gap-2 border-b bg-muted/30 px-3 py-2">
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-2"
          onClick={() => setPaused((p) => !p)}
        >
          {paused ? (
            <>
              <Play className="mr-1 h-3 w-3" />
              Resume
            </>
          ) : (
            <>
              <Pause className="mr-1 h-3 w-3" />
              Pause
            </>
          )}
        </Button>
        <Select value={filter} onValueChange={(v) => setFilter(v as Filter)}>
          <SelectTrigger className="h-7 w-32 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="matched">Matched</SelectItem>
            <SelectItem value="missed">Missed</SelectItem>
            <SelectItem value="ambiguous">Ambiguous</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Min sim
          </span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(minSim * 100)}
            onChange={(e) => setMinSim(parseInt(e.target.value, 10) / 100)}
            className="h-1 w-24 cursor-pointer"
          />
          <span className="w-8 font-mono text-[10px] text-muted-foreground">
            {Math.round(minSim * 100)}%
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {visible.length === 0 ? (
          <EmptyState total={total} paused={paused} />
        ) : (
          <ul className="divide-y">
            {visible.map((evt) => (
              <RecognitionRow key={evt.event_id} event={evt} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function EmptyState({ total, paused }: { total: number; paused: boolean }) {
  if (total === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 py-12 text-center text-sm text-muted-foreground">
        <span>Waiting for recognition events…</span>
        <span className="text-xs">
          Events will appear as soon as the pipeline makes a decision.
        </span>
      </div>
    )
  }
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 py-12 text-center text-sm text-muted-foreground">
      <span>No events match the current filter.</span>
      {paused && <span className="text-xs">Feed paused · adjust filter or resume.</span>}
    </div>
  )
}

function RecognitionRow({ event }: { event: RecognitionEventMessage }) {
  const similarity = Math.max(0, Math.min(1, event.similarity))
  const threshold = Math.max(0, Math.min(1, event.threshold_used))
  const when = new Date(event.server_time_ms || Date.now())
  const name = event.student_name ?? (event.matched ? 'Unknown' : null)

  return (
    <li className="flex gap-2 px-3 py-2">
      <CropThumbnail url={event.crop_urls.live} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-xs font-medium">
            {name ?? 'Unmatched'}
          </span>
          <OutcomeBadge
            matched={event.matched}
            ambiguous={event.is_ambiguous}
          />
        </div>
        <ScoreBar score={similarity} threshold={threshold} matched={event.matched} />
        <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
          <span className="truncate">
            track #{event.track_id} · {event.camera_id}
          </span>
          <span title={formatFullDatetime(when)} className="font-mono tabular-nums">
            sim {(similarity * 100).toFixed(1)}% · {formatTimestamp(when)}
          </span>
        </div>
      </div>
    </li>
  )
}

function CropThumbnail({ url }: { url: string }) {
  const { src, error } = useAuthedImage(url)
  if (error || !src) {
    return <div className="h-12 w-12 shrink-0 rounded border bg-muted/30" />
  }
  return (
    <img
      src={src}
      alt="live crop"
      className="h-12 w-12 shrink-0 rounded border object-cover"
    />
  )
}

function OutcomeBadge({
  matched,
  ambiguous,
}: {
  matched: boolean
  ambiguous: boolean
}) {
  if (ambiguous)
    return (
      <Badge variant="outline" className="text-[10px] text-amber-600">
        Ambiguous
      </Badge>
    )
  if (matched) return <Badge variant="default" className="text-[10px]">Match</Badge>
  return <Badge variant="secondary" className="text-[10px]">Miss</Badge>
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
  const fill = matched ? 'bg-green-500' : 'bg-orange-400'
  return (
    <div className="relative mt-1 h-1.5 w-full overflow-hidden rounded bg-muted">
      <div className={`h-full ${fill}`} style={{ width: `${score * 100}%` }} />
      <div
        className="absolute top-0 h-full w-px bg-foreground/70"
        style={{ left: `${threshold * 100}%` }}
      />
    </div>
  )
}

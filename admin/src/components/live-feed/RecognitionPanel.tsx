import { useEffect, useMemo, useRef, useState } from 'react'
import { Pause, Play } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
 * Subscribes (via the parent's useAttendanceWs hook) to the attendance
 * WS channel's recognition_event messages. Keeps its own paused-buffer
 * so an admin can freeze the list to point at a specific row during a
 * demo without new arrivals scrolling it away.
 */
export function RecognitionPanel({ events, scheduleId: _scheduleId }: Props) {
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [minSim, setMinSim] = useState(0)
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
    <Card className="flex h-full flex-col">
      <CardHeader className="gap-2 pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Recognition stream</CardTitle>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {filteredCount} / {total}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
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
            <SelectTrigger size="sm" className="h-7 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="matched">Matched</SelectItem>
              <SelectItem value="missed">Missed</SelectItem>
              <SelectItem value="ambiguous">Ambiguous</SelectItem>
            </SelectContent>
          </Select>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Min sim
            </span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(minSim * 100)}
              onChange={(e) => setMinSim(parseInt(e.target.value, 10) / 100)}
              className="h-1 w-20 cursor-pointer accent-primary"
              aria-label="Minimum similarity filter"
            />
            <span className="w-7 font-mono text-[10px] tabular-nums text-muted-foreground">
              {Math.round(minSim * 100)}%
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-hidden p-0">
        <div className="h-full overflow-y-auto">
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
      </CardContent>
    </Card>
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
    <li className="flex gap-3 px-4 py-2.5">
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
    return <div className="h-12 w-12 shrink-0 rounded-md border bg-muted/30" />
  }
  return (
    <img
      src={src}
      alt="live crop"
      className="h-12 w-12 shrink-0 rounded-md border object-cover"
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
      <Badge
        variant="outline"
        className="border-amber-500/30 bg-amber-500/10 text-[10px] text-amber-700 dark:text-amber-400"
      >
        Ambiguous
      </Badge>
    )
  if (matched)
    return (
      <Badge
        variant="outline"
        className="border-emerald-500/30 bg-emerald-500/10 text-[10px] text-emerald-700 dark:text-emerald-400"
      >
        Match
      </Badge>
    )
  return (
    <Badge variant="outline" className="text-[10px] text-muted-foreground">
      Miss
    </Badge>
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
  const fill = matched ? 'bg-emerald-500' : 'bg-orange-400'
  return (
    <div className="relative mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div className={`h-full ${fill}`} style={{ width: `${score * 100}%` }} />
      <div
        className="absolute top-0 h-full w-px bg-foreground/70"
        style={{ left: `${threshold * 100}%` }}
      />
    </div>
  )
}

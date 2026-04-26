import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
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
 * Horizontal recognition timeline shown directly under the live video.
 *
 * Replaces the right-rail vertical RecognitionPanel. Each decision is a
 * compact tile — avatar + name + sim bar + timestamp — and tiles scroll
 * left-to-right (newest on the left). Fixed height (~150px) so the video
 * keeps most of the vertical real estate, and the strip remains visible
 * even with a long roster on the right rail.
 */
export function RecognitionStrip({ events, scheduleId: _scheduleId }: Props) {
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [minSim, setMinSim] = useState(0)
  const snapshotRef = useRef<RecognitionEventMessage[]>([])
  const scrollerRef = useRef<HTMLDivElement | null>(null)

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

  // Programmatic horizontal scroll on the chevron buttons. Tile width
  // (~152 px including gap) × ~3 = a comfortable "one page" jump.
  const scrollByTiles = (direction: -1 | 1) => {
    const el = scrollerRef.current
    if (!el) return
    el.scrollBy({ left: direction * 460, behavior: 'smooth' })
  }

  return (
    <Card className="flex flex-col gap-2 p-3">
      {/* Header row: title + counter on the left, controls on the right. */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">Recognition stream</span>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {filteredCount} / {total}
          </span>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
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
          <div className="flex items-center gap-1.5">
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
          <div className="flex items-center gap-0.5">
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => scrollByTiles(-1)}
              aria-label="Scroll older"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => scrollByTiles(1)}
              aria-label="Scroll newer"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Horizontal tile rail */}
      {visible.length === 0 ? (
        <EmptyState total={total} paused={paused} />
      ) : (
        <div
          ref={scrollerRef}
          className="flex gap-2 overflow-x-auto overflow-y-hidden scroll-smooth pb-1"
          // Tile-snap so a manual swipe lands cleanly on a tile boundary.
          style={{ scrollSnapType: 'x mandatory' }}
        >
          {visible.map((evt) => (
            <RecognitionTile key={evt.event_id} event={evt} />
          ))}
        </div>
      )}
    </Card>
  )
}

function EmptyState({ total, paused }: { total: number; paused: boolean }) {
  return (
    <div className="flex h-[110px] flex-col items-center justify-center gap-1 px-6 text-center text-xs text-muted-foreground">
      {total === 0 ? (
        <>
          <span>Waiting for recognition events…</span>
          <span className="text-[11px] opacity-80">
            Tiles appear as soon as the pipeline makes a decision.
          </span>
        </>
      ) : (
        <>
          <span>No events match the current filter.</span>
          {paused && <span className="text-[11px] opacity-80">Feed paused · adjust filter or resume.</span>}
        </>
      )}
    </div>
  )
}

function RecognitionTile({ event }: { event: RecognitionEventMessage }) {
  const similarity = Math.max(0, Math.min(1, event.similarity))
  const threshold = Math.max(0, Math.min(1, event.threshold_used))
  const when = new Date(event.server_time_ms || Date.now())
  const name = event.student_name ?? (event.matched ? 'Unknown' : null)

  return (
    <div
      className="flex w-[180px] shrink-0 flex-col gap-1.5 rounded-md border bg-card p-2"
      style={{ scrollSnapAlign: 'start' }}
      title={formatFullDatetime(when)}
    >
      <div className="flex items-start gap-2">
        <CropThumbnail url={event.crop_urls.live} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-1.5">
            <span className="line-clamp-2 break-words text-xs font-medium leading-tight">
              {name ?? 'Unmatched'}
            </span>
          </div>
          <div className="mt-0.5">
            <OutcomeBadge matched={event.matched} ambiguous={event.is_ambiguous} />
          </div>
        </div>
      </div>
      <ScoreBar score={similarity} threshold={threshold} matched={event.matched} />
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="truncate" title={`track #${event.track_id} · ${event.camera_id}`}>
          #{event.track_id} · {event.camera_id}
        </span>
        <span className="shrink-0 font-mono tabular-nums">
          {(similarity * 100).toFixed(1)}%
        </span>
      </div>
      <div className="text-right font-mono text-[10px] tabular-nums text-muted-foreground/80">
        {formatTimestamp(when)}
      </div>
    </div>
  )
}

function CropThumbnail({ url }: { url: string }) {
  const { src, error } = useAuthedImage(url)
  if (error || !src) {
    return <div className="h-11 w-11 shrink-0 rounded-md border bg-muted/30" />
  }
  return (
    <img
      src={src}
      alt="live crop"
      className="h-11 w-11 shrink-0 rounded-md border object-cover"
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
        className="h-4 border-amber-500/30 bg-amber-500/10 px-1 text-[9px] leading-none text-amber-700 dark:text-amber-400"
      >
        Ambiguous
      </Badge>
    )
  if (matched)
    return (
      <Badge
        variant="outline"
        className="h-4 border-emerald-500/30 bg-emerald-500/10 px-1 text-[9px] leading-none text-emerald-700 dark:text-emerald-400"
      >
        Match
      </Badge>
    )
  return (
    <Badge
      variant="outline"
      className="h-4 px-1 text-[9px] leading-none text-muted-foreground"
    >
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
    <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div className={`h-full ${fill}`} style={{ width: `${score * 100}%` }} />
      <div
        className="absolute top-0 h-full w-px bg-foreground/70"
        style={{ left: `${threshold * 100}%` }}
      />
    </div>
  )
}

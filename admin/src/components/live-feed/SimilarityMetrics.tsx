import { useEffect, useState } from 'react'
import { WifiOff } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { TrackInfo } from '@/hooks/use-attendance-ws'

interface Props {
  track: TrackInfo | null
  /** Fallback when the sheet was opened via a roster row with no live track. */
  fallbackUserId: string | null
  fallbackName: string | null
  isConnected: boolean
  /** `performance.now()` of last WS frame that contained this track. */
  lastSeenAtMs: number | null
  /** True when the selected track is no longer in `latestFrame.tracks`. */
  isStale: boolean
}

// Matches backend `settings.RECOGNITION_THRESHOLD` (0.38) — close enough for a
// visual threshold marker. Updated 2026-04-22 when it dropped from 0.50 → 0.38
// alongside the sub-stream + buffalo_l swap. Keep in sync when re-tuning.
const THRESHOLD = 0.38

type RecognitionState = 'recognized' | 'warming_up' | 'unknown'

function deriveState(track: TrackInfo | null): RecognitionState | null {
  if (!track) return null
  if (track.recognition_state === 'recognized') return 'recognized'
  if (track.recognition_state === 'unknown') return 'unknown'
  if (track.recognition_state === 'warming_up') return 'warming_up'
  if (track.status === 'recognized') return 'recognized'
  if (track.status === 'unknown') return 'unknown'
  return 'warming_up'
}

function stateConfig(state: RecognitionState | null): {
  label: string
  className: string
} {
  if (state === 'recognized')
    return {
      label: 'Recognized',
      className: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
    }
  if (state === 'unknown')
    return {
      label: 'Unknown',
      className: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
    }
  if (state === 'warming_up')
    return {
      label: 'Detecting…',
      className: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    }
  return { label: 'No Live Track', className: 'bg-muted text-muted-foreground' }
}

function formatAgo(ms: number): string {
  if (ms < 1000) return 'just now'
  if (ms < 60_000) return `${Math.round(ms / 1000)}s ago`
  return `${Math.round(ms / 60_000)}m ago`
}

export function SimilarityMetrics({
  track,
  fallbackUserId,
  fallbackName,
  isConnected,
  lastSeenAtMs,
  isStale,
}: Props) {
  const state = deriveState(track)
  const config = stateConfig(state)
  const confidence = track?.confidence ?? 0
  const pct = Math.max(0, Math.min(100, confidence * 100))
  const threshPct = THRESHOLD * 100
  const aboveThreshold = confidence >= THRESHOLD

  const name = track?.name ?? fallbackName ?? 'Unresolved'
  const userId = track?.user_id ?? fallbackUserId

  // Re-render the "Xs ago" label every second.
  const [, forceTick] = useState(0)
  useEffect(() => {
    if (!lastSeenAtMs) return
    const t = setInterval(() => forceTick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [lastSeenAtMs])

  const agoLabel = lastSeenAtMs
    ? formatAgo(performance.now() - lastSeenAtMs)
    : null

  return (
    <div className="flex flex-col gap-3 rounded-md border bg-muted/20 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{name}</div>
          {userId && (
            <div className="truncate font-mono text-[11px] text-muted-foreground">
              {userId}
            </div>
          )}
        </div>
        <Badge variant="outline" className={config.className}>
          {config.label}
        </Badge>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-baseline justify-between gap-2 text-xs">
          <span className="text-muted-foreground">Cosine similarity</span>
          <span className="font-mono text-sm font-semibold">
            {track ? confidence.toFixed(3) : '—'}
          </span>
        </div>
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={
              aboveThreshold
                ? 'h-full rounded-full bg-emerald-500 transition-all'
                : 'h-full rounded-full bg-blue-500 transition-all'
            }
            style={{ width: `${pct}%` }}
          />
          <div
            className="pointer-events-none absolute top-0 h-full w-px bg-foreground/60"
            style={{ left: `${threshPct}%` }}
            aria-hidden
          />
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>0.0</span>
          <span className="font-mono">
            threshold {THRESHOLD.toFixed(2)}
          </span>
          <span>1.0</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        {track?.track_id != null && (
          <span>
            Track <span className="font-mono">#{track.track_id}</span>
          </span>
        )}
        {agoLabel && (
          <span>
            Updated <span className="font-mono">{agoLabel}</span>
          </span>
        )}
        {isStale && (
          <span className="font-medium text-amber-600 dark:text-amber-500">
            Left frame
          </span>
        )}
        {!isConnected && (
          <span className="ml-auto inline-flex items-center gap-1 text-amber-600 dark:text-amber-500">
            <WifiOff className="h-3 w-3" aria-hidden />
            Disconnected
          </span>
        )}
      </div>
    </div>
  )
}

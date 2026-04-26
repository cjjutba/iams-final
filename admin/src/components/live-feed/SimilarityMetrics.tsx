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

// Fallback when the backend doesn't emit a per-track effective threshold
// (older builds pre-dating the 2026-04-26 diagnostic plumbing). Matches
// the current default of 0.50 — keep loosely in sync with
// settings.RECOGNITION_THRESHOLD if you ever ship a UI build before a
// backend build, but the backend's per-track ``effective_threshold``
// should always win when present (it accounts for the phone-only bonus).
const FALLBACK_THRESHOLD = 0.5

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
  dotClassName: string
} {
  if (state === 'recognized')
    return {
      label: 'Recognized',
      className:
        'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
      dotClassName: 'bg-emerald-500',
    }
  if (state === 'unknown')
    return {
      label: 'Unknown',
      className:
        'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30',
      dotClassName: 'bg-amber-500',
    }
  if (state === 'warming_up')
    return {
      label: 'Detecting',
      className:
        'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30',
      dotClassName: 'bg-sky-500 animate-pulse',
    }
  return {
    label: 'No live track',
    className: 'bg-muted text-muted-foreground border-border',
    dotClassName: 'bg-muted-foreground/40',
  }
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
  // Use the backend's per-track effective threshold when present
  // (accounts for RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS); fall back to
  // the static default for older backend builds.
  const threshold =
    track?.effective_threshold && track.effective_threshold > 0
      ? track.effective_threshold
      : FALLBACK_THRESHOLD
  const threshPct = threshold * 100
  const aboveThreshold = confidence >= threshold
  const hasScore = !!track && state !== null

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

  // Color the score number to mirror the bar — green above threshold, sky
  // (the warming-up color) below — so a glance at the headline tells you
  // whether the match is strong or weak without parsing the bar.
  const scoreColor = !hasScore
    ? 'text-muted-foreground/50'
    : aboveThreshold
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-sky-600 dark:text-sky-400'

  return (
    <div className="flex flex-col gap-4 rounded-lg border bg-card/40 p-4">
      {/* Header: name, ID, status pill */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="truncate text-base font-semibold leading-tight">
            {name}
          </div>
          {userId && (
            <div className="mt-0.5 truncate font-mono text-[10.5px] text-muted-foreground/80">
              {userId}
            </div>
          )}
        </div>
        <Badge
          variant="outline"
          className={`shrink-0 gap-1.5 px-2 py-0.5 text-[11px] font-medium ${config.className}`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${config.dotClassName}`}
            aria-hidden
          />
          {config.label}
        </Badge>
      </div>

      {/* Score: large number on the left, bar fills the right */}
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3">
          <div className="flex items-baseline gap-2">
            <span
              className={`font-mono text-2xl font-semibold tabular-nums ${scoreColor}`}
            >
              {hasScore ? confidence.toFixed(3) : '—'}
            </span>
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
              cosine similarity
            </span>
          </div>
          <span
            className={`font-mono text-[10.5px] tabular-nums ${
              aboveThreshold
                ? 'text-emerald-600/70 dark:text-emerald-400/70'
                : 'text-muted-foreground'
            }`}
          >
            min {threshold.toFixed(2)}
          </span>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={
              aboveThreshold
                ? 'h-full rounded-full bg-emerald-500 transition-all duration-300'
                : 'h-full rounded-full bg-sky-500 transition-all duration-300'
            }
            style={{ width: `${pct}%` }}
          />
          <div
            className="pointer-events-none absolute top-0 h-full w-px bg-foreground/40"
            style={{ left: `${threshPct}%` }}
            aria-hidden
          />
        </div>
      </div>

      {/* Footer line: track id, last-seen, status flags */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {track?.track_id != null && (
          <span className="inline-flex items-center gap-1">
            <span className="text-muted-foreground/70">Track</span>
            <span className="font-mono tabular-nums text-foreground/80">
              #{track.track_id}
            </span>
          </span>
        )}
        {agoLabel && <span className="font-mono tabular-nums">{agoLabel}</span>}
        {isStale && (
          <span className="inline-flex items-center gap-1 font-medium text-amber-600 dark:text-amber-500">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
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

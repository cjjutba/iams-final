import { useEffect, useState } from 'react'
import { AlertTriangle, Camera, Loader2 } from 'lucide-react'

import { useLiveCrop } from '@/hooks/use-live-crop'
import type { LiveCropSource } from '@/types'

interface Props {
  source: LiveCropSource
}

// A crop captured within this many ms is considered "fresh" and gets the
// pulsing LIVE indicator. Beyond it the indicator fades and the timestamp
// switches to "Xs ago" so the operator knows the image is no longer
// updating in real time.
const FRESH_THRESHOLD_MS = 3000

function formatAge(ageMs: number): string {
  if (ageMs < 1000) return 'now'
  if (ageMs < 60_000) return `${Math.round(ageMs / 1000)}s ago`
  return `${Math.round(ageMs / 60_000)}m ago`
}

/**
 * Right-side panel for the face-comparison sheet.
 *
 * Server kind feeds `source={ kind: 'server', recognitionEvents, ... }` —
 * the latest WS recognition_event for the selected user wins, throttled
 * to ~1 swap/sec inside `useServerSideCrop` so the image doesn't flicker
 * at recognition fps.
 */
export function LiveCropPanel({ source }: Props) {
  const result = useLiveCrop(source)

  // Tick once per second so the "Xs ago" age label keeps refreshing even
  // when no new event has arrived. Cheap — only one timer for the whole
  // panel, only running while a crop is on screen.
  const [, forceTick] = useState(0)
  useEffect(() => {
    if (!result.capturedAt) return
    const t = setInterval(() => forceTick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [result.capturedAt])

  const ageMs = result.capturedAt ? Date.now() - result.capturedAt : null
  const isFresh = ageMs !== null && ageMs < FRESH_THRESHOLD_MS

  const { sourceWidth, sourceHeight, isSubStream } = result.resolutionHint ?? {
    sourceWidth: 0,
    sourceHeight: 0,
    isSubStream: false,
  }
  const sourceCaption =
    source.kind === 'client' && sourceWidth > 0
      ? `Client ${sourceWidth}×${sourceHeight}${isSubStream ? ' (sub)' : ''}`
      : source.kind === 'server' && sourceWidth > 0
        ? `Server ${sourceWidth}×${sourceHeight}`
        : null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative flex aspect-square items-center justify-center overflow-hidden rounded-md border border-border/60 bg-muted/40">
        {result.dataUrl ? (
          <img
            src={result.dataUrl}
            alt="Live detected face"
            className="h-full w-full object-cover"
          />
        ) : result.status === 'loading' ? (
          <div className="flex flex-col items-center gap-2 px-4 text-center text-[11px] text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin opacity-70" aria-hidden />
            <span>Waiting for first frame…</span>
          </div>
        ) : result.status === 'not-implemented' ? (
          <div className="flex flex-col items-center gap-1.5 px-4 text-center text-[11px] text-muted-foreground">
            <AlertTriangle className="h-4 w-4 opacity-70" aria-hidden />
            <span>Server crop endpoint unavailable</span>
          </div>
        ) : result.status === 'error' ? (
          <div className="flex flex-col items-center gap-1.5 px-4 text-center text-[11px] text-amber-600 dark:text-amber-500">
            <AlertTriangle className="h-4 w-4" aria-hidden />
            <span className="font-medium">{result.errorMessage ?? 'Failed to grab crop'}</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5 px-4 text-center text-[11px] text-muted-foreground">
            <Camera className="h-4 w-4 opacity-70" aria-hidden />
            <span>Student not on camera</span>
          </div>
        )}

        {/* Live indicator — top-left while fresh events are landing. */}
        {result.dataUrl && isFresh && (
          <div className="pointer-events-none absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-white backdrop-blur-sm">
            <span
              className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400"
              aria-hidden
            />
            Live
          </div>
        )}

        {/* Stale-track banner stays at the bottom edge, unchanged in spirit. */}
        {result.dataUrl && result.status === 'stale' && (
          <div
            role="status"
            aria-live="polite"
            className="absolute inset-x-0 bottom-0 bg-amber-500/80 px-2 py-1 text-center text-[10px] font-medium text-white backdrop-blur-sm"
          >
            Track left frame
          </div>
        )}
      </div>

      {/* Caption: source + freshness in a single tight line. While the
          LIVE pill is on (broadcast cadence is ~1 Hz, fresh window is
          3 s), the stamp stays "now" instead of bumping 0s → 1s → 2s
          between broadcasts — the inter-broadcast tick looked like the
          panel was already going stale even though the next broadcast
          was always one beat away. Only switches to numeric age once
          we're truly past the fresh window. */}
      <div className="flex items-center justify-between gap-2 px-0.5 text-[10px] text-muted-foreground">
        <span className="truncate">{sourceCaption ?? ' '}</span>
        {ageMs !== null && (
          <span
            className={`shrink-0 font-mono tabular-nums ${
              isFresh ? 'text-emerald-600 dark:text-emerald-400' : ''
            }`}
          >
            {isFresh ? 'now' : formatAge(ageMs)}
          </span>
        )}
      </div>
    </div>
  )
}

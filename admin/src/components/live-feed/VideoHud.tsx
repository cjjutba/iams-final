import { Activity, AlertTriangle, Download, RotateCcw } from 'lucide-react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { FrameUpdateMessage, LatencyStats } from '@/hooks/use-attendance-ws'

interface VideoHudProps {
  latestFrame: FrameUpdateMessage | null
  latencyStats: LatencyStats | null
  onDownloadCsv: () => void
  onClearSamples: () => void
  fallbackActive: boolean
  fallbackKey?: string
  /**
   * Where the diagnostics popover portals to. Default behaviour (no value)
   * portals to `document.body`, which is correct for the inline page. In
   * fullscreen, only the fullscreened element + descendants are rendered,
   * so callers must pass the fullscreen container ref's current value to
   * keep the popover visible and interactive.
   */
  portalContainer?: HTMLElement | null
}

/**
 * Floating heads-up display laid over the video player. Surfaces the
 * single most useful telemetry line (FPS · latency · tracks) at glance
 * weight; the full per-stage / E2E breakdown and the CSV / reset
 * controls hide behind a click on the chip. Keeps the video frame the
 * page's hero rather than burying it under a wall of dev metrics.
 */
export function VideoHud({
  latestFrame,
  latencyStats,
  onDownloadCsv,
  onClearSamples,
  fallbackActive,
  fallbackKey,
  portalContainer,
}: VideoHudProps) {
  if (!latestFrame && !fallbackActive) return null

  const fps = latestFrame?.fps ?? 0
  const latency = latestFrame?.processing_ms ?? null
  const trackCount = latestFrame?.tracks.length ?? 0

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-2 p-3">
      {fallbackActive && (
        <div className="pointer-events-auto inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/15 px-2 py-1 text-[11px] font-medium text-amber-100 backdrop-blur-sm">
          <AlertTriangle className="h-3 w-3" />
          <span>
            Sub stream unavailable — showing{' '}
            <span className="font-mono">{fallbackKey}</span> (main)
          </span>
        </div>
      )}

      {latestFrame && (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="pointer-events-auto ml-auto inline-flex items-center gap-2 rounded-md border border-white/15 bg-black/55 px-2.5 py-1 font-mono text-[11px] text-white backdrop-blur-sm transition hover:bg-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
              aria-label="Show pipeline diagnostics"
            >
              <Activity className="h-3 w-3 text-emerald-400" aria-hidden />
              <span>{fps.toFixed(1)} fps</span>
              {latency != null && (
                <>
                  <span className="text-white/30">·</span>
                  <span>{latency.toFixed(0)} ms</span>
                </>
              )}
              <span className="text-white/30">·</span>
              <span>
                {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
              </span>
            </button>
          </PopoverTrigger>

          <PopoverContent
            align="end"
            className="w-80 space-y-3 text-xs"
            container={portalContainer ?? undefined}
            collisionBoundary={portalContainer ?? undefined}
          >
            <div>
              <div className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Per-stage timing (ms)
              </div>
              <div className="grid grid-cols-4 gap-2 font-mono">
                <StageStat label="det" value={latestFrame.det_ms ?? null} />
                <StageStat label="embed" value={latestFrame.embed_ms ?? null} />
                <StageStat label="faiss" value={latestFrame.faiss_ms ?? null} />
                <StageStat label="other" value={latestFrame.other_ms ?? null} />
              </div>
            </div>

            <div className="h-px bg-border" />

            <div>
              <div className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                End-to-end latency
              </div>
              {latencyStats ? (
                <div
                  className="flex items-center justify-between font-mono text-[11px]"
                  title="Wall-clock delay from FrameGrabber drain to admin WS message receive"
                >
                  <div className="flex gap-3">
                    <span>
                      <span className="text-muted-foreground">p50</span>{' '}
                      {latencyStats.p50Ms.toFixed(0)} ms
                    </span>
                    <span>
                      <span className="text-muted-foreground">p95</span>{' '}
                      {latencyStats.p95Ms.toFixed(0)} ms
                    </span>
                  </div>
                  <span className="text-muted-foreground">
                    n={latencyStats.count}
                  </span>
                </div>
              ) : (
                <div className="text-[11px] text-muted-foreground">
                  Collecting samples…
                </div>
              )}
            </div>

            <div className="h-px bg-border" />

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onDownloadCsv}
                disabled={!latencyStats || latencyStats.count === 0}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                title="Download every collected latency sample as CSV"
              >
                <Download className="h-3 w-3" />
                Download CSV
              </button>
              <button
                type="button"
                onClick={onClearSamples}
                disabled={!latencyStats || latencyStats.count === 0}
                className="inline-flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                title="Reset the rolling latency buffer"
              >
                <RotateCcw className="h-3 w-3" />
                Reset
              </button>
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  )
}

function StageStat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-md border bg-muted/30 px-2 py-1.5 text-center">
      <div className="text-[9px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-[11px] font-medium">
        {value != null ? value.toFixed(0) : '—'}
      </div>
    </div>
  )
}

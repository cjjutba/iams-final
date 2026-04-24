import { AlertTriangle, Camera, Loader2 } from 'lucide-react'

import { useLiveCrop } from '@/hooks/use-live-crop'
import type { LiveCropSource } from '@/types'

interface Props {
  source: LiveCropSource
}

/**
 * Right-side panel for the face-comparison sheet.
 *
 * Phase 1 feeds `source={ kind: 'client', ... }` — canvas-grab from the WHEP
 * `<video>` element. Phase 3 flips to `source={ kind: 'server', ... }` to pull
 * a server-captured main-profile crop instead. `useLiveCrop` is the facade
 * that routes between them; this component is kind-agnostic.
 */
export function LiveCropPanel({ source }: Props) {
  const result = useLiveCrop(source)

  const { sourceWidth, sourceHeight, isSubStream } = result.resolutionHint ?? {
    sourceWidth: 0,
    sourceHeight: 0,
    isSubStream: false,
  }

  const subStreamHint =
    source.kind === 'client' && isSubStream && sourceWidth > 0
      ? `Client-grab from ${sourceWidth}×${sourceHeight} sub stream — ML pipeline decodes the main 2304×1296 profile.`
      : source.kind === 'client' && sourceWidth > 0
      ? `Client-grab from ${sourceWidth}×${sourceHeight} main stream.`
      : source.kind === 'server'
      ? 'Server crop from main 2304×1296 profile.'
      : null

  return (
    <div className="flex flex-col gap-2">
      <div className="relative flex aspect-square items-center justify-center overflow-hidden rounded-md border bg-muted/20">
        {result.dataUrl ? (
          <img
            src={result.dataUrl}
            alt="Live detected face"
            className="h-full w-full object-contain"
          />
        ) : result.status === 'loading' ? (
          <div className="flex flex-col items-center gap-2 p-4 text-center text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            <span>Waiting for first frame…</span>
          </div>
        ) : result.status === 'not-implemented' ? (
          <div className="flex flex-col items-center gap-2 p-4 text-center text-sm text-muted-foreground">
            <AlertTriangle className="h-5 w-5" aria-hidden />
            <span>Server crop endpoint not yet available.</span>
          </div>
        ) : result.status === 'error' ? (
          <div className="flex flex-col items-center gap-2 p-4 text-center text-sm text-amber-600 dark:text-amber-500">
            <AlertTriangle className="h-5 w-5" aria-hidden />
            <span>{result.errorMessage ?? 'Failed to grab crop'}</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 p-4 text-center text-sm text-muted-foreground">
            <Camera className="h-5 w-5" aria-hidden />
            <span>Student not currently on camera</span>
          </div>
        )}
        {result.dataUrl && result.status === 'stale' && (
          <div
            role="status"
            aria-live="polite"
            className="absolute inset-x-0 bottom-0 bg-amber-500/80 px-2 py-1 text-center text-[11px] font-medium text-white"
          >
            Track left frame — showing last crop
          </div>
        )}
      </div>
      {subStreamHint && (
        <p className="text-[11px] leading-snug text-muted-foreground">
          Source: {subStreamHint}
        </p>
      )}
    </div>
  )
}

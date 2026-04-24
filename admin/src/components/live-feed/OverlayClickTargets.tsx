import { useEffect, useState } from 'react'

import type { TrackInfo } from '@/hooks/use-attendance-ws'
import { useTrackSelectionStore } from '@/stores/track-selection.store'

interface Props {
  tracks: TrackInfo[]
  videoElement: HTMLVideoElement | null
  videoSize: { width: number; height: number } | null
}

interface LayoutBox {
  trackId: number
  userId: string | null
  name: string | null
  left: number
  top: number
  width: number
  height: number
}

/**
 * Transparent DOM overlay of `<button>` elements — one per live track — that
 * captures clicks to open the TrackDetailSheet. Kept separate from
 * `DetectionOverlay` (pure canvas) so the canvas stays `pointer-events-none`
 * and snap-then-lerp animation keeps its existing hot path.
 *
 * Uses the same letterbox math as DetectionOverlay but maps to DOM
 * coordinates instead of canvas pixels, and pins the hit region to the
 * most-recent target bbox (not the lerped position) so the button doesn't
 * slide around underneath a moving cursor.
 */
export function OverlayClickTargets({ tracks, videoElement, videoSize }: Props) {
  const select = useTrackSelectionStore((s) => s.select)
  const [layout, setLayout] = useState<LayoutBox[]>([])

  useEffect(() => {
    if (!videoElement) {
      setLayout([])
      return
    }
    const displayWidth = videoElement.clientWidth
    const displayHeight = videoElement.clientHeight
    if (displayWidth <= 0 || displayHeight <= 0) {
      setLayout([])
      return
    }

    const vw = videoSize?.width ?? videoElement.videoWidth ?? displayWidth
    const vh = videoSize?.height ?? videoElement.videoHeight ?? displayHeight

    let drawW = displayWidth
    let drawH = displayHeight
    let offsetX = 0
    let offsetY = 0
    if (vw > 0 && vh > 0) {
      const videoAspect = vw / vh
      const displayAspect = displayWidth / displayHeight
      if (videoAspect > displayAspect) {
        drawH = displayWidth / videoAspect
        offsetY = (displayHeight - drawH) / 2
      } else {
        drawW = displayHeight * videoAspect
        offsetX = (displayWidth - drawW) / 2
      }
    }

    const next: LayoutBox[] = tracks
      .map((track) => {
        const [x1n, y1n, x2n, y2n] = track.bbox
        const left = offsetX + x1n * drawW
        const top = offsetY + y1n * drawH
        const width = (x2n - x1n) * drawW
        const height = (y2n - y1n) * drawH
        return {
          trackId: track.track_id,
          userId: track.user_id,
          name: track.name,
          left,
          top,
          width,
          height,
        }
      })
      .filter((b) => b.width > 4 && b.height > 4)
    setLayout(next)
  }, [tracks, videoElement, videoSize])

  if (!videoElement) return null

  return (
    <div className="pointer-events-none absolute inset-0">
      {layout.map((box) => (
        <button
          key={box.trackId}
          type="button"
          aria-label={`Inspect ${box.name ?? 'unrecognized face'} (track ${box.trackId})`}
          onClick={() => select(box.trackId, box.userId)}
          className="pointer-events-auto absolute cursor-pointer rounded bg-transparent outline-none ring-0 transition focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-0"
          style={{
            left: `${box.left}px`,
            top: `${box.top}px`,
            width: `${box.width}px`,
            height: `${box.height}px`,
          }}
        />
      ))}
    </div>
  )
}

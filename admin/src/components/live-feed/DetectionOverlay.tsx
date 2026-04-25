import { useEffect, useRef } from 'react'
import type { TrackInfo } from '@/hooks/use-attendance-ws'

interface DetectionOverlayProps {
  /** Latest tracks from the WebSocket. Normalized bbox (0-1). */
  tracks: TrackInfo[]
  /** The <video> element the overlay sits on top of. */
  videoElement: HTMLVideoElement | null
  /** Intrinsic video size (from onLoadedMetadata). Optional — canvas auto-sizes. */
  videoSize?: { width: number; height: number } | null
  /**
   * Track id currently open in the TrackDetailSheet. When set, its box is
   * drawn with a thicker stroke + outer halo so admins can visually tie the
   * sheet to a specific detection.
   */
  selectedTrackId?: number | null
  className?: string
}

// Tri-state the overlay commits to, derived from the backend's
// `recognition_state` (preferred) with a fallback to the legacy `status`
// field for older payloads. This is what colors + labels key off of.
type OverlayState = 'recognized' | 'warming_up' | 'unknown'

const COLOR_RECOGNIZED = '#22c55e'
const COLOR_UNKNOWN = '#f59e0b'
const COLOR_WARMING_UP = '#3b82f6'

const LABEL_BG_ALPHA = 0.9

function deriveOverlayState(track: TrackInfo): OverlayState {
  if (track.recognition_state === 'recognized') return 'recognized'
  if (track.recognition_state === 'unknown') return 'unknown'
  if (track.recognition_state === 'warming_up') return 'warming_up'

  if (track.status === 'recognized') return 'recognized'
  if (track.status === 'unknown') return 'unknown'
  return 'warming_up'
}

function colorForState(state: OverlayState): string {
  if (state === 'recognized') return COLOR_RECOGNIZED
  if (state === 'unknown') return COLOR_UNKNOWN
  return COLOR_WARMING_UP
}

function labelForTrack(track: TrackInfo, state: OverlayState): string {
  if (state === 'recognized' && track.name) return track.name
  if (state === 'unknown') return 'Unknown'
  return 'Detecting…'
}

/**
 * Canvas overlay that draws labeled bounding boxes on top of the live video.
 *
 * Design (post-2026-04-25 honest-overlay rewrite):
 * - Backend `frame_update` is the single source of truth.
 * - We paint exactly `props.tracks` — no interpolation, no extrapolation, no
 *   per-track decay. If a track isn't in the latest WS message, it isn't on
 *   screen.
 * - The rAF loop only exists to keep the canvas sized to the video element
 *   (which can resize on window/fullscreen changes) and to redraw on each
 *   frame so a resize doesn't leave stale pixels. The scene itself is
 *   stateless w.r.t. previous frames.
 *
 * At backend ~1.5 fps the box visibly blinks at the backend rate; at backend
 * ~10 fps the eye reads it as continuous motion. This is intentional:
 * "blinking but always correct" beats "smooth but on the wrong person", per
 * the live-feed-overhaul plan dated 2026-04-25.
 */
export function DetectionOverlay({ tracks, videoElement, videoSize, selectedTrackId, className }: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const animationRef = useRef<number | null>(null)
  // Refs so the rAF loop sees the latest props without re-subscribing.
  const tracksRef = useRef<TrackInfo[]>(tracks)
  tracksRef.current = tracks
  const selectedTrackIdRef = useRef<number | null>(null)
  selectedTrackIdRef.current = selectedTrackId ?? null

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const draw = () => {
      const video = videoElement
      const displayWidth = video?.clientWidth ?? canvas.parentElement?.clientWidth ?? 0
      const displayHeight = video?.clientHeight ?? canvas.parentElement?.clientHeight ?? 0
      if (canvas.width !== displayWidth) canvas.width = displayWidth
      if (canvas.height !== displayHeight) canvas.height = displayHeight

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        animationRef.current = requestAnimationFrame(draw)
        return
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Compute letterbox offset. The video has intrinsic size (videoSize), the
      // display area is displayWidth × displayHeight, object-fit: contain
      // preserves aspect ratio. Determine the actual drawn rectangle inside
      // the element so we can scale normalized bbox coords correctly.
      const vw = videoSize?.width ?? video?.videoWidth ?? displayWidth
      const vh = videoSize?.height ?? video?.videoHeight ?? displayHeight
      let drawWidth = displayWidth
      let drawHeight = displayHeight
      let offsetX = 0
      let offsetY = 0
      if (vw > 0 && vh > 0) {
        const videoAspect = vw / vh
        const displayAspect = displayWidth / displayHeight
        if (videoAspect > displayAspect) {
          drawHeight = displayWidth / videoAspect
          offsetY = (displayHeight - drawHeight) / 2
        } else {
          drawWidth = displayHeight * videoAspect
          offsetX = (displayWidth - drawWidth) / 2
        }
      }

      const liveTracks = tracksRef.current
      const selectedId = selectedTrackIdRef.current

      for (const track of liveTracks) {
        const [x1n, y1n, x2n, y2n] = track.bbox
        const x1 = offsetX + x1n * drawWidth
        const y1 = offsetY + y1n * drawHeight
        const x2 = offsetX + x2n * drawWidth
        const y2 = offsetY + y2n * drawHeight
        const boxW = x2 - x1
        const boxH = y2 - y1

        if (boxW <= 0 || boxH <= 0) continue

        const state = deriveOverlayState(track)
        const color = colorForState(state)
        const isSelected = selectedId === track.track_id

        if (isSelected) {
          ctx.lineWidth = 8
          ctx.strokeStyle = `${color}55`
          ctx.strokeRect(x1 - 3, y1 - 3, boxW + 6, boxH + 6)
        }

        ctx.lineWidth = isSelected ? 5 : 3
        ctx.strokeStyle = color
        ctx.strokeRect(x1, y1, boxW, boxH)

        const label = labelForTrack(track, state)
        ctx.font = '600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
        const metrics = ctx.measureText(label)
        const labelW = metrics.width + 12
        const labelH = 22
        const labelX = x1
        const labelY = y1 >= labelH ? y1 - labelH : y1

        ctx.fillStyle = `${color}${Math.round(LABEL_BG_ALPHA * 255).toString(16).padStart(2, '0')}`
        ctx.fillRect(labelX, labelY, labelW, labelH)

        ctx.fillStyle = '#ffffff'
        ctx.textBaseline = 'middle'
        ctx.fillText(label, labelX + 6, labelY + labelH / 2)
      }

      animationRef.current = requestAnimationFrame(draw)
    }

    animationRef.current = requestAnimationFrame(draw)

    return () => {
      if (animationRef.current !== null) cancelAnimationFrame(animationRef.current)
      animationRef.current = null
    }
  }, [videoElement, videoSize])

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none absolute inset-0 ${className ?? ''}`}
      aria-hidden="true"
    />
  )
}

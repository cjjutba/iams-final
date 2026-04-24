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
   * sheet to a specific detection. All other tracks animate normally.
   */
  selectedTrackId?: number | null
  className?: string
}

// Tri-state the overlay commits to, derived from the backend's
// `recognition_state` (preferred) with a fallback to the legacy `status` field
// for older payloads. This is what colors + labels key off of.
type OverlayState = 'recognized' | 'warming_up' | 'unknown'

interface InterpolatedTrack {
  trackId: number
  name: string | null
  overlayState: OverlayState
  // Current (displayed) bbox
  currentBbox: [number, number, number, number]
  // Last bbox the backend reported (anchor for extrapolation)
  targetBbox: [number, number, number, number]
  // Last velocity the backend reported, in center+size space: (cx_vel,
  // cy_vel, w_vel, h_vel), normalized units per second.
  velocity: [number, number, number, number]
  // Wall time when the current targetBbox / velocity was received. Used to
  // compute the elapsed-time term in the velocity extrapolation.
  targetUpdatedMs: number
  // Last time the WS gave us a position for this track
  lastSeenMs: number
}

// Colors per overlay state
const COLOR_RECOGNIZED = '#22c55e' // green-500 — known, named face
const COLOR_UNKNOWN = '#f59e0b' // amber-500 — confirmed not-enrolled
const COLOR_WARMING_UP = '#3b82f6' // blue-500 — FAISS still deciding ("Detecting…")

const LABEL_BG_ALPHA = 0.9
// Higher = snappier catch-up when a fresh target arrives. Bumped from
// 0.25 → 0.35 on 2026-04-24 so the box converges in ~3 rAF frames at 60
// fps instead of ~5 — noticeable when the face moves between the ~227 ms
// backend updates.
const LERP_RATE = 0.35
// Max forward extrapolation window. Caps how far we'll project the bbox
// along its last known velocity before a fresh WS frame arrives. Prevents
// runaway drift if the backend stops sending (e.g. pipeline stall).
const MAX_EXTRAPOLATION_MS = 500
const STALE_MS = 2000 // drop tracks we haven't seen for this long

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

function deriveOverlayState(track: TrackInfo): OverlayState {
  // Prefer the explicit tri-state from the backend (see realtime_tracker.py's
  // _derive_recognition_state) — it already handles the "warm-up vs. committed
  // unknown" gating.
  if (track.recognition_state === 'recognized') return 'recognized'
  if (track.recognition_state === 'unknown') return 'unknown'
  if (track.recognition_state === 'warming_up') return 'warming_up'

  // Fallback to the legacy status field if the payload is missing
  // recognition_state (older backend builds).
  if (track.status === 'recognized') return 'recognized'
  if (track.status === 'unknown') return 'unknown'
  return 'warming_up'
}

function colorForState(state: OverlayState): string {
  if (state === 'recognized') return COLOR_RECOGNIZED
  if (state === 'unknown') return COLOR_UNKNOWN
  return COLOR_WARMING_UP
}

function labelForTrack(track: InterpolatedTrack): string {
  if (track.overlayState === 'recognized' && track.name) return track.name
  if (track.overlayState === 'unknown') return 'Unknown'
  return 'Detecting…'
}

/**
 * Canvas overlay that draws labeled bounding boxes on top of the live video.
 *
 * Design:
 * - tracks arrive at ~10 fps from the backend WebSocket (onprem).
 * - We store each track's last target bbox and lerp toward it at ~60 fps via
 *   requestAnimationFrame. This matches the snap-then-lerp pattern from
 *   android/app/src/main/java/com/iams/app/ui/components/InterpolatedTrackOverlay.kt
 *   (ported per lessons 2026-04-21).
 * - Tracks unseen for STALE_MS are dropped.
 * - Canvas dimensions follow the video element's offsetWidth/Height so the
 *   overlay always aligns with the letterboxed video.
 */
export function DetectionOverlay({ tracks, videoElement, videoSize, selectedTrackId, className }: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const tracksRef = useRef<Map<number, InterpolatedTrack>>(new Map())
  const animationRef = useRef<number | null>(null)
  const selectedTrackIdRef = useRef<number | null>(null)
  selectedTrackIdRef.current = selectedTrackId ?? null

  // Whenever the WS gives us new tracks, update the targets + velocity.
  useEffect(() => {
    const now = performance.now()
    const map = tracksRef.current
    const seenIds = new Set<number>()

    for (const track of tracks) {
      seenIds.add(track.track_id)
      const overlayState = deriveOverlayState(track)
      const velocity: [number, number, number, number] = track.velocity ?? [0, 0, 0, 0]
      const existing = map.get(track.track_id)
      if (existing) {
        // Update target + velocity; keep currentBbox so we lerp from the
        // last displayed position toward the new extrapolated target.
        existing.targetBbox = track.bbox
        existing.velocity = velocity
        existing.targetUpdatedMs = now
        existing.name = track.name
        existing.overlayState = overlayState
        existing.lastSeenMs = now
      } else {
        // New track — snap current = target so the first draw doesn't animate
        // in from (0,0).
        map.set(track.track_id, {
          trackId: track.track_id,
          name: track.name,
          overlayState,
          currentBbox: [...track.bbox] as [number, number, number, number],
          targetBbox: track.bbox,
          velocity,
          targetUpdatedMs: now,
          lastSeenMs: now,
        })
      }
    }
    // Don't delete absent tracks here — let the render loop expire them via STALE_MS
    // so a single dropped frame doesn't cause a flicker.
  }, [tracks])

  // rAF loop: lerp currentBbox toward targetBbox, expire stale tracks, redraw.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    let lastDrawMs = performance.now()

    const draw = () => {
      const now = performance.now()
      const dtFactor = Math.min(1, (now - lastDrawMs) / 16.67) // normalize to 60 fps frame
      lastDrawMs = now

      // Resize canvas to match the video element's display box (accounts for
      // object-fit: contain letterboxing on the video).
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
      // preserves aspect ratio. Determine the actual drawn rectangle inside the
      // element so we can scale normalized bbox coords correctly.
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
          // Letterbox top/bottom
          drawHeight = displayWidth / videoAspect
          offsetY = (displayHeight - drawHeight) / 2
        } else {
          // Pillarbox left/right
          drawWidth = displayHeight * videoAspect
          offsetX = (displayWidth - drawWidth) / 2
        }
      }

      const map = tracksRef.current
      const toDelete: number[] = []

      for (const track of map.values()) {
        if (now - track.lastSeenMs > STALE_MS) {
          toDelete.push(track.trackId)
          continue
        }

        // ── Step 1: project targetBbox forward using the last reported
        // velocity. The backend broadcasts bbox + velocity at its
        // processing rate (~4 fps onprem → ~227 ms between frames). Over
        // that window the face can move 5–15 % of the frame, which makes
        // an un-extrapolated box look glued to an old position while the
        // face has visibly moved on. The extrapolation is capped at
        // MAX_EXTRAPOLATION_MS so a stalled pipeline doesn't drag the box
        // off-screen.
        const dtSinceTargetSec =
          Math.min(now - track.targetUpdatedMs, MAX_EXTRAPOLATION_MS) / 1000
        const [tx1, ty1, tx2, ty2] = track.targetBbox
        const tcx = (tx1 + tx2) / 2
        const tcy = (ty1 + ty2) / 2
        const tw = tx2 - tx1
        const th = ty2 - ty1
        const [vcx, vcy, vw, vh] = track.velocity
        const ecx = tcx + vcx * dtSinceTargetSec
        const ecy = tcy + vcy * dtSinceTargetSec
        // Prevent negative/degenerate sizes when velocity says the face is
        // shrinking faster than time can flatten it.
        const ew = Math.max(0.01, tw + vw * dtSinceTargetSec)
        const eh = Math.max(0.01, th + vh * dtSinceTargetSec)
        const extrapolatedTarget: [number, number, number, number] = [
          ecx - ew / 2,
          ecy - eh / 2,
          ecx + ew / 2,
          ecy + eh / 2,
        ]

        // ── Step 2: lerp the currently drawn bbox toward the extrapolated
        // target. The lerp still matters — it smooths out the small jumps
        // between "last reported" and "next predicted" targets, and it
        // masks any residual overshoot when velocity was slightly wrong.
        const t = Math.min(1, LERP_RATE * dtFactor * 2) // *2 because 60fps means 16ms per frame
        track.currentBbox = [
          lerp(track.currentBbox[0], extrapolatedTarget[0], t),
          lerp(track.currentBbox[1], extrapolatedTarget[1], t),
          lerp(track.currentBbox[2], extrapolatedTarget[2], t),
          lerp(track.currentBbox[3], extrapolatedTarget[3], t),
        ]

        const [x1n, y1n, x2n, y2n] = track.currentBbox
        const x1 = offsetX + x1n * drawWidth
        const y1 = offsetY + y1n * drawHeight
        const x2 = offsetX + x2n * drawWidth
        const y2 = offsetY + y2n * drawHeight
        const boxW = x2 - x1
        const boxH = y2 - y1

        if (boxW <= 0 || boxH <= 0) continue

        const color = colorForState(track.overlayState)
        const isSelected = selectedTrackIdRef.current === track.trackId

        // Outer halo on the selected track so the admin can see at-a-glance
        // which detection the open sheet is talking about.
        if (isSelected) {
          ctx.lineWidth = 8
          ctx.strokeStyle = `${color}55`
          ctx.strokeRect(x1 - 3, y1 - 3, boxW + 6, boxH + 6)
        }

        // Bounding box — slightly thicker line so boxes stay visible on
        // busy CCTV scenes. Selected track gets an even thicker stroke.
        ctx.lineWidth = isSelected ? 5 : 3
        ctx.strokeStyle = color
        ctx.strokeRect(x1, y1, boxW, boxH)

        // Label
        const label = labelForTrack(track)
        ctx.font = '600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
        const metrics = ctx.measureText(label)
        const labelW = metrics.width + 12
        const labelH = 22
        const labelX = x1
        // If the box is at the very top of the video, draw the label INSIDE
        // the box (bottom-anchored) so it never clips off-canvas.
        const labelY = y1 >= labelH ? y1 - labelH : y1

        ctx.fillStyle = `${color}${Math.round(LABEL_BG_ALPHA * 255).toString(16).padStart(2, '0')}`
        ctx.fillRect(labelX, labelY, labelW, labelH)

        ctx.fillStyle = '#ffffff'
        ctx.textBaseline = 'middle'
        ctx.fillText(label, labelX + 6, labelY + labelH / 2)
      }

      for (const id of toDelete) map.delete(id)

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

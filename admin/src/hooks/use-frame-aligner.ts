/**
 * use-frame-aligner — pin WS bbox draws to the matching WHEP video frame.
 *
 * Why this exists
 * ---------------
 * The backend produces ``frame_update`` WS messages with bboxes stamped
 * on the upstream RTSP/RTP 90 kHz timestamp (``rtp_pts_90k``). The
 * browser plays the same upstream stream via WHEP and Chromium exposes
 * the per-decoded-frame RTP timestamp through
 * ``requestVideoFrameCallback().rtpTimestamp``. Both consumers see the
 * same RTP clock because mediamtx forwards source RTP timestamps
 * unchanged through WHEP egress.
 *
 * The hook keeps a ring buffer of recent backend bbox sets keyed by
 * their RTP PTS, and on every browser-decoded video frame it picks the
 * bbox set whose PTS is the largest value still ≤ the just-decoded
 * frame's RTP timestamp. The selected set is re-rendered through the
 * existing ``DetectionOverlay`` — no further changes to the canvas
 * code.
 *
 * Falls back to the latest-only behavior when:
 *   - The browser doesn't expose ``rtpTimestamp`` (Safari).
 *   - The backend doesn't broadcast ``rtp_pts_90k`` (legacy build).
 *   - The aligner buffer is empty (early frames after schedule load).
 *
 * Live-feed plan 2026-04-25 Step 3c.
 */
import { useEffect, useRef, useState } from 'react'

import type { WhepPlayerHandle } from '@/components/live-feed/WhepPlayer'
import type { FrameUpdateMessage, TrackInfo } from '@/hooks/use-attendance-ws'

const BUFFER_MAX = 60
const STALE_MS = 2000

interface BufferedFrame {
  pts: number
  tracks: TrackInfo[]
  receivedMs: number
}

/**
 * RTP 90 kHz clock wraps every ~13 hours at 32 bits. To compare two
 * timestamps near the wrap boundary, work in signed 32-bit deltas: if the
 * difference fits in [-2^31, 2^31), call it "later"; otherwise "earlier".
 * This is the standard RTP-time arithmetic from RFC 3550 §5.
 */
function isPtsLeq(a: number, b: number): boolean {
  // Both inputs are non-negative integers under 2^32.
  const delta = (b - a) | 0 // forces 32-bit signed subtraction
  return delta >= 0
}

export interface UseFrameAlignerOptions {
  /** Set false to bypass alignment and just return ``latestFrame.tracks``.
   *  Useful for the rollout flag (``VITE_ENABLE_FRAME_ALIGN``). */
  enabled?: boolean
}

/**
 * Returns the bbox track list that should be painted on the *currently
 * displayed* video frame.
 *
 * The hook runs at video-decoded-frame rate (typically 10-30 Hz from
 * mediamtx WHEP), not at React render rate, so we update state through
 * a ref + setState pair: the frame callback writes a candidate, and a
 * ``requestAnimationFrame`` flushes it to React state when it actually
 * changes. This keeps the canvas in sync with the video without
 * triggering a React render per video frame.
 */
export function useFrameAligner(
  playerHandle: WhepPlayerHandle | null,
  latestFrame: FrameUpdateMessage | null,
  options: UseFrameAlignerOptions = {},
): TrackInfo[] {
  const enabled = options.enabled ?? true
  const bufferRef = useRef<BufferedFrame[]>([])
  const lastEmittedTracksRef = useRef<TrackInfo[] | null>(null)
  const [alignedTracks, setAlignedTracks] = useState<TrackInfo[]>([])

  // Append every WS frame that carries an rtp_pts_90k to the buffer. If
  // the WS message lacks the field (legacy backend), we treat it as a
  // disable-aligner signal at the consumer level.
  useEffect(() => {
    if (!latestFrame) return
    if (latestFrame.rtp_pts_90k == null) {
      // No alignment possible — emit immediately so consumer falls back
      // to the latest-only path. We DON'T touch the buffer here so
      // intermittent gaps don't poison alignment when frames resume.
      lastEmittedTracksRef.current = latestFrame.tracks
      setAlignedTracks(latestFrame.tracks)
      return
    }
    const buf = bufferRef.current
    buf.push({
      pts: latestFrame.rtp_pts_90k,
      tracks: latestFrame.tracks,
      receivedMs: performance.now(),
    })
    // Keep the buffer bounded. ``BUFFER_MAX`` covers ~3-6 s at the
    // backend's broadcast rate.
    while (buf.length > BUFFER_MAX) buf.shift()
  }, [latestFrame])

  useEffect(() => {
    if (!enabled || !playerHandle) return

    let rafHandle: number | null = null
    let pendingTracks: TrackInfo[] | null = null

    // The flush loop runs at rAF rate (60 Hz max) and only commits to
    // React state when the bbox set has actually changed. This is the
    // single seam between the high-frequency rVFC loop and React's
    // render cycle — it keeps the canvas updates smooth without
    // hammering setState per video frame.
    const flushLoop = () => {
      if (pendingTracks !== null && pendingTracks !== lastEmittedTracksRef.current) {
        lastEmittedTracksRef.current = pendingTracks
        setAlignedTracks(pendingTracks)
      }
      rafHandle = requestAnimationFrame(flushLoop)
    }
    rafHandle = requestAnimationFrame(flushLoop)

    const unsubscribe = playerHandle.onVideoFrame((meta) => {
      const buf = bufferRef.current
      if (buf.length === 0) {
        pendingTracks = []
        return
      }

      // No browser-side RTP timestamp (Safari) → degrade to latest-only.
      // The buffer is still filled; an aligner-aware Chromium tab on the
      // same machine will work normally, only the Safari tab degrades.
      if (meta.rtpTimestamp == null) {
        pendingTracks = buf[buf.length - 1].tracks
        return
      }

      const browserPts = meta.rtpTimestamp >>> 0 // ensure unsigned 32-bit

      // Linear scan from newest to oldest: pick the first buffered frame
      // whose PTS is ≤ the browser's just-decoded PTS. Linear is fine —
      // BUFFER_MAX is small and this runs at <30 Hz. A binary search
      // would be invalidated by RTP wraparound anyway.
      let chosen: BufferedFrame | null = null
      for (let i = buf.length - 1; i >= 0; i -= 1) {
        if (isPtsLeq(buf[i].pts, browserPts)) {
          chosen = buf[i]
          break
        }
      }

      // Edge case: every buffered frame is *ahead* of the video's
      // current frame. That means the backend is pushing PTS faster
      // than the browser is presenting them — either we just opened
      // the page, or the WHEP stream froze for a moment. Show nothing
      // (rather than draw boxes for a frame the user can't see yet).
      if (chosen === null) {
        pendingTracks = []
        return
      }

      // Drop entries older than the chosen one — they'll never be
      // selected again, no point keeping them.
      const chosenIdx = buf.indexOf(chosen)
      if (chosenIdx > 0) buf.splice(0, chosenIdx)

      // If the picked frame is too old (mediamtx stalled, big jitter)
      // the boxes would be visibly stale — fall back to "no boxes" so
      // the user sees that something's wrong rather than a misaligned
      // scene. STALE_MS matches the user's stated tolerance: blink
      // is fine, drift is not.
      if (performance.now() - chosen.receivedMs > STALE_MS) {
        pendingTracks = []
        return
      }

      pendingTracks = chosen.tracks
    })

    return () => {
      unsubscribe()
      if (rafHandle !== null) cancelAnimationFrame(rafHandle)
    }
  }, [enabled, playerHandle])

  // Consumer fallback: when alignment is disabled at the option level,
  // act as a passthrough on ``latestFrame.tracks``. This is the
  // ``VITE_ENABLE_FRAME_ALIGN=0`` rollout flag's hot path.
  if (!enabled) return latestFrame?.tracks ?? []

  return alignedTracks
}

import { useEffect, useRef, useState } from 'react'

import type { LiveCropResult } from '@/types'

interface UseClientSideCropArgs {
  videoElement: HTMLVideoElement | null
  /** Normalized [x1, y1, x2, y2] in [0,1] — what the backend broadcasts. */
  bbox: [number, number, number, number] | null
  trackId: number | null
  /** True when the selected track is no longer in `latestFrame.tracks`. */
  isStale: boolean
  isSubStream: boolean
}

const OUTPUT_SIZE = 192 // px — plenty for a thumbnail, not huge on base64
const JPEG_QUALITY = 0.85
const BBOX_PADDING = 0.08 // 8 % of bbox width/height on each side
const MIN_CAPTURE_INTERVAL_MS = 250 // throttle canvas grabs
const MIN_BBOX_DELTA = 0.02 // 2 % change in any coord to justify a re-capture

function hasBboxChanged(
  prev: [number, number, number, number] | null,
  next: [number, number, number, number],
): boolean {
  if (!prev) return true
  for (let i = 0; i < 4; i++) {
    if (Math.abs(prev[i] - next[i]) > MIN_BBOX_DELTA) return true
  }
  return false
}

/**
 * Capture a JPEG data URL of the face-bbox region from the live WHEP `<video>`.
 *
 * The video's srcObject is a MediaStream from WebRTC — not cross-origin, so
 * `drawImage` + `toDataURL` are not tainted and no `crossOrigin` attribute is
 * needed. Output is always the same size regardless of bbox area so the
 * thumbnail slot in the sheet stays stable.
 *
 * Phase-1 caveat: the admin's WHEP pipe is the 640×360 sub profile, so the
 * resulting crop is low-res. Phase 3 replaces this with a server-side crop
 * taken from the main 2304×1296 stream. Shape + output match
 * `useServerSideCrop` so `LiveCropPanel` doesn't care which one fed it.
 */
export function useClientSideCrop({
  videoElement,
  bbox,
  trackId,
  isStale,
  isSubStream,
}: UseClientSideCropArgs): LiveCropResult {
  const [dataUrl, setDataUrl] = useState<string | null>(null)
  const [status, setStatus] = useState<LiveCropResult['status']>('idle')
  const [capturedAt, setCapturedAt] = useState<number | null>(null)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const lastBboxRef = useRef<[number, number, number, number] | null>(null)
  const lastCaptureAtRef = useRef<number>(0)
  const lastTrackIdRef = useRef<number | null>(null)

  // Reset state when the selected track changes — prevents flashing the
  // previous student's crop while the first frame for the new one is captured.
  useEffect(() => {
    if (lastTrackIdRef.current !== trackId) {
      lastTrackIdRef.current = trackId
      lastBboxRef.current = null
      setDataUrl(null)
      setCapturedAt(null)
      setStatus('loading')
    }
  }, [trackId])

  useEffect(() => {
    if (!videoElement || !bbox || trackId === null) {
      if (!dataUrl) setStatus('loading')
      return
    }

    // HAVE_CURRENT_DATA or better — we need pixels to draw.
    if (videoElement.readyState < 2) {
      setStatus('loading')
      return
    }

    const vw = videoElement.videoWidth
    const vh = videoElement.videoHeight
    if (vw <= 0 || vh <= 0) {
      setStatus('loading')
      return
    }

    // Pad bbox + clamp. Degenerate (off-screen) bboxes freeze the last good crop.
    const bw = bbox[2] - bbox[0]
    const bh = bbox[3] - bbox[1]
    const x1n = Math.max(0, bbox[0] - BBOX_PADDING * bw)
    const y1n = Math.max(0, bbox[1] - BBOX_PADDING * bh)
    const x2n = Math.min(1, bbox[2] + BBOX_PADDING * bw)
    const y2n = Math.min(1, bbox[3] + BBOX_PADDING * bh)
    const sx = x1n * vw
    const sy = y1n * vh
    const sw = (x2n - x1n) * vw
    const sh = (y2n - y1n) * vh

    if (sw < 4 || sh < 4) {
      // Track is practically off-screen — keep whatever we have, mark stale.
      if (dataUrl) setStatus('stale')
      return
    }

    const now = performance.now()
    const forceCapture = dataUrl === null // first frame for this selection
    const bboxMoved = hasBboxChanged(lastBboxRef.current, bbox)
    const intervalElapsed = now - lastCaptureAtRef.current >= MIN_CAPTURE_INTERVAL_MS

    if (!forceCapture && (!bboxMoved || !intervalElapsed)) {
      // Nothing worth recapturing — but mark ok if we already have a crop.
      if (dataUrl) setStatus(isStale ? 'stale' : 'ok')
      return
    }

    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas')
      canvasRef.current.width = OUTPUT_SIZE
      canvasRef.current.height = OUTPUT_SIZE
    }
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    try {
      // Fill black first so non-square source regions don't leak a prior frame.
      ctx.fillStyle = '#000000'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Preserve aspect by letterboxing inside OUTPUT_SIZE × OUTPUT_SIZE.
      const cropAspect = sw / sh
      let dw = canvas.width
      let dh = canvas.height
      let dx = 0
      let dy = 0
      if (cropAspect > 1) {
        dh = canvas.height / cropAspect
        dy = (canvas.height - dh) / 2
      } else if (cropAspect < 1) {
        dw = canvas.width * cropAspect
        dx = (canvas.width - dw) / 2
      }

      ctx.drawImage(videoElement, sx, sy, sw, sh, dx, dy, dw, dh)
      const url = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
      lastBboxRef.current = bbox
      lastCaptureAtRef.current = now
      setDataUrl(url)
      setCapturedAt(now)
      setStatus(isStale ? 'stale' : 'ok')
    } catch {
      // Drawing can throw if the video becomes tainted (shouldn't for WebRTC)
      // — log and keep the last good crop.
      if (!dataUrl) setStatus('error')
    }
  }, [videoElement, bbox, trackId, isStale, dataUrl])

  // Flip status between ok/stale as the parent toggles isStale without a new bbox.
  useEffect(() => {
    if (!dataUrl) return
    setStatus(isStale ? 'stale' : 'ok')
  }, [isStale, dataUrl])

  return {
    status,
    dataUrl,
    capturedAt,
    resolutionHint: {
      sourceWidth: videoElement?.videoWidth ?? 0,
      sourceHeight: videoElement?.videoHeight ?? 0,
      isSubStream,
    },
  }
}

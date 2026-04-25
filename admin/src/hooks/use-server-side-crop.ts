import { useEffect, useMemo, useRef, useState } from 'react'

import { useAuthedImage } from './use-authed-image'
import type { RecognitionEventMessage } from './use-attendance-ws'
import type { LiveCropResult } from '@/types'

/**
 * Server-side live crop, driven by the WS recognition-event stream.
 *
 * Old behavior: polled `/face/live-crops/{schedule}/{user}` every 3s. That
 * endpoint only returns crops the pipeline saved on the warming_up →
 * recognized transition (one per `(user_id, track_id)` pair, see
 * `_recognized_captured` in backend/app/services/realtime_pipeline.py),
 * so once a track was bound to a student, the panel froze on whichever
 * single frame happened to be captured first. Operators saw the crop
 * "never updating" even as fresh recognition events scrolled by in the
 * Recognition Stream panel.
 *
 * New behavior: every FAISS decision (~10 fps when a face is in frame)
 * emits a `recognition_event` over the attendance WS, each carrying a
 * `crop_urls.live` URL to the actual frame the ML decided on. We surface
 * the newest matching event for the selected user — so the panel ticks
 * forward in real time exactly like the Recognition Stream, just filtered
 * to one student.
 *
 * Flicker control: ML inference at 10 fps would swap the `<img src>` 10
 * times per second, churning the useAuthedImage blob cache and looking
 * twitchy. We throttle the visible swap to once per `THROTTLE_MS` (~800ms)
 * — the latest event still drives the URL, but the actual update is
 * coalesced. When events stop arriving (student leaves frame), the last
 * shown crop persists, which is what we want.
 */

const THROTTLE_MS = 800

export function useServerSideCrop({
  scheduleId,
  userId,
  recognitionEvents,
}: {
  scheduleId: string
  userId: string | null
  recognitionEvents: RecognitionEventMessage[]
}): LiveCropResult {
  const enabled = !!scheduleId && !!userId

  // Newest matching event from the WS stream. The events array is already
  // newest-first (see `mergeRecognitionEvents` in use-attendance-ws), so
  // `.find` returns the most recent hit without an extra sort.
  const newest = useMemo(() => {
    if (!enabled) return null
    return (
      recognitionEvents.find(
        (e) =>
          e.schedule_id === scheduleId &&
          e.student_id === userId &&
          !!e.crop_urls?.live,
      ) ?? null
    )
  }, [enabled, recognitionEvents, scheduleId, userId])

  // Throttled "shown" event — the source of truth for what URL the panel
  // is currently displaying. Update at most every THROTTLE_MS so the image
  // doesn't flicker at recognition fps.
  const [shown, setShown] = useState<RecognitionEventMessage | null>(null)
  const lastSwapAtRef = useRef<number>(0)

  useEffect(() => {
    if (!newest) {
      // No matching event yet — leave the previously shown crop in place
      // (or null on first run). This is the "loading" state for status.
      return
    }
    if (shown?.event_id === newest.event_id) return

    const now = performance.now()
    const elapsed = now - lastSwapAtRef.current
    if (elapsed >= THROTTLE_MS) {
      setShown(newest)
      lastSwapAtRef.current = now
      return
    }
    // Defer the swap so the *latest* event at the throttle boundary wins.
    const timer = setTimeout(() => {
      setShown(newest)
      lastSwapAtRef.current = performance.now()
    }, THROTTLE_MS - elapsed)
    return () => clearTimeout(timer)
  }, [newest, shown?.event_id])

  // Reset when the selection changes — otherwise the previous student's
  // crop briefly bleeds through while the next one's events arrive.
  useEffect(() => {
    setShown(null)
    lastSwapAtRef.current = 0
  }, [scheduleId, userId])

  const cropUrl = shown?.crop_urls?.live ?? null
  const { src, loading, error } = useAuthedImage(cropUrl)

  const status: LiveCropResult['status'] = useMemo(() => {
    if (!enabled) return 'idle'
    if (error) return 'error'
    if (!shown) return 'loading' // waiting for first matching event
    if (loading) return 'loading'
    if (src) return 'ok'
    return 'loading'
  }, [enabled, error, shown, loading, src])

  return {
    status,
    dataUrl: src ?? null,
    capturedAt: shown ? shown.server_time_ms : null,
    resolutionHint:
      status === 'ok'
        ? { sourceWidth: 2304, sourceHeight: 1296, isSubStream: false }
        : undefined,
    errorMessage: error?.message,
  }
}

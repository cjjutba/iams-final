import { useEffect, useMemo, useRef, useState } from 'react'

import { useAuthedImage } from './use-authed-image'
import type {
  LiveCropUpdateMessage,
  RecognitionEventMessage,
} from './use-attendance-ws'
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
  liveCrop,
}: {
  scheduleId: string
  userId: string | null
  recognitionEvents: RecognitionEventMessage[]
  /** Fast-lane live-display crop (~1 Hz) for this user. Overrides the
   *  recognition_event fallback when present. See LiveCropSource type. */
  liveCrop: LiveCropUpdateMessage | null
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
  //
  // Selection-change reset is folded into this same effect (rather than a
  // separate `useEffect([scheduleId, userId])` reset) because effect order
  // matters: a separate reset effect that fires after this one would clobber
  // the initial setShown on first mount and the panel would hang on
  // "Waiting for first frame…" forever (or until the *next* matching
  // event arrived). Detecting a selection swap by comparing the new event's
  // identity vs. the currently-shown event's identity avoids that race.
  const [shown, setShown] = useState<RecognitionEventMessage | null>(null)
  const lastSwapAtRef = useRef<number>(0)

  useEffect(() => {
    // Disabled selection or no matching event yet — clear any previously
    // shown crop so a newly opened sheet for an unrecognized student
    // doesn't briefly inherit the last visible one.
    if (!enabled || !newest) {
      if (shown !== null) setShown(null)
      return
    }
    // Same event already showing — nothing to do.
    if (shown?.event_id === newest.event_id) return

    // Selection changed (different schedule or student) → swap immediately,
    // bypassing the throttle so the operator sees the new selection's
    // first frame the moment they switch.
    const isFreshSelection =
      !shown ||
      shown.schedule_id !== newest.schedule_id ||
      shown.student_id !== newest.student_id
    if (isFreshSelection) {
      setShown(newest)
      lastSwapAtRef.current = performance.now()
      return
    }

    // Same selection, newer event → throttle the visible swap so we don't
    // churn the <img src> at 10 fps. The latest event at the throttle
    // boundary wins.
    const now = performance.now()
    const elapsed = now - lastSwapAtRef.current
    if (elapsed >= THROTTLE_MS) {
      setShown(newest)
      lastSwapAtRef.current = now
      return
    }
    const timer = setTimeout(() => {
      setShown(newest)
      lastSwapAtRef.current = performance.now()
    }, THROTTLE_MS - elapsed)
    return () => clearTimeout(timer)
  }, [enabled, newest, shown])

  const cropUrl = shown?.crop_urls?.live ?? null
  const { src, loading, error } = useAuthedImage(cropUrl)

  // Fast-lane override candidate: when a `live_crop_update` for this exact
  // (schedule, user) is present, the panel will render its inline base64
  // JPEG and skip the recognition_event fallback below. The pipeline
  // broadcasts these at ~1 Hz (LIVE_DISPLAY_BROADCAST_HZ) so the panel
  // refreshes ~once per second instead of inheriting evidence_writer's
  // 10 s persistence throttle. We still call all hooks unconditionally so
  // the fallback is ready the moment the live broadcast stops landing.
  const liveDataUrl = useMemo(() => {
    if (!enabled || !liveCrop) return null
    if (
      liveCrop.schedule_id !== scheduleId ||
      liveCrop.user_id !== userId
    )
      return null
    return `data:image/jpeg;base64,${liveCrop.crop_b64}`
  }, [enabled, liveCrop, scheduleId, userId])

  const status: LiveCropResult['status'] = useMemo(() => {
    if (!enabled) return 'idle'
    if (error) return 'error'
    if (!shown) return 'loading' // waiting for first matching event
    if (loading) return 'loading'
    if (src) return 'ok'
    return 'loading'
  }, [enabled, error, shown, loading, src])

  // Branch on the final result (not the hooks).
  if (liveDataUrl && liveCrop) {
    return {
      status: 'ok',
      dataUrl: liveDataUrl,
      capturedAt: liveCrop.captured_at_ms,
      resolutionHint: { sourceWidth: 2304, sourceHeight: 1296, isSubStream: false },
    }
  }

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

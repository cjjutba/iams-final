import { useEffect, useRef, useState } from 'react'

import { recognitionsService } from '@/services/recognitions.service'
import type { RecognitionEvent } from '@/types'

// Message shapes broadcast by the backend's /api/v1/ws/attendance/{schedule_id}
// endpoint. See backend/app/services/realtime_pipeline.py for the producer
// and android/app/src/main/java/com/iams/app/data/api/AttendanceWebSocketClient.kt
// for the mobile consumer (currently; removed in Phase 9 of this plan).

export interface TrackInfo {
  track_id: number
  bbox: [number, number, number, number] // normalized [x1, y1, x2, y2] in 0-1
  /**
   * Per-track motion in CENTER+SIZE space (cx_vel, cy_vel, w_vel, h_vel),
   * normalized units per second. Used by the DetectionOverlay to extrapolate
   * bbox positions between WS frames so the box glides smoothly at 60 fps
   * instead of teleporting every ~227 ms at the onprem ~4 fps backend rate.
   */
  velocity?: [number, number, number, number]
  name: string | null
  confidence: number
  user_id: string | null
  status: 'recognized' | 'unknown' | 'detecting'
  recognition_state?: string
}

export interface FrameUpdateMessage {
  type: 'frame_update'
  tracks: TrackInfo[]
  frame_size?: { width: number; height: number }
  fps?: number
  processing_ms?: number
  server_time_ms?: number
  frame_sequence?: number
  /**
   * Per-stage timing breakdown added on 2026-04-25 (live-feed plan Step 2a)
   * so the live page HUD can show where the per-frame budget is going.
   * `other_ms` = `processing_ms - det_ms - embed_ms - faiss_ms` — when it
   * dominates, the bottleneck has moved off ML and into the rest of the
   * pipeline (NMS, ByteTrack, identity bookkeeping). All four are optional
   * so older backend builds remain forward-compatible.
   */
  det_ms?: number
  embed_ms?: number
  faiss_ms?: number
  other_ms?: number
  /**
   * Upstream RTP 90 kHz timestamp of the source RTSP frame this update
   * describes. Added for Step 3 (frame-pinning); the live overlay uses
   * this with `requestVideoFrameCallback().rtpTimestamp` from the WHEP
   * `<video>` to align bbox draws with the matching video frame. Optional
   * because pre-Step-3 backends do not emit it.
   */
  rtp_pts_90k?: number
}

export interface AttendanceStatusEntry {
  user_id: string
  student_id?: string
  name: string
  status: 'present' | 'late' | 'absent' | 'early_leave' | 'early_leave_returned'
  check_in_time?: string | null
  early_leave_time?: string | null
  return_time?: string | null
}

export interface AttendanceSummaryMessage {
  type: 'attendance_summary'
  present_count: number
  late_count: number
  absent_count: number
  early_leave_count: number
  early_leave_returned_count: number
  total_enrolled: number
  present: AttendanceStatusEntry[]
  late: AttendanceStatusEntry[]
  absent: AttendanceStatusEntry[]
  early_leave: AttendanceStatusEntry[]
  early_leave_returned: AttendanceStatusEntry[]
}

// Session lifecycle events published by PresenceService._publish_attendance.
// Note the `event` (not `type`) field — they share the WS channel with
// frame_update / attendance_summary messages but use a different envelope.
export interface SessionEventMessage {
  event: 'session_start' | 'session_end'
  schedule_id: string
  subject_code?: string
  subject_name?: string
  [key: string]: unknown
}

// Recognition-evidence event, pushed by backend/app/services/evidence_writer.py
// once per FAISS decision (match, miss, or ambiguous). The live-feed panel
// subscribes to these and renders a streaming list next to the video.
// Fields mirror RecognitionEventDraft + the writer's _broadcast_batch payload.
export interface RecognitionEventMessage {
  type: 'recognition_event'
  event_id: string
  schedule_id: string
  student_id: string | null
  track_id: number
  camera_id: string
  frame_idx: number
  similarity: number
  threshold_used: number
  matched: boolean
  is_ambiguous: boolean
  det_score: number
  bbox: { x1: number; y1: number; x2: number; y2: number }
  model_name: string
  server_time_ms: number
  crop_urls: {
    live: string
    registered: string | null
  }
  student_name?: string | null
}

export type AttendanceWsMessage =
  | FrameUpdateMessage
  | AttendanceSummaryMessage
  | SessionEventMessage
  | RecognitionEventMessage
  | { type?: string; event?: string; [key: string]: unknown }

/** Bounded ring-buffer size for the recognition-event stream.
 * 500 rows is enough to scroll back ~1 min at 8 fps, bounded memory. */
const RECOGNITION_BUFFER_MAX = 500

/** How many recent rows to backfill from REST on (re)mount so the panel
 * survives a page refresh instead of resetting to 0. The page already shows
 * "filteredCount / total" so capping below the WS ring keeps both numbers
 * meaningful while still recovering the most recent ~minutes of decisions.
 */
const RECOGNITION_BACKFILL_LIMIT = 200

/**
 * Convert a persisted REST recognition row into the same envelope the WS
 * pushes, so the consumer (RecognitionPanel) doesn't have to know there
 * were two sources. The WS uses ``server_time_ms`` for relative-time
 * formatting; we synthesise it from ``created_at`` (DB millisecond truth).
 */
function restEventToMessage(r: RecognitionEvent): RecognitionEventMessage {
  return {
    type: 'recognition_event',
    event_id: r.event_id,
    schedule_id: r.schedule_id,
    student_id: r.student_id,
    track_id: r.track_id,
    camera_id: r.camera_id,
    frame_idx: r.frame_idx,
    similarity: r.similarity,
    threshold_used: r.threshold_used,
    matched: r.matched,
    is_ambiguous: r.is_ambiguous,
    det_score: r.det_score,
    bbox: r.bbox,
    model_name: r.model_name,
    server_time_ms: new Date(r.created_at).getTime(),
    crop_urls: r.crop_urls,
    student_name: r.student_name,
  }
}

/**
 * Merge two newest-first event lists, dedup by ``event_id``, and re-sort by
 * ``server_time_ms`` desc. Used when REST backfill races with live WS
 * arrivals: either could land first, and a row briefly persisted to the DB
 * mid-flight may appear in both.
 */
function mergeRecognitionEvents(
  current: RecognitionEventMessage[],
  incoming: RecognitionEventMessage[],
): RecognitionEventMessage[] {
  const seen = new Set<string>()
  const merged: RecognitionEventMessage[] = []
  for (const e of current) {
    if (seen.has(e.event_id)) continue
    seen.add(e.event_id)
    merged.push(e)
  }
  for (const e of incoming) {
    if (seen.has(e.event_id)) continue
    seen.add(e.event_id)
    merged.push(e)
  }
  merged.sort((a, b) => (b.server_time_ms ?? 0) - (a.server_time_ms ?? 0))
  if (merged.length > RECOGNITION_BUFFER_MAX) {
    merged.length = RECOGNITION_BUFFER_MAX
  }
  return merged
}

interface UseAttendanceWsReturn {
  isConnected: boolean
  latestFrame: FrameUpdateMessage | null
  latestSummary: AttendanceSummaryMessage | null
  latestSessionEvent: SessionEventMessage | null
  /** Newest-first bounded log of recognition events seen this session. */
  recognitionEvents: RecognitionEventMessage[]
}

/**
 * Schedule-scoped WebSocket hook for the admin portal's live-feed page.
 *
 * This is a peer of use-websocket.ts (which is user-scoped for notifications).
 * It subscribes to /api/v1/ws/attendance/{scheduleId} and keeps the latest
 * frame_update and attendance_summary messages in state so consumers (the
 * canvas overlay + side panel) can re-render on each broadcast.
 *
 * Connection lifecycle:
 * - Opens on mount if scheduleId is truthy.
 * - Closes on unmount or when scheduleId changes.
 * - Reconnects up to 3 times with 5 s backoff on unexpected close.
 *
 * Message shape: the hook stores the raw backend payload — overlay and panel
 * components read from latestFrame.tracks and latestSummary directly.
 */
export function useAttendanceWs(scheduleId: string | null | undefined): UseAttendanceWsReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [latestFrame, setLatestFrame] = useState<FrameUpdateMessage | null>(null)
  const [latestSummary, setLatestSummary] = useState<AttendanceSummaryMessage | null>(null)
  const [latestSessionEvent, setLatestSessionEvent] = useState<SessionEventMessage | null>(null)
  const [recognitionEvents, setRecognitionEvents] = useState<RecognitionEventMessage[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)
  const MAX_ATTEMPTS = 3

  useEffect(() => {
    // Reset per-schedule state on every (re)mount so a navigation between
    // two live pages (or a remount in dev) doesn't leak the previous
    // schedule's events into the new view before the WS / backfill catch up.
    // The setStates are intentional and only fire when `scheduleId` actually
    // changes — this is the effect's only dep — so the cascading-render
    // concern from `react-hooks/set-state-in-effect` does not apply here.
    /* eslint-disable react-hooks/set-state-in-effect */
    setIsConnected(false)
    setLatestFrame(null)
    setLatestSummary(null)
    setLatestSessionEvent(null)
    setRecognitionEvents([])
    /* eslint-enable react-hooks/set-state-in-effect */

    if (!scheduleId) return

    let cancelled = false

    // REST backfill: hydrate the panel with the most recent decisions for
    // this schedule so a page refresh doesn't reset the counter to 0. The
    // request is fire-and-forget — failures are non-fatal because the WS
    // remains the source of truth for live updates.
    recognitionsService
      .list({
        schedule_id: scheduleId,
        limit: RECOGNITION_BACKFILL_LIMIT,
      })
      .then((res) => {
        if (cancelled) return
        const restEvents = res.items.map(restEventToMessage)
        if (restEvents.length === 0) return
        setRecognitionEvents((prev) => mergeRecognitionEvents(prev, restEvents))
      })
      .catch(() => {
        // Recognition routes may be disabled (VPS thin profile) or the
        // user may not have admin rights; either way, fall back to a
        // pure-WS view rather than surfacing an error toast.
      })

    const connect = () => {
      if (cancelled) return

      const wsEnv = String(import.meta.env.VITE_WS_URL ?? '').trim()
      // If no explicit WS URL and we're on HTTPS (Vercel), skip — Vercel can't
      // proxy WebSocket. The onprem nginx serves over plain HTTP on the LAN,
      // so this branch rarely fires in the intended deployment.
      if (!wsEnv && window.location.protocol === 'https:') {
        return
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = wsEnv || `${protocol}//${window.location.host}`
      const token = localStorage.getItem('access_token')
      const url = `${host}/api/v1/ws/attendance/${scheduleId}${token ? `?token=${token}` : ''}`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) {
          ws.close()
          return
        }
        console.log('[attendance-ws] connected', scheduleId)
        attemptsRef.current = 0
        setIsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as AttendanceWsMessage
          if (data.type === 'frame_update') {
            setLatestFrame(data as FrameUpdateMessage)
          } else if (data.type === 'attendance_summary') {
            setLatestSummary(data as AttendanceSummaryMessage)
          } else if (data.event === 'session_start' || data.event === 'session_end') {
            // Session lifecycle events let the live page flip its
            // Start/End button without waiting for the next 10 s REST
            // poll of /presence/sessions/active.
            setLatestSessionEvent(data as SessionEventMessage)
          } else if (data.type === 'recognition_event') {
            // Bounded newest-first ring. Every FAISS decision produces one
            // of these; at 8 fps with 2-3 tracks that's ~20-30/sec so we
            // need to cap the buffer to keep the DOM reasonable. Dedup
            // against the buffer so an event that races between the REST
            // backfill and the live WS push doesn't render twice.
            const evt = data as RecognitionEventMessage
            setRecognitionEvents((prev) => {
              if (prev.some((e) => e.event_id === evt.event_id)) return prev
              const next = [evt, ...prev]
              if (next.length > RECOGNITION_BUFFER_MAX) {
                next.length = RECOGNITION_BUFFER_MAX
              }
              return next
            })
          }
          // Other message types (scan_result, pong, etc.) are ignored here —
          // the realtime pipeline sends them but the admin live-feed page
          // only cares about per-frame tracks + periodic summaries.
        } catch {
          // Non-JSON frame (e.g. keepalive pong) — ignore.
        }
      }

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null
          setIsConnected(false)
        }
        if (!cancelled && attemptsRef.current < MAX_ATTEMPTS) {
          attemptsRef.current += 1
          console.warn('[attendance-ws] disconnected — retrying', attemptsRef.current)
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = setTimeout(connect, 5000)
        }
      }

      ws.onerror = () => {
        // onclose handles reconnect.
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setIsConnected(false)
    }
  }, [scheduleId])

  return {
    isConnected,
    latestFrame,
    latestSummary,
    latestSessionEvent,
    recognitionEvents,
  }
}

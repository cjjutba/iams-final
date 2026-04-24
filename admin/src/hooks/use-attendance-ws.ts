import { useEffect, useRef, useState } from 'react'

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
    if (!scheduleId) {
      setIsConnected(false)
      setLatestFrame(null)
      setLatestSummary(null)
      setLatestSessionEvent(null)
      setRecognitionEvents([])
      return
    }

    let cancelled = false

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
            // need to cap the buffer to keep the DOM reasonable.
            const evt = data as RecognitionEventMessage
            setRecognitionEvents((prev) => {
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

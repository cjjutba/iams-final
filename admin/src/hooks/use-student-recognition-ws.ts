import { useEffect, useRef, useState } from 'react'

import { recognitionsService } from '@/services/recognitions.service'
import type { RecognitionEvent } from '@/types'

/**
 * Live recognition stream for one student, used by the "Recent detections"
 * panel on the Student Record Detail page.
 *
 * Two data sources are merged into one newest-first list:
 *
 *   1. REST backfill on mount — `GET /recognitions?student_id=...` so a fresh
 *      page load already has the most recent persisted decisions, even if
 *      no new events arrive for a while (between sessions, after hours).
 *   2. WebSocket push from `/api/v1/ws/student/{studentId}` — every new
 *      `recognition_event` the backend persists for this student is fanned
 *      out here in real time. We dedupe by `event_id` so a row that races
 *      between the REST backfill and a fast WS arrival never renders twice.
 *
 * Lifecycle:
 *   - Open WS on mount, close on unmount or studentId change.
 *   - Reconnect up to 3 times with 5 s backoff on unexpected close.
 *   - Resets all state when studentId changes so navigating between two
 *     student pages doesn't bleed events from one into the other.
 */

// Backend recognition_event WS payload shape — mirrored from
// backend/app/services/evidence_writer.py::_broadcast_batch.
interface RecognitionEventWsMessage {
  type: 'recognition_event'
  event_id: string
  schedule_id: string
  student_id: string | null
  student_name: string | null
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
  crop_urls: { live: string; registered: string | null }
}

const RECOGNITION_BUFFER_MAX = 200
const RECOGNITION_BACKFILL_LIMIT = 50

/**
 * Convert a WS push into the same `RecognitionEvent` shape the REST endpoint
 * returns, so the consuming component (`DetectionHistoryList`) sees one
 * uniform list and doesn't have to branch on source.
 *
 * `schedule_subject` and `embedding_norm` aren't included in the WS payload
 * — `schedule_subject` is a join-derived label and `embedding_norm` only
 * matters for the analytics pages. The detection-row UI falls back to a
 * generic "Schedule" label when subject is null, and never reads
 * embedding_norm, so synthesising sane defaults is safe.
 */
function wsMessageToEvent(msg: RecognitionEventWsMessage): RecognitionEvent {
  return {
    event_id: msg.event_id,
    schedule_id: msg.schedule_id,
    schedule_subject: null,
    student_id: msg.student_id,
    student_name: msg.student_name,
    track_id: msg.track_id,
    camera_id: msg.camera_id,
    frame_idx: msg.frame_idx,
    similarity: msg.similarity,
    threshold_used: msg.threshold_used,
    matched: msg.matched,
    is_ambiguous: msg.is_ambiguous,
    det_score: msg.det_score,
    embedding_norm: 0,
    bbox: msg.bbox,
    model_name: msg.model_name,
    crop_urls: msg.crop_urls,
    created_at: new Date(msg.server_time_ms).toISOString(),
  }
}

interface UseStudentRecognitionWsReturn {
  events: RecognitionEvent[]
  isConnected: boolean
  isLoading: boolean
  error: Error | null
}

export function useStudentRecognitionWs(
  studentId: string | null | undefined,
): UseStudentRecognitionWsReturn {
  const [events, setEvents] = useState<RecognitionEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isLoading, setIsLoading] = useState<boolean>(Boolean(studentId))
  const [error, setError] = useState<Error | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)
  const MAX_ATTEMPTS = 3

  useEffect(() => {
    // Reset every time studentId changes so navigation between two student
    // detail pages never leaks the previous student's events.
    /* eslint-disable react-hooks/set-state-in-effect */
    setEvents([])
    setIsConnected(false)
    setError(null)
    setIsLoading(Boolean(studentId))
    /* eslint-enable react-hooks/set-state-in-effect */

    if (!studentId) return

    let cancelled = false

    // 1) REST backfill — the panel must show recent history immediately,
    //    even if no new events arrive for the rest of the page lifetime.
    recognitionsService
      .list({ student_id: studentId, limit: RECOGNITION_BACKFILL_LIMIT })
      .then((res) => {
        if (cancelled) return
        setEvents((prev) => mergeEvents(prev, res.items))
      })
      .catch((e) => {
        if (cancelled) return
        // Recognitions routes may be disabled (VPS thin profile) or the
        // user may lack admin rights. Surface the error so the existing
        // `isError` UI in DetectionHistoryList still works as a fallback.
        setError(e instanceof Error ? e : new Error(String(e)))
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    // 2) Live WS — connect to /ws/student/{id}.
    const connect = () => {
      if (cancelled) return

      const wsEnv = String(import.meta.env.VITE_WS_URL ?? '').trim()
      if (!wsEnv && window.location.protocol === 'https:') {
        // No explicit WS URL on HTTPS (Vercel) — proxying isn't available.
        // The REST backfill already populated the panel; we just won't get
        // live updates in that environment.
        return
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = wsEnv || `${protocol}//${window.location.host}`
      const token = localStorage.getItem('access_token')
      const url = `${host}/api/v1/ws/student/${studentId}${
        token ? `?token=${token}` : ''
      }`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) {
          ws.close()
          return
        }
        attemptsRef.current = 0
        setIsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as { type?: string }
          if (data.type !== 'recognition_event') return
          const msg = data as unknown as RecognitionEventWsMessage
          // Server-side fanout is already filtered by student_id, but
          // double-check defensively in case routing logic ever changes.
          if (msg.student_id && msg.student_id !== studentId) return
          const next = wsMessageToEvent(msg)
          setEvents((prev) => {
            if (prev.some((e) => e.event_id === next.event_id)) return prev
            const merged = [next, ...prev]
            if (merged.length > RECOGNITION_BUFFER_MAX) {
              merged.length = RECOGNITION_BUFFER_MAX
            }
            return merged
          })
        } catch {
          // Non-JSON keepalive — ignore.
        }
      }

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null
          setIsConnected(false)
        }
        if (!cancelled && attemptsRef.current < MAX_ATTEMPTS) {
          attemptsRef.current += 1
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
  }, [studentId])

  return { events, isConnected, isLoading, error }
}

/**
 * Merge two newest-first lists, dedup by event_id, and re-sort by
 * created_at desc. Used when REST backfill races with WS arrivals.
 */
function mergeEvents(
  current: RecognitionEvent[],
  incoming: RecognitionEvent[],
): RecognitionEvent[] {
  const seen = new Set<string>()
  const merged: RecognitionEvent[] = []
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
  merged.sort((a, b) => {
    const aT = new Date(a.created_at).getTime()
    const bT = new Date(b.created_at).getTime()
    return bT - aT
  })
  if (merged.length > RECOGNITION_BUFFER_MAX) {
    merged.length = RECOGNITION_BUFFER_MAX
  }
  return merged
}

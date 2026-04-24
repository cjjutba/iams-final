import { useEffect, useRef, useState } from 'react'
import type { ActivityEvent, ActivityWsMessage } from '@/types'

interface ActivityWsFilters {
  event_type?: string // CSV
  category?: string
  severity?: string
  schedule_id?: string
  student_id?: string
}

interface UseActivityWsOptions {
  enabled?: boolean
  filters?: ActivityWsFilters
  onEvent?: (event: ActivityEvent) => void
}

interface UseActivityWsReturn {
  isConnected: boolean
  latestEvent: ActivityEvent | null
  reconnect: () => void
}

/**
 * System Activity live-tail WebSocket hook.
 *
 * Subscribes to /api/v1/ws/events with server-side filters snapshotted at
 * connect time. To change filters, the hook reconnects (closing and
 * reopening the socket) — this keeps per-message filter logic trivial on
 * the server side.
 *
 * Reconnects up to 3 times with 5 s backoff on unexpected close.
 * Admin-only: the backend rejects non-admin JWTs with 4003 on handshake.
 */
export function useActivityWs(
  options: UseActivityWsOptions = {},
): UseActivityWsReturn {
  const { enabled = true, filters = {}, onEvent } = options

  const [isConnected, setIsConnected] = useState(false)
  const [latestEvent, setLatestEvent] = useState<ActivityEvent | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)
  const onEventRef = useRef(onEvent)
  const MAX_ATTEMPTS = 3

  // Keep latest onEvent callback in a ref so we don't reopen the socket
  // every time the caller rebuilds its handler.
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  // Stringify filters so changes retrigger the effect without referential
  // churn on new {} literals from the caller.
  const filtersKey = [
    filters.event_type ?? '',
    filters.category ?? '',
    filters.severity ?? '',
    filters.schedule_id ?? '',
    filters.student_id ?? '',
  ].join('|')

  const reconnect = () => {
    attemptsRef.current = 0
    if (wsRef.current) {
      wsRef.current.close()
    }
  }

  useEffect(() => {
    if (!enabled) {
      setIsConnected(false)
      return
    }

    let cancelled = false

    const connect = () => {
      if (cancelled) return

      const wsEnv = String(import.meta.env.VITE_WS_URL ?? '').trim()
      if (!wsEnv && window.location.protocol === 'https:') {
        // Vercel can't proxy WS — on HTTPS origins we need an explicit
        // VITE_WS_URL. Skip rather than attempt a broken ws:// connect.
        return
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = wsEnv || `${protocol}//${window.location.host}`
      const token = localStorage.getItem('access_token')

      const qs = new URLSearchParams()
      if (token) qs.set('token', token)
      if (filters.event_type) qs.set('event_type', filters.event_type)
      if (filters.category) qs.set('category', filters.category)
      if (filters.severity) qs.set('severity', filters.severity)
      if (filters.schedule_id) qs.set('schedule_id', filters.schedule_id)
      if (filters.student_id) qs.set('student_id', filters.student_id)

      const url = `${host}/api/v1/ws/events${qs.toString() ? `?${qs.toString()}` : ''}`
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
          const data = JSON.parse(event.data) as ActivityWsMessage
          if (data && data.type === 'activity_event' && data.event_id) {
            setLatestEvent(data)
            onEventRef.current?.(data)
          }
        } catch {
          // Non-JSON / pong / malformed — ignore.
        }
      }

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null
          setIsConnected(false)
        }
        if (!cancelled && attemptsRef.current < MAX_ATTEMPTS) {
          attemptsRef.current += 1
          if (reconnectTimeoutRef.current)
            clearTimeout(reconnectTimeoutRef.current)
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
      if (reconnectTimeoutRef.current)
        clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setIsConnected(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, filtersKey])

  return { isConnected, latestEvent, reconnect }
}

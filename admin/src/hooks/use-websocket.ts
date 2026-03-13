import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '@/stores/auth.store'

type MessageHandler = (data: any) => void

export function useWebSocket(onMessage?: MessageHandler) {
  const user = useAuthStore((s) => s.user)
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (!user) return

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}`
    const ws = new WebSocket(`${wsUrl}/api/v1/ws/${user.id}`)

    ws.onopen = () => {
      setIsConnected(true)
      console.log('[WS] Connected')
    }

    ws.onclose = () => {
      setIsConnected(false)
      console.log('[WS] Disconnected, reconnecting in 5s...')
      reconnectTimeoutRef.current = setTimeout(connect, 5000)
    }

    ws.onerror = (error) => {
      console.error('[WS] Error:', error)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessageRef.current?.(data)
      } catch {
        // Ignore non-JSON messages (like pings)
      }
    }

    wsRef.current = ws
  }, [user])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeoutRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { isConnected }
}

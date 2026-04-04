import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '@/stores/auth.store'

type MessageHandler = (data: unknown) => void

// Singleton WebSocket connection shared across all hook instances
let sharedWs: WebSocket | null = null
let sharedUserId: string | null = null
const messageHandlers = new Set<MessageHandler>()
let reconnectTimeout: ReturnType<typeof setTimeout> | undefined
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 3

function connectShared(userId: string) {
  // Don't open a new connection if one is already active or connecting
  if (sharedWs && sharedWs.readyState <= WebSocket.OPEN) return

  const wsUrl = String(import.meta.env.VITE_WS_URL ?? '').trim()

  // If no explicit WS URL and we're on HTTPS (e.g. Vercel), skip WebSocket
  // Vercel can't proxy WebSocket connections
  if (!wsUrl && window.location.protocol === 'https:') return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = wsUrl || `${protocol}//${window.location.host}`
  const token = localStorage.getItem('access_token')
  const ws = new WebSocket(`${host}/api/v1/ws/${userId}${token ? `?token=${token}` : ''}`)

  ws.onopen = () => {
    console.log('[WS] Connected')
    reconnectAttempts = 0
  }

  ws.onclose = () => {
    // Only reconnect if we still want to be connected (user still set)
    if (sharedWs === ws) {
      sharedWs = null
      if (sharedUserId && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++
        clearTimeout(reconnectTimeout)
        reconnectTimeout = setTimeout(() => connectShared(userId), 5000)
      }
    }
  }

  ws.onerror = () => {
    // onclose will handle reconnect
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      messageHandlers.forEach((handler) => handler(data))
    } catch {
      // Ignore non-JSON messages
    }
  }

  sharedWs = ws
  sharedUserId = userId
}

function disconnectShared() {
  clearTimeout(reconnectTimeout)
  sharedUserId = null
  if (sharedWs) {
    sharedWs.close()
    sharedWs = null
  }
}

export function useWebSocket(onMessage?: MessageHandler) {
  const user = useAuthStore((s) => s.user)
  const [isConnected, setIsConnected] = useState(false)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  // Stable handler wrapper
  const handlerRef = useRef<MessageHandler>((data) => {
    onMessageRef.current?.(data)
  })

  useEffect(() => {
    if (!user) {
      // User logged out — tear down the singleton
      disconnectShared()
      setIsConnected(false)
      return
    }

    // If user changed, disconnect old
    if (sharedUserId && sharedUserId !== user.id) {
      disconnectShared()
    }

    connectShared(user.id)
    messageHandlers.add(handlerRef.current)

    // Track connection state
    const interval = setInterval(() => {
      setIsConnected(sharedWs?.readyState === WebSocket.OPEN)
    }, 2000)

    return () => {
      messageHandlers.delete(handlerRef.current)
      clearInterval(interval)
      // Don't disconnect the singleton on component unmount —
      // it stays alive for the entire session
    }
  }, [user])

  return { isConnected }
}

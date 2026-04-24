import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AxiosError } from 'axios'

import api from '@/services/api'
import type { LiveCropResult } from '@/types'

interface ServerLiveCrop {
  crop_b64: string
  captured_at: string
  confidence: number
  track_id: number
  bbox: [number, number, number, number]
}

interface ServerLiveCropsResponse {
  schedule_id: string
  user_id: string
  available: boolean
  crops: ServerLiveCrop[]
}

const POLL_INTERVAL_MS = 3000

/**
 * Phase-3 counterpart to `useClientSideCrop`.
 *
 * Polls `GET /api/v1/face/live-crops/{schedule_id}/{user_id}` for the most
 * recent server-captured JPEG (the actual frame the ML pipeline saw, at
 * main-profile 2304×1296 instead of the admin's sub-stream WHEP pipe). When
 * the endpoint returns `available: false` (VPS, Redis down, no crops yet),
 * returns an `idle` status so the caller can render an empty state. Consumers
 * should NOT fall back to the client hook — `useLiveCrop` handles that at a
 * higher level.
 */
export function useServerSideCrop({
  scheduleId,
  userId,
}: {
  scheduleId: string
  userId: string | null
}): LiveCropResult {
  const enabled = !!scheduleId && !!userId
  const query = useQuery<ServerLiveCropsResponse, AxiosError>({
    queryKey: ['face', 'live-crops', scheduleId, userId],
    queryFn: async () => {
      const res = await api.get<ServerLiveCropsResponse>(
        `/face/live-crops/${encodeURIComponent(scheduleId)}/${encodeURIComponent(userId!)}`,
        { params: { limit: 5 } },
      )
      return res.data
    },
    enabled,
    refetchInterval: (q) => (q.state.data?.available ? POLL_INTERVAL_MS : POLL_INTERVAL_MS * 2),
    staleTime: 0,
    retry: false,
  })

  const latest = query.data?.crops?.[0]
  const [dataUrl, setDataUrl] = useState<string | null>(null)
  const lastCapturedAtRef = useRef<string | null>(null)

  // Decode base64 → data URL whenever a new crop arrives. Cached per server
  // timestamp so we only rebuild the string when the top-of-list entry actually
  // changes.
  useEffect(() => {
    if (!latest) return
    if (lastCapturedAtRef.current === latest.captured_at) return
    lastCapturedAtRef.current = latest.captured_at
    setDataUrl(`data:image/jpeg;base64,${latest.crop_b64}`)
  }, [latest])

  const status: LiveCropResult['status'] = useMemo(() => {
    if (!enabled) return 'idle'
    if (query.isLoading) return 'loading'
    if (query.isError) return 'error'
    if (!query.data?.available) return 'idle'
    if (dataUrl) return 'ok'
    return 'loading'
  }, [enabled, query.isLoading, query.isError, query.data?.available, dataUrl])

  return {
    status,
    dataUrl,
    capturedAt: latest ? new Date(latest.captured_at).getTime() : null,
    resolutionHint:
      status === 'ok'
        ? { sourceWidth: 2304, sourceHeight: 1296, isSubStream: false }
        : undefined,
    errorMessage: query.isError ? query.error?.message : undefined,
  }
}

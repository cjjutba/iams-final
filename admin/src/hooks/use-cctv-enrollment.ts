import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cctvEnrollmentService } from '@/services/cctv-enrollment.service'
import type {
  CctvEnrollCommitRequest,
  CctvEnrollPreviewRequest,
  CctvIdentifyRequest,
} from '@/types'

const KEYS = {
  status: ['cctv-enrollment', 'status'] as const,
}

/**
 * Live CCTV-enrollment posture across all students with a phone
 * registration. Refetches every 30 s so progress lands automatically as
 * the operator commits captures during a bulk-enrollment session,
 * and on window focus so coming back to the tab shows the latest counts.
 */
export function useCctvEnrollmentStatus() {
  return useQuery({
    queryKey: KEYS.status,
    queryFn: () => cctvEnrollmentService.status(),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 10_000,
  })
}

/**
 * Single-frame preview before committing. NOT a useQuery — the operator
 * triggers each preview by clicking a button, and we want the latest
 * frame each click rather than React Query caching a stale capture.
 */
export function useCctvEnrollPreview() {
  return useMutation({
    mutationFn: ({
      userId,
      body,
    }: {
      userId: string
      body: CctvEnrollPreviewRequest
    }) => cctvEnrollmentService.preview(userId, body),
  })
}

/**
 * The real 5-capture enrollment. On success, invalidate the status
 * query so the queue + per-room counts reflect the new embeddings.
 */
export function useCctvEnrollCommit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      body,
    }: {
      userId: string
      body: CctvEnrollCommitRequest
    }) => cctvEnrollmentService.commit(userId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.status })
    },
  })
}

/**
 * Camera-first scan — identify every face in one frame against every
 * enrolled student. Drives the "Scan Classroom" tab.
 */
export function useCctvIdentify() {
  return useMutation({
    mutationFn: (body: CctvIdentifyRequest) =>
      cctvEnrollmentService.identify(body),
  })
}

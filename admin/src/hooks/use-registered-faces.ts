import { useQuery } from '@tanstack/react-query'
import { AxiosError } from 'axios'

import { faceRegistrationsService } from '@/services/face-registrations.service'
import type { FaceRegistrationDetail, RegistrationData } from '@/types'

/**
 * Admin-only hook: fetch per-angle registration metadata for the student
 * currently open in the live-feed TrackDetailSheet.
 *
 * Maps the backend response into the discriminated `RegistrationData` union
 * consumed by `RegisteredFaceGallery`. 404 is treated as a first-class
 * "not-registered" state rather than an error.
 */
export function useRegisteredFaces(userId: string | null): { data: RegistrationData } {
  const query = useQuery<FaceRegistrationDetail, AxiosError>({
    queryKey: ['face', 'registration', userId],
    queryFn: () => faceRegistrationsService.get(userId!),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000,
    retry: (failureCount, error) => {
      // 404 = no registration; don't retry.
      if (error.response?.status === 404) return false
      return failureCount < 2
    },
  })

  if (!userId) return { data: { status: 'idle' } }
  if (query.isLoading) return { data: { status: 'loading' } }
  if (query.isError) {
    if (query.error?.response?.status === 404) return { data: { status: 'not-registered' } }
    return { data: { status: 'error', message: query.error?.message ?? 'Failed to load' } }
  }
  if (query.data) {
    if (!query.data.available) return { data: { status: 'not-registered' } }
    return {
      data: {
        status: 'ok',
        registeredAt: query.data.registered_at,
        embeddingDim: query.data.embedding_dim,
        angles: query.data.angles,
      },
    }
  }
  return { data: { status: 'idle' } }
}

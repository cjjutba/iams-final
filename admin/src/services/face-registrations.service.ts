import api from './api'
import type { FaceRegistrationDetail } from '@/types'

/**
 * Admin-only reader for a student's face registration metadata.
 * Hits `GET /api/v1/face/registrations/{user_id}`. Backend returns 403 for
 * non-admin callers (enforced by `get_current_admin`) and `available: false`
 * when no active registration exists.
 */
export const faceRegistrationsService = {
  get: (userId: string) =>
    api
      .get<FaceRegistrationDetail>(`/face/registrations/${encodeURIComponent(userId)}`)
      .then((r) => r.data),
}

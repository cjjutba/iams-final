import api from './api'
import type {
  CctvEnrollCommitRequest,
  CctvEnrollCommitResult,
  CctvEnrollPreviewRequest,
  CctvEnrollPreviewResult,
  CctvEnrollmentStatus,
  CctvIdentifyRequest,
  CctvIdentifyResult,
} from '@/types'

/**
 * Admin-only API surface for the bulk CCTV enrollment workflow.
 *
 * Three endpoints:
 *
 *   - ``status()``  — list every student's CCTV posture broken down by
 *     room. Drives the queue + filter on the bulk-enroll page.
 *   - ``preview()`` — single-frame, NON-COMMITTING capture so the
 *     operator can confirm the right student is in front of the camera
 *     before pulling the trigger on a real enrollment.
 *   - ``commit()``  — the existing 5-capture enrollment that writes to
 *     FAISS + face_embeddings. Wraps ``POST /api/v1/face/cctv-enroll/{user_id}``
 *     so the page never has to construct that URL.
 */
export const cctvEnrollmentService = {
  status: () =>
    api
      .get<CctvEnrollmentStatus>('/face/cctv-enrollment-status')
      .then((r) => r.data),

  preview: (userId: string, body: CctvEnrollPreviewRequest) =>
    api
      .post<CctvEnrollPreviewResult>(
        `/face/cctv-enroll/${userId}/preview`,
        body,
      )
      .then((r) => r.data),

  commit: (userId: string, body: CctvEnrollCommitRequest) =>
    api
      .post<CctvEnrollCommitResult>(`/face/cctv-enroll/${userId}`, body)
      .then((r) => r.data),

  identify: (body: CctvIdentifyRequest) =>
    api
      .post<CctvIdentifyResult>('/face/cctv-identify', body)
      .then((r) => r.data),
}

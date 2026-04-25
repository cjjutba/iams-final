/**
 * Admin face-comparison sheet types.
 *
 * Matches backend/app/schemas/face.py FaceRegistrationDetailResponse +
 * FaceAngleMetadataResponse. `image_url` is null in Phase 1 and populated
 * in Phase 2 for angles whose `image_storage_key` is set.
 */

import type { RecognitionEventMessage } from '@/hooks/use-attendance-ws'

export interface FaceAngleMetadata {
  id: string
  angle_label: string | null
  quality_score: number | null
  created_at: string
  image_url: string | null
}

export interface FaceRegistrationDetail {
  user_id: string
  available: boolean
  registered_at: string | null
  embedding_dim: number
  angles: FaceAngleMetadata[]
}

/** Discriminated union consumed by `RegisteredFaceGallery`. */
export type RegistrationData =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'not-registered' }
  | { status: 'error'; message: string }
  | {
      status: 'ok'
      registeredAt: string | null
      embeddingDim: number
      angles: FaceAngleMetadata[]
    }

/** Discriminated union consumed by `LiveCropPanel` via `useLiveCrop`. */
export type LiveCropSource =
  | {
      kind: 'client'
      videoElement: HTMLVideoElement | null
      bbox: [number, number, number, number] | null
      trackId: number | null
      isStale: boolean
      isSubStream: boolean
    }
  | {
      kind: 'server'
      scheduleId: string
      userId: string | null
      // WS recognition-event stream (newest-first). The server hook
      // surfaces the most recent event matching (schedule, user) and uses
      // its `crop_urls.live` URL — every FAISS decision the ML pipeline
      // emits is a fresh crop, so the panel ticks forward in real time
      // instead of getting stuck on the first captured frame.
      recognitionEvents: RecognitionEventMessage[]
    }

/** Uniform shape returned by the facade `useLiveCrop(source)` hook. */
export interface LiveCropResult {
  status: 'idle' | 'loading' | 'ok' | 'stale' | 'error' | 'not-implemented'
  dataUrl: string | null
  capturedAt: number | null
  resolutionHint?: { sourceWidth: number; sourceHeight: number; isSubStream: boolean }
  errorMessage?: string
}

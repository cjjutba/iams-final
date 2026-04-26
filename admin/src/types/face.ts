export interface FaceRegistration {
  id: string
  user_id: string
  embedding_id: string
  registered_at: string
  is_active: boolean
}

export interface FaceStatistics {
  total_registered: number
  total_active: number
  total_inactive: number
}

// ===== CCTV Bulk Enrollment =====

export interface CctvEnrollmentStudent {
  user_id: string
  student_id: string | null
  full_name: string
  cctv_count: number
  phone_only: boolean
  /** Map of room.stream_key -> count of CCTV embeddings labelled for that room. */
  per_room: Record<string, number>
  /** Pre-Phase-2 ``cctv_<idx>`` rows with no room context. */
  cctv_legacy: number
}

export interface CctvEnrollmentRoomOption {
  id: string
  name: string
  stream_key: string
  has_camera: boolean
}

export interface CctvEnrollmentStatus {
  students: CctvEnrollmentStudent[]
  /** Legacy flat list of stream_keys. Kept for the live-feed banner. */
  rooms: string[]
  room_options: CctvEnrollmentRoomOption[]
  threshold: number
  phone_only_threshold: number
  phone_only_count: number
  total_registered: number
}

export interface CctvEnrollPreviewRequest {
  room: string
  min_face_size_px?: number
  min_det_score?: number
}

export interface CctvEnrollPreviewFace {
  /** JPEG base64-encoded, no data URI prefix. */
  crop_b64: string
  det_score: number
  /** [x, y, w, h] in source frame coords. */
  bbox: number[]
  self_similarity_to_phone: number
  is_best_match: boolean
  /** Cross-identification: which enrolled student this face most resembles. */
  best_match_user_id: string | null
  best_match_full_name: string | null
  best_match_student_id: string | null
  best_match_sim: number | null
}

export interface CctvEnrollPreviewResult {
  ok: boolean
  message: string
  face_count: number
  faces: CctvEnrollPreviewFace[]
  /** Highest sim across all detected faces. */
  best_self_similarity_to_phone: number | null
  /** [width, height] of the source frame. */
  frame_size: number[] | null
}

export interface CctvEnrollCommitRequest {
  room_code_or_id: string
  num_captures?: number
  capture_interval_s?: number
  min_face_size_px?: number
  min_det_score?: number
}

export interface CctvEnrollCapture {
  faiss_id: number
  label: string
  det_score: number
  bbox: number[]
}

export interface CctvIdentifyRequest {
  room: string
  min_face_size_px?: number
  min_det_score?: number
  min_identify_sim?: number
}

export interface CctvIdentifiedFace {
  /** JPEG base64-encoded, no data URI prefix. */
  crop_b64: string
  det_score: number
  bbox: number[]
  /** Cross-identification — null when no enrolled student matched confidently. */
  identified_user_id: string | null
  identified_full_name: string | null
  identified_student_id: string | null
  identified_sim: number | null
  /** Per-room CCTV capture counts for the identified student. */
  per_room: Record<string, number>
  already_enrolled_in_room: boolean
}

export interface CctvIdentifyResult {
  ok: boolean
  message: string
  face_count: number
  identified_count: number
  faces: CctvIdentifiedFace[]
  frame_size: number[] | null
}

export interface CctvEnrollCommitResult {
  success: boolean
  user_id: string
  added: number
  faiss_ids: number[]
  labels: string[]
  attempts: number
  skipped_reasons: Record<string, number>
  self_similarity_to_phone_mean: number
  self_similarity_to_phone_min: number
  self_similarity_to_phone_max: number
  per_capture: CctvEnrollCapture[]
}

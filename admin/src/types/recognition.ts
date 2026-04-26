/**
 * Recognition-evidence types.
 *
 * Matches backend/app/schemas/recognition.py. Crop URLs are relative — the
 * admin portal resolves them via its Axios baseURL (same origin as the
 * REST API).
 */

export interface BBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface CropUrls {
  live: string
  registered: string | null
}

export interface RecognitionEvent {
  event_id: string
  schedule_id: string
  schedule_subject: string | null
  student_id: string | null
  student_name: string | null
  track_id: number
  camera_id: string
  frame_idx: number
  similarity: number
  threshold_used: number
  matched: boolean
  is_ambiguous: boolean
  det_score: number
  embedding_norm: number
  bbox: BBox
  model_name: string
  crop_urls: CropUrls
  created_at: string
}

export interface RecognitionListResponse {
  items: RecognitionEvent[]
  next_cursor: string | null
}

export interface RecognitionEventBrief {
  event_id: string
  similarity: number
  timestamp: string | null
}

export interface TimelineBucket {
  minute: string
  matches: number
  misses: number
}

export interface RecognitionSummary {
  student_id: string
  schedule_id: string | null
  match_count: number
  miss_count: number
  best_match: RecognitionEventBrief | null
  worst_accepted: RecognitionEventBrief | null
  first_match: RecognitionEventBrief | null
  last_match: RecognitionEventBrief | null
  histogram: number[]
  timeline: TimelineBucket[]
  threshold_at_session: number | null
}

export interface RecognitionListFilters {
  schedule_id?: string
  student_id?: string
  matched?: boolean
  since?: string
  until?: string
  cursor?: string
  limit?: number
}

export interface AccessAuditEntry {
  id: number
  viewer_user_id: string
  viewer_name: string | null
  event_id: string
  crop_kind: 'live' | 'registered'
  viewed_at: string
  ip: string | null
  user_agent: string | null
  student_id: string | null
  student_name: string | null
}

export interface AccessAuditListResponse {
  items: AccessAuditEntry[]
  total: number
}

export interface AccessAuditFilters {
  event_id?: string
  viewer_id?: string
  since?: string
  until?: string
  skip?: number
  limit?: number
}

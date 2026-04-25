/**
 * System Activity types.
 *
 * Matches backend/app/schemas/activity.py. The WebSocket message shape
 * for /api/v1/ws/events is a superset — it includes a "type" discriminator
 * so the hook can distinguish activity_event frames from pong/etc.
 */

export type ActivityCategory =
  | 'attendance'
  | 'session'
  | 'recognition'
  | 'system'
  | 'audit'

export type ActivitySeverity = 'info' | 'success' | 'warn' | 'error'

export type ActivityActorType = 'system' | 'user' | 'pipeline'

export interface ActivityEvent {
  event_id: string
  event_type: string
  category: ActivityCategory
  severity: ActivitySeverity
  actor_type: ActivityActorType

  actor_id: string | null
  actor_name: string | null

  subject_user_id: string | null
  subject_user_name: string | null
  /**
   * Human-facing student record number (e.g. "JR-2024-001234") for the
   * subject user, when they are a student. Distinct from
   * ``subject_user_id`` (UUID). Used by the sidebar drilldown so the URL
   * matches the route param the student-record-detail page accepts.
   */
  subject_user_student_id: string | null

  subject_schedule_id: string | null
  subject_schedule_subject: string | null

  subject_room_id: string | null
  camera_id: string | null

  ref_attendance_id: string | null
  ref_early_leave_id: string | null
  ref_recognition_event_id: string | null

  summary: string
  payload: Record<string, unknown> | null
  created_at: string
}

export interface ActivityListResponse {
  items: ActivityEvent[]
  next_cursor: string | null
}

export interface ActivityCategoryStats {
  attendance: number
  session: number
  recognition: number
  system: number
  audit: number
}

export interface ActivitySeverityStats {
  info: number
  success: number
  warn: number
  error: number
}

export interface ActivityStats {
  window_minutes: number
  window_start: string
  window_end: string
  total_events: number
  events_per_minute: number
  by_category: ActivityCategoryStats
  by_severity: ActivitySeverityStats
  active_session_count: number
}

/** Query params accepted by GET /api/v1/activity/events */
export interface ActivityListFilters {
  event_type?: string // CSV of event type strings
  category?: string // CSV of categories
  severity?: string // CSV of severities
  schedule_id?: string
  student_id?: string
  actor_id?: string
  since?: string // ISO datetime
  until?: string // ISO datetime
  cursor?: string
  limit?: number
}

/** WebSocket message envelope over /api/v1/ws/events */
export interface ActivityWsMessage extends ActivityEvent {
  type: 'activity_event'
  // Backend also stamps origin_pid + _activity for multi-worker dedup;
  // clients can ignore those fields.
  origin_pid?: number
  _activity?: boolean
}

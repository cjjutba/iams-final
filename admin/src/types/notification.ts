export type NotificationSeverity =
  | 'info'
  | 'success'
  | 'warn'
  | 'error'
  | 'critical'

export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  severity: NotificationSeverity
  read_at: string | null
  reference_id: string | null
  reference_type: string | null
  created_at: string
}

export interface NotificationPreference {
  early_leave_alerts: boolean
  low_attendance_warning: boolean
  email_enabled: boolean
  low_attendance_threshold: number
  // Phase 1 backend additions — kept optional so the admin keeps working
  // against backends that haven't redeployed yet.
  camera_alerts?: boolean
  ml_health_alerts?: boolean
  security_alerts?: boolean
  audit_alerts?: boolean
  schedule_conflict_alerts?: boolean
  face_alerts?: boolean
  daily_health_summary?: boolean
}

export type NotificationPreferenceUpdate = Partial<NotificationPreference>

// Phase 8: per-type and per-severity unread counts for the sidebar.
// Returned by GET /api/v1/notifications/stats. The keys are open-ended
// (the backend groups by whatever `type` strings exist in the DB), so
// we type them as Record<string, number> instead of an enum.
export interface NotificationStats {
  by_type: Record<string, number>
  by_severity: Record<string, number>
  total: number
}

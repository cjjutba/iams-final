export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  created_at: string
}

export interface BroadcastNotificationRequest {
  target: 'all' | 'students' | 'faculty' | 'admin'
  target_user_id?: string
  title: string
  message: string
}

export interface NotificationPreference {
  early_leave_alerts: boolean
  anomaly_alerts: boolean
  attendance_confirmation: boolean
  low_attendance_warning: boolean
  daily_digest: boolean
  weekly_digest: boolean
  email_enabled: boolean
  low_attendance_threshold: number
}

export type NotificationPreferenceUpdate = Partial<NotificationPreference>

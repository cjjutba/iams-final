export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  created_at: string
}

export interface NotificationPreference {
  early_leave_alerts: boolean
  low_attendance_warning: boolean
  email_enabled: boolean
  low_attendance_threshold: number
}

export type NotificationPreferenceUpdate = Partial<NotificationPreference>

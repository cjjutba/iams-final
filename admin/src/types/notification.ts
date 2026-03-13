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

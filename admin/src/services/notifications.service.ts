import api from './api'
import type { Notification, BroadcastNotificationRequest, NotificationPreference, NotificationPreferenceUpdate } from '@/types'

export const notificationsService = {
  list: () =>
    api.get<Notification[]>('/notifications/').then(r => r.data),
  markRead: (id: string) =>
    api.patch(`/notifications/${id}/read`).then(r => r.data),
  markAllRead: () =>
    api.post('/notifications/read-all').then(r => r.data),
  unreadCount: () =>
    api.get<{ count: number }>('/notifications/unread-count').then(r => r.data),
  broadcast: (data: BroadcastNotificationRequest) =>
    api.post('/notifications/broadcast', data).then(r => r.data),
  getPreferences: () =>
    api.get<NotificationPreference>('/notifications/preferences').then(r => r.data),
  updatePreferences: (data: NotificationPreferenceUpdate) =>
    api.put<NotificationPreference>('/notifications/preferences', data).then(r => r.data),
}

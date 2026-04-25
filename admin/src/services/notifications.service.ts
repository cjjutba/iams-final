import api from './api'
import type {
  Notification,
  NotificationPreference,
  NotificationPreferenceUpdate,
  NotificationStats,
} from '@/types'

export interface NotificationListOptions {
  unread_only?: boolean
  type?: string
  severity?: string
  skip?: number
  limit?: number
}

export interface UnreadCountResponse {
  unread_count: number
  unread_critical_count: number
}

function buildListParams(opts?: NotificationListOptions): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {}
  if (!opts) return params
  if (opts.unread_only !== undefined) params.unread_only = opts.unread_only
  if (opts.type) params.type = opts.type
  if (opts.severity) params.severity = opts.severity
  if (opts.skip !== undefined) params.skip = opts.skip
  if (opts.limit !== undefined) params.limit = opts.limit
  return params
}

export const notificationsService = {
  list: (opts?: NotificationListOptions) =>
    api
      .get<Notification[]>('/notifications/', { params: buildListParams(opts) })
      .then((r) => r.data),
  markRead: (id: string) =>
    api.patch(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () =>
    api.post('/notifications/read-all').then((r) => r.data),
  remove: (id: string) =>
    api.delete(`/notifications/${id}`).then((r) => r.data),
  removeAll: () =>
    api.delete('/notifications/').then((r) => r.data),
  unreadCount: () =>
    api
      .get<{ unread_count: number; unread_critical_count?: number }>(
        '/notifications/unread-count',
      )
      .then((r): UnreadCountResponse => ({
        unread_count: r.data.unread_count ?? 0,
        unread_critical_count: r.data.unread_critical_count ?? 0,
      })),
  stats: () =>
    api
      .get<NotificationStats>('/notifications/stats')
      .then((r): NotificationStats => ({
        by_type: r.data.by_type ?? {},
        by_severity: r.data.by_severity ?? {},
        total: r.data.total ?? 0,
      })),
  getPreferences: () =>
    api.get<NotificationPreference>('/notifications/preferences').then((r) => r.data),
  updatePreferences: (data: NotificationPreferenceUpdate) =>
    api.put<NotificationPreference>('/notifications/preferences', data).then((r) => r.data),
}

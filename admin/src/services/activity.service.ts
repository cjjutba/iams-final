import api from './api'
import type {
  ActivityEvent,
  ActivityListFilters,
  ActivityListResponse,
  ActivityStats,
} from '@/types'

export const activityService = {
  list: (filters: ActivityListFilters = {}) =>
    api
      .get<ActivityListResponse>('/activity/events', { params: filters })
      .then((r) => r.data),

  getById: (eventId: string) =>
    api.get<ActivityEvent>(`/activity/events/${eventId}`).then((r) => r.data),

  stats: (windowMinutes: number = 15) =>
    api
      .get<ActivityStats>('/activity/events/stats', {
        params: { window_minutes: windowMinutes },
      })
      .then((r) => r.data),

  /**
   * CSV download URL — browser hits it directly so Axios interceptors
   * don't apply. Returns an origin-absolute path.
   */
  exportCsvUrl: (filters: ActivityListFilters = {}) => {
    const qs = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qs.set(k, String(v))
    })
    const q = qs.toString()
    return `${api.defaults.baseURL ?? ''}/activity/events/export.csv${q ? `?${q}` : ''}`
  },

  /** NDJSON download URL — preserves full payloads for reproducibility. */
  exportJsonUrl: (filters: ActivityListFilters = {}) => {
    const qs = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qs.set(k, String(v))
    })
    const q = qs.toString()
    return `${api.defaults.baseURL ?? ''}/activity/events/export.json${q ? `?${q}` : ''}`
  },
}

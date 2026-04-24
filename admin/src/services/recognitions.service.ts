import api from './api'
import type {
  AccessAuditFilters,
  AccessAuditListResponse,
  RecognitionEvent,
  RecognitionListFilters,
  RecognitionListResponse,
  RecognitionSummary,
} from '@/types'

export const recognitionsService = {
  list: (filters: RecognitionListFilters = {}) =>
    api
      .get<RecognitionListResponse>('/recognitions', { params: filters })
      .then((r) => r.data),

  getById: (eventId: string) =>
    api.get<RecognitionEvent>(`/recognitions/${eventId}`).then((r) => r.data),

  summarize: (params: { student_id: string; schedule_id?: string; since?: string }) =>
    api
      .get<RecognitionSummary>('/recognitions/summary', { params })
      .then((r) => r.data),

  exportCsvUrl: (filters: RecognitionListFilters = {}) => {
    const qs = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qs.set(k, String(v))
    })
    const q = qs.toString()
    // The browser hits this URL directly so Axios interceptors don't apply —
    // return the origin-absolute path so a `<a href>` download works.
    return `${api.defaults.baseURL ?? ''}/recognitions/export.csv${q ? `?${q}` : ''}`
  },

  accessAudit: (filters: AccessAuditFilters = {}) =>
    api
      .get<AccessAuditListResponse>('/recognitions/access-audit', { params: filters })
      .then((r) => r.data),
}

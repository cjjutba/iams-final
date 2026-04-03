import api from './api'
import type { SystemMetrics, AttendanceAnomaly, AtRiskStudent } from '@/types'

export const analyticsService = {
  systemMetrics: () =>
    api.get<{ success: boolean; data: SystemMetrics }>('/analytics/system/metrics').then(r => r.data),
  classOverview: (scheduleId: string) =>
    api.get(`/analytics/class/${scheduleId}/overview`).then(r => r.data),
  heatmap: (scheduleId: string) =>
    api.get(`/analytics/class/${scheduleId}/heatmap`).then(r => r.data),
  ranking: (scheduleId: string) =>
    api.get(`/analytics/class/${scheduleId}/ranking`).then(r => r.data),
  atRisk: () =>
    api.get<AtRiskStudent[]>('/analytics/at-risk-students').then(r => r.data),
  anomalies: () =>
    api.get<AttendanceAnomaly[]>('/analytics/anomalies').then(r => r.data),
  resolveAnomaly: (id: string) =>
    api.patch(`/analytics/anomalies/${id}/resolve`).then(r => r.data),
  predictions: (scheduleId: string) =>
    api.get(`/analytics/predictions/${scheduleId}`).then(r => r.data),
  dailyTrend: (days = 30) =>
    api.get<DailyTrendItem[]>('/analytics/system/daily-trend', { params: { days } }).then(r => r.data),
  weekdayBreakdown: () =>
    api.get<WeekdayBreakdownItem[]>('/analytics/system/weekday-breakdown').then(r => r.data),
}

export interface DailyTrendItem {
  date: string
  present: number
  late: number
  absent: number
}

export interface WeekdayBreakdownItem {
  day: string
  rate: number
}

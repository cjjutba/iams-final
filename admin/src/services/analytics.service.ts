import api from './api'
import type { SystemMetrics, AtRiskStudent } from '@/types'

export const analyticsService = {
  systemMetrics: () =>
    api.get<{ success: boolean; data: SystemMetrics }>('/analytics/system/metrics').then(r => r.data),
  atRisk: () =>
    api.get<AtRiskStudent[]>('/analytics/at-risk-students').then(r => r.data),
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
  early_leave: number
}

export interface WeekdayBreakdownItem {
  day: string
  rate: number
}

import api from './api'
import type { AttendanceRecord, ScheduleAttendanceSummary, LiveAttendanceResponse, EarlyLeaveAlert } from '@/types'

export const attendanceService = {
  list: (params?: { schedule_id?: string; student_id?: string; start_date?: string; end_date?: string; status?: string; skip?: number; limit?: number }) =>
    api.get<AttendanceRecord[]>('/attendance', { params }).then(r => r.data),
  getById: (id: string) =>
    api.get<AttendanceRecord>(`/attendance/${id}`).then(r => r.data),
  getScheduleSummaries: (targetDate?: string) =>
    api.get<ScheduleAttendanceSummary[]>('/attendance/schedule-summaries', { params: { target_date: targetDate } }).then(r => r.data),
  getScheduleAttendance: (scheduleId: string, date?: string) =>
    api.get<AttendanceRecord[]>(`/attendance/schedule/${scheduleId}`, { params: { date } }).then(r => r.data),
  getScheduleSummary: (scheduleId: string, startDate?: string, endDate?: string) =>
    api.get(`/attendance/schedule/${scheduleId}/summary`, { params: { start_date: startDate, end_date: endDate } }).then(r => r.data),
  getLive: (scheduleId: string) =>
    api.get<LiveAttendanceResponse>(`/attendance/live/${scheduleId}`).then(r => r.data),
  getAlerts: (params?: { filter?: string; schedule_id?: string }) =>
    api.get<EarlyLeaveAlert[]>('/attendance/alerts', { params }).then(r => r.data),
  getEarlyLeaves: () =>
    api.get('/attendance/early-leaves').then(r => r.data),
  export: (params: { schedule_id?: string; start_date?: string; end_date?: string; status?: string; format?: 'csv' | 'json' }) =>
    api.get('/attendance/export', { params, responseType: params.format === 'csv' ? 'blob' : 'json' }).then(r => r.data),
  update: (id: string, data: { status?: string; remarks?: string }) =>
    api.patch<AttendanceRecord>(`/attendance/${id}`, data).then(r => r.data),
  getPresenceLogs: (attendanceId: string) =>
    api.get(`/attendance/${attendanceId}/logs`).then(r => r.data),
}

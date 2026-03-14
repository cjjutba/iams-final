import api from './api'
import type { ScheduleResponse, ScheduleCreate, ScheduleUpdate } from '@/types'

export const schedulesService = {
  list: (params?: { day?: number }) =>
    api.get<ScheduleResponse[]>('/schedules/', { params }).then(r => r.data),
  getById: (id: string) =>
    api.get<ScheduleResponse>(`/schedules/${id}`).then(r => r.data),
  getEnrolledStudents: (id: string) =>
    api.get(`/schedules/${id}/students`).then(r => r.data),
  create: (data: ScheduleCreate) =>
    api.post<ScheduleResponse>('/schedules/', data).then(r => r.data),
  update: (id: string, data: ScheduleUpdate) =>
    api.patch<ScheduleResponse>(`/schedules/${id}`, data).then(r => r.data),
  delete: (id: string) =>
    api.delete(`/schedules/${id}`).then(r => r.data),
}

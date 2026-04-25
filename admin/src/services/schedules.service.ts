import api from './api'
import type {
  ScheduleResponse,
  ScheduleCreate,
  ScheduleUpdate,
  StudentEnrollmentsPage,
} from '@/types'

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
  enrollStudent: (scheduleId: string, studentUserId: string) =>
    api.post(`/schedules/${scheduleId}/enroll/${studentUserId}`).then(r => r.data),
  unenrollStudent: (scheduleId: string, studentUserId: string) =>
    api.delete(`/schedules/${scheduleId}/enroll/${studentUserId}`).then(r => r.data),
  getStudentEnrollments: (
    studentUserId: string,
    params?: { limit?: number; offset?: number },
  ) =>
    api
      .get<StudentEnrollmentsPage>(`/schedules/student/${studentUserId}/enrollments`, {
        params: { limit: params?.limit ?? 20, offset: params?.offset ?? 0 },
      })
      .then(r => r.data),
  getStudentEnrollmentIds: (studentUserId: string) =>
    api
      .get<{ schedule_ids: string[] }>(`/schedules/student/${studentUserId}/enrollments/ids`)
      .then(r => r.data.schedule_ids),
}

import api from './api'
import type {
  AdminCreateUser,
  CreateStudentRecord,
  StudentRecordResponse,
  StudentRecordWithStatus,
  UpdateStudentRecord,
  UserResponse,
  UserUpdate,
  UserRole,
  UserStatistics,
} from '@/types'

export const usersService = {
  create: (data: AdminCreateUser) =>
    api.post<UserResponse>('/users/', data).then(r => r.data),
  createStudentRecord: (data: CreateStudentRecord) =>
    api.post<StudentRecordResponse>('/users/student-records', data).then(r => r.data),
  listStudentRecords: () =>
    api.get<StudentRecordWithStatus[]>('/users/student-records').then(r => r.data),
  getStudentRecord: (studentId: string) =>
    api.get<StudentRecordWithStatus>(`/users/student-records/${studentId}`).then(r => r.data),
  updateStudentRecord: (studentId: string, data: UpdateStudentRecord) =>
    api.patch<StudentRecordResponse>(`/users/student-records/${studentId}`, data).then(r => r.data),
  deactivateStudentRecord: (studentId: string) =>
    api.delete(`/users/student-records/${studentId}`).then(r => r.data),
  list: (params?: { skip?: number; limit?: number; role?: UserRole }) =>
    api.get<UserResponse[]>('/users/', { params }).then(r => r.data),
  getById: (id: string) =>
    api.get<UserResponse>(`/users/${id}`).then(r => r.data),
  update: (id: string, data: UserUpdate) =>
    api.patch<UserResponse>(`/users/${id}`, data).then(r => r.data),
  deactivate: (id: string) =>
    api.delete(`/users/${id}`).then(r => r.data),
  reactivate: (id: string) =>
    api.post(`/users/${id}/reactivate`).then(r => r.data),
  statistics: () =>
    api.get<{ success: boolean; data: UserStatistics }>('/users/statistics').then(r => r.data),
}

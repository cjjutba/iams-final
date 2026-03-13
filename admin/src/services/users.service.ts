import api from './api'
import type { UserResponse, UserUpdate, UserRole, UserStatistics } from '@/types'

export const usersService = {
  list: (params?: { skip?: number; limit?: number; role?: UserRole }) =>
    api.get<UserResponse[]>('/users', { params }).then(r => r.data),
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

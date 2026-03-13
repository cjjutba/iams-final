import api from './api'
import type { LoginRequest, LoginResponse } from '@/types'

export const authService = {
  login: (data: LoginRequest) =>
    api.post<LoginResponse>('/auth/login', data).then(r => r.data),
  me: () =>
    api.get('/auth/me').then(r => r.data),
  logout: () =>
    api.post('/auth/logout').then(r => r.data),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data).then(r => r.data),
}

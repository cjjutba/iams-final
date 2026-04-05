import type { UserResponse } from './user'

export interface LoginRequest {
  identifier: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserResponse
}

export interface AuthUser {
  id: string
  email: string
  first_name: string
  last_name: string
  role: 'student' | 'faculty' | 'admin'
}

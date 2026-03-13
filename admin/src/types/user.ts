export type UserRole = 'student' | 'faculty' | 'admin'

export interface UserResponse {
  id: string
  email: string
  first_name: string
  last_name: string
  phone: string | null
  role: UserRole
  student_id: string | null
  is_active: boolean
  email_verified: boolean
  created_at: string
}

export interface UserCreate {
  email: string
  first_name: string
  last_name: string
  phone?: string
  password: string
  role: UserRole
  student_id?: string
}

export interface UserUpdate {
  email?: string
  first_name?: string
  last_name?: string
  phone?: string
}

export interface UserStatistics {
  total_users: number
  total_students: number
  total_faculty: number
  total_admins: number
  active_users: number
  inactive_users: number
}

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

export interface AdminCreateUser {
  email: string
  first_name: string
  last_name: string
  phone?: string
  password: string
  role: 'faculty' | 'admin'
}

export interface CreateStudentRecord {
  student_id: string
  first_name: string
  middle_name?: string
  last_name: string
  email?: string
  course?: string
  year_level?: number
  section?: string
  birthdate?: string
  contact_number?: string
}

export interface StudentRecordResponse {
  student_id: string
  first_name: string
  middle_name: string | null
  last_name: string
  email: string | null
  course: string | null
  year_level: number | null
  section: string | null
  birthdate: string | null
  contact_number: string | null
  is_active: boolean
  created_at: string
}

export interface StudentRecordWithStatus extends StudentRecordResponse {
  user_id: string | null
  is_registered: boolean
  has_face_registered: boolean
}

export interface UpdateStudentRecord {
  first_name?: string
  middle_name?: string
  last_name?: string
  email?: string
  course?: string
  year_level?: number
  section?: string
  birthdate?: string
  contact_number?: string
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

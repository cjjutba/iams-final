import type { UserResponse } from './user'

export interface RoomInfo {
  id: string
  name: string
  building: string | null
  capacity: number | null
}

export interface ScheduleResponse {
  id: string
  subject_code: string
  subject_name: string
  day_of_week: number
  start_time: string
  end_time: string
  semester: string
  academic_year: string
  target_course: string | null
  target_year_level: number | null
  faculty_id: string
  room_id: string
  is_active: boolean
  faculty: UserResponse | null
  room: RoomInfo | null
}

export interface ScheduleCreate {
  subject_code: string
  subject_name: string
  day_of_week: number
  start_time: string
  end_time: string
  semester: string
  academic_year: string
  target_course?: string
  target_year_level?: number
  faculty_id: string
  room_id: string
}

export interface ScheduleUpdate {
  subject_code?: string
  subject_name?: string
  day_of_week?: number
  start_time?: string
  end_time?: string
  semester?: string
  academic_year?: string
  target_course?: string
  target_year_level?: number
  faculty_id?: string
  room_id?: string
  is_active?: boolean
}

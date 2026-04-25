import type { UserResponse } from './user'

export interface RoomInfo {
  id: string
  name: string
  building: string | null
  capacity: number | null
}

/**
 * One row of the schedule's session history. Returned by
 * `GET /api/v1/schedules/{id}/sessions` — one row per unique date that
 * has attendance_records for the schedule, newest first.
 */
export interface ScheduleSessionSummary {
  date: string // ISO date (YYYY-MM-DD)
  start_time: string // HH:mm:ss
  end_time: string // HH:mm:ss
  present: number
  late: number
  absent: number
  early_leave: number
  excused: number
  /** (present + late) / total_records as a percentage, null when total_records is 0. */
  attendance_rate: number | null
  total_records: number
}

/**
 * Per-student row inside `ScheduleWithStudents.enrolled_students`.
 * `has_face_registered` is computed server-side via JOIN against
 * face_registrations and reflects whether the student has an active
 * registration (admins can toggle via the user detail page).
 */
export interface EnrolledStudentInfo {
  id: string
  student_id: string | null
  first_name: string
  last_name: string
  email: string
  is_active?: boolean
  has_face_registered: boolean
}

// Backend-derived presentation status — distinct from `is_active` (which
// is the enable/archive flag). Computed per-row in the schedules router
// from session_manager + the current clock so the schedules list can
// show "Live now / Upcoming / Ended / Scheduled / Disabled" instead of
// always reading "Active".
export type ScheduleRuntimeStatus =
  | 'live'
  | 'upcoming'
  | 'ended'
  | 'scheduled'
  | 'disabled'

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
  runtime_status: ScheduleRuntimeStatus
  faculty: UserResponse | null
  room: RoomInfo | null
  faculty_name?: string | null
  room_name?: string | null
}

export interface StudentEnrollment {
  enrollment_id: string
  schedule_id: string
  enrolled_at: string | null
  schedule: ScheduleResponse | null
}

export interface StudentEnrollmentsPage {
  items: StudentEnrollment[]
  total: number
  limit: number
  offset: number
  has_more: boolean
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

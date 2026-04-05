export type AttendanceStatus = 'present' | 'late' | 'absent' | 'excused' | 'early_leave'

/** Format a status value for display: "early_leave" → "Early Leave" */
export function formatStatus(status: string): string {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export interface AttendanceRecord {
  id: string
  student_id: string
  schedule_id: string
  date: string
  status: AttendanceStatus
  check_in_time: string | null
  check_out_time: string | null
  presence_score: number
  total_scans: number
  scans_present: number
  remarks: string | null
  student_name: string | null
  subject_code: string | null
}

export interface ScheduleAttendanceSummary {
  schedule_id: string
  subject_code: string
  subject_name: string
  start_time: string
  end_time: string
  room_name: string | null
  session_active: boolean
  total_enrolled: number
  present_count: number
  late_count: number
  absent_count: number
  attendance_rate: number
}

export interface LiveAttendanceResponse {
  schedule_id: string
  subject_code: string
  subject_name: string
  date: string
  start_time: string
  end_time: string
  session_active: boolean
  total_enrolled: number
  present_count: number
  late_count: number
  absent_count: number
  early_leave_count: number
  students: StudentAttendanceStatus[]
}

export interface StudentAttendanceStatus {
  student_id: string
  student_name: string
  status: AttendanceStatus
  check_in_time: string | null
  presence_score: number
}

export interface EarlyLeaveAlert {
  id: string
  attendance_id: string
  student_id: string
  student_name: string
  student_student_id: string | null
  schedule_id: string
  subject_code: string
  subject_name: string
  detected_at: string
  last_seen_at: string
  consecutive_misses: number
  notified: boolean
  date: string
}

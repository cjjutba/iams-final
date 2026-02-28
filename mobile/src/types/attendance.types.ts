/**
 * Attendance Types
 *
 * Type definitions for attendance records, presence tracking, and early leave events.
 */

// Attendance status enum
export enum AttendanceStatus {
  PRESENT = 'present',
  LATE = 'late',
  ABSENT = 'absent',
  EARLY_LEAVE = 'early_leave',
}

// Attendance record (from GET /attendance/me or /attendance/today)
export interface AttendanceRecord {
  id: string;
  student_id: string;
  schedule_id: string;
  date: string; // ISO date string
  status: AttendanceStatus;
  check_in_time?: string; // HH:MM:SS format
  check_out_time?: string;
  presence_score?: number; // Percentage (0-100)
  total_scans?: number;
  scans_present?: number;
  remarks?: string;
  created_at: string;
  updated_at?: string;
}

// Attendance record with student info (for faculty views)
export interface AttendanceRecordWithStudent extends AttendanceRecord {
  student: {
    id: string;
    student_id: string;
    first_name: string;
    last_name: string;
    email: string;
  };
}

// Presence log (individual scan result)
export interface PresenceLog {
  id: string;
  attendance_id: string;
  scan_number: number;
  scan_time: string; // ISO datetime
  detected: boolean;
  confidence?: number; // 0-1
  created_at: string;
}

// Early leave event
export interface EarlyLeaveEvent {
  id: string;
  attendance_id: string;
  student_id: string;
  student_name?: string;
  schedule_id: string;
  detected_at: string; // ISO datetime
  last_seen_at?: string;
  consecutive_misses: number;
  notified: boolean;
  created_at: string;
}

// Attendance summary (from GET /attendance/me/summary)
export interface AttendanceSummary {
  total: number;
  present: number;
  late: number;
  absent: number;
  early_leave: number;
  attendance_rate: number; // Percentage (0-100)
  start_date: string;
  end_date: string;
}

// Live attendance student status (for faculty live view)
export interface StudentAttendanceStatus {
  student_id: string;
  student_name: string;
  status: AttendanceStatus;
  check_in_time?: string;
  presence_score?: number;
  total_scans?: number;
  scans_present?: number;
  last_seen_at?: string;
  consecutive_misses?: number;
  currently_detected?: boolean; // Green dot indicator
}

// Live attendance response (GET /attendance/live/{schedule_id})
export interface LiveAttendanceResponse {
  schedule_id: string;
  subject_code: string;
  subject_name: string;
  date: string;
  start_time: string;
  end_time: string;
  session_active: boolean;
  total_enrolled: number;
  present_count: number;
  late_count: number;
  absent_count: number;
  early_leave_count: number;
  students: StudentAttendanceStatus[];
}

// Manual attendance entry request (POST /attendance/manual)
export interface ManualAttendanceRequest {
  student_id: string;
  schedule_id: string;
  date: string; // ISO date
  status: AttendanceStatus;
  remarks?: string;
}

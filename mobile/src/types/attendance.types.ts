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

// Per-schedule attendance summary (GET /attendance/schedule-summaries)
export interface ScheduleAttendanceSummary {
  schedule_id: string;
  subject_code: string;
  subject_name: string;
  start_time: string; // HH:MM:SS
  end_time: string;   // HH:MM:SS
  room_name?: string;
  session_active: boolean;
  total_enrolled: number;
  present_count: number;
  late_count: number;
  absent_count: number;
  attendance_rate: number; // 0-100
}

// ---------------------------------------------------------------------------
// Analytics Types
// ---------------------------------------------------------------------------

// Class overview analytics (from GET /analytics/class/{scheduleId})
export interface ClassOverview {
  schedule_id: string;
  subject_code: string;
  subject_name: string;
  total_sessions: number;
  average_attendance_rate: number; // Percentage (0-100)
  total_enrolled: number;
  early_leave_count: number;
  anomaly_count: number;
}

// Student ranking within a class (from GET /analytics/class/{scheduleId}/ranking)
export interface StudentRanking {
  student_id: string;
  student_name: string;
  student_number: string | null;
  attendance_rate: number; // Percentage (0-100)
  sessions_attended: number;
  sessions_total: number;
  engagement_score: number | null; // Optional engagement metric
}

// At-risk student alert (from GET /analytics/at-risk)
export interface AtRiskStudent {
  student_id: string;
  student_name: string;
  student_number: string | null;
  schedule_id: string;
  subject_code: string;
  subject_name: string;
  attendance_rate: number; // Percentage (0-100)
  sessions_missed: number;
  sessions_total: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  last_attended: string | null; // ISO date or null if never attended
}

// Heatmap entry for daily attendance visualization
export interface HeatmapEntry {
  date: string; // ISO date (YYYY-MM-DD)
  attendance_rate: number; // Percentage (0-100)
  present_count: number;
  total_enrolled: number;
}

// Student analytics dashboard (from GET /analytics/me/dashboard)
export interface StudentAnalyticsDashboard {
  overall_attendance_rate: number; // Percentage (0-100)
  total_classes_attended: number;
  total_classes: number;
  current_streak: number; // Consecutive present days
  longest_streak: number;
  early_leave_count: number;
  trend: 'improving' | 'stable' | 'declining';
  rank_in_class: number | null;
  total_students: number | null;
}

// Per-subject attendance breakdown (from GET /analytics/me/subjects)
export interface SubjectBreakdown {
  schedule_id: string;
  subject_code: string;
  subject_name: string;
  attendance_rate: number; // Percentage (0-100)
  sessions_attended: number;
  sessions_total: number;
  status: AttendanceStatus | 'good' | 'warning' | 'critical';
  last_attended: string | null; // ISO date
}

// Anomaly detection item (from GET /analytics/anomalies)
export interface AnomalyItem {
  id: string;
  type: 'proxy_attendance' | 'unusual_pattern' | 'bulk_absence' | 'time_anomaly';
  severity: 'low' | 'medium' | 'high';
  description: string;
  student_id: string | null;
  student_name: string | null;
  schedule_id: string | null;
  subject_name: string | null;
  detected_at: string; // ISO datetime
  resolved: boolean;
  resolved_at: string | null;
}

// System-wide metrics (from GET /analytics/system/metrics, admin only)
export interface SystemMetrics {
  total_students: number;
  total_faculty: number;
  total_schedules: number;
  total_sessions_today: number;
  overall_attendance_rate: number; // Percentage (0-100)
  at_risk_count: number;
  anomaly_count: number;
  active_sessions: number;
}

// Attendance prediction (from GET /analytics/predictions/{scheduleId})
export interface AttendancePrediction {
  date: string; // ISO date (YYYY-MM-DD)
  predicted_attendance_rate: number; // Percentage (0-100)
  predicted_present: number;
  total_enrolled: number;
  confidence: number; // 0-1 confidence score
}

export interface SystemMetrics {
  total_students: number
  total_faculty: number
  total_schedules: number
  total_attendance_records: number
  average_attendance_rate: number
  total_anomalies: number
  unresolved_anomalies: number
  total_early_leaves: number
}

export interface AttendanceAnomaly {
  id: string
  student_id: string
  anomaly_type: 'FREQUENT_ABSENTEE' | 'CHRONIC_ABSENTEE' | 'PATTERN_CHANGE'
  severity: string
  description: string
  resolved: boolean
  detected_at: string
  resolved_by: string | null
  resolved_at: string | null
}

export interface AtRiskStudent {
  student_id: string
  student_name: string
  attendance_rate: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  missed_classes: number
}

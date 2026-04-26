export interface SystemMetrics {
  total_students: number
  total_faculty: number
  total_schedules: number
  total_attendance_records: number
  average_attendance_rate: number
  total_early_leaves: number
}

export interface AtRiskStudent {
  student_id: string
  student_name: string
  attendance_rate: number
  risk_level: string
  missed_classes: number
}

package com.iams.app.data.model

import com.google.gson.annotations.SerializedName

// === Auth ===
data class LoginRequest(val identifier: String, val password: String)
data class CheckStudentIdRequest(
    @SerializedName("student_id") val studentId: String
)
data class CheckStudentIdResponse(
    val exists: Boolean,
    val available: Boolean,
    val message: String
)
data class VerifyStudentIdRequest(
    @SerializedName("student_id") val studentId: String,
    val birthdate: String
)
data class VerifyStudentIdResponse(
    val valid: Boolean,
    @SerializedName("student_info") val studentInfo: Map<String, Any>?,
    val message: String
)
data class RegisterRequest(
    val email: String,
    val password: String,
    @SerializedName("first_name") val firstName: String,
    @SerializedName("last_name") val lastName: String,
    @SerializedName("student_id") val studentId: String,
    val birthdate: String
)
data class RegisterResponse(val message: String, val user: UserResponse?, val tokens: RegistrationTokens?)
data class RegistrationTokens(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String?,
    @SerializedName("token_type") val tokenType: String,
)
data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String,
    val user: UserResponse
)
data class RefreshRequest(@SerializedName("refresh_token") val refreshToken: String)
data class ChangePasswordRequest(
    @SerializedName("old_password") val oldPassword: String,
    @SerializedName("new_password") val newPassword: String
)
data class MessageResponse(val message: String)
data class ForgotPasswordRequest(val email: String)

// === User ===
data class UserResponse(
    val id: String,
    val email: String,
    @SerializedName("first_name") val firstName: String,
    @SerializedName("last_name") val lastName: String,
    val role: String,
    @SerializedName("student_id") val studentId: String?,
    @SerializedName("face_registered") val faceRegistered: Boolean?
)

// === Face ===
data class FaceRegisterResponse(
    val message: String,
    @SerializedName("images_processed") val imagesProcessed: Int
)
data class FaceStatusResponse(
    @SerializedName("registered") val faceRegistered: Boolean
)

// === Schedule ===
data class ScheduleResponse(
    val id: String,
    @SerializedName("subject_name") val subjectName: String,
    @SerializedName("subject_code") val subjectCode: String?,
    @SerializedName("day_of_week") val dayOfWeek: Any, // Can be Int or String from backend
    @SerializedName("start_time") val startTime: String,
    @SerializedName("end_time") val endTime: String,
    @SerializedName("room_name") val roomName: String?,
    @SerializedName("room_id") val roomId: String?,
    @SerializedName("faculty_name") val facultyName: String?,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("early_leave_timeout_minutes") val earlyLeaveTimeoutMinutes: Int? = null,
) {
    /** Normalise day_of_week to Int (0=Monday) regardless of backend format. */
    val dayOfWeekInt: Int get() = when (dayOfWeek) {
        is Number -> (dayOfWeek as Number).toInt()
        is String -> {
            val s = (dayOfWeek as String).lowercase()
            when {
                s == "monday" || s == "0" -> 0
                s == "tuesday" || s == "1" -> 1
                s == "wednesday" || s == "2" -> 2
                s == "thursday" || s == "3" -> 3
                s == "friday" || s == "4" -> 4
                s == "saturday" || s == "5" -> 5
                s == "sunday" || s == "6" -> 6
                else -> s.toIntOrNull() ?: 0
            }
        }
        else -> 0
    }
}

data class ScheduleConfigUpdateRequest(
    @SerializedName("early_leave_timeout_minutes") val earlyLeaveTimeoutMinutes: Int
)

// === Attendance ===
data class AttendanceRecordResponse(
    val id: String,
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("student_id") val studentId: String?,
    @SerializedName("student_name") val studentName: String?,
    @SerializedName("subject_code") val subjectCode: String? = null,
    val status: String,
    val date: String,
    @SerializedName("check_in_time") val checkInTime: String?,
    @SerializedName("presence_score") val presenceScore: Float?,
    @SerializedName("total_scans") val totalScans: Int? = null,
    @SerializedName("scans_present") val scansPresent: Int? = null,
    val remarks: String? = null,
)

data class PresenceLogResponse(
    val id: String,
    @SerializedName("scan_number") val scanNumber: Int,
    @SerializedName("scan_time") val scanTime: String,
    val detected: Boolean,
    val confidence: Float? = null,
)
data class AttendanceSummaryResponse(
    @SerializedName("total_classes") val totalClasses: Int,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("absent_count") val absentCount: Int,
    @SerializedName("late_count") val lateCount: Int,
    @SerializedName("attendance_rate") val attendanceRate: Float
)
data class LiveAttendanceResponse(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("subject_code") val subjectCode: String? = null,
    @SerializedName("subject_name") val subjectName: String? = null,
    val date: String? = null,
    @SerializedName("start_time") val startTime: String? = null,
    @SerializedName("end_time") val endTime: String? = null,
    @SerializedName("session_active") val sessionActive: Boolean = false,
    @SerializedName("total_enrolled") val totalEnrolled: Int = 0,
    @SerializedName("present_count") val presentCount: Int = 0,
    @SerializedName("late_count") val lateCount: Int = 0,
    @SerializedName("absent_count") val absentCount: Int = 0,
    @SerializedName("early_leave_count") val earlyLeaveCount: Int = 0,
    val students: List<StudentAttendanceStatus> = emptyList(),
    // Legacy fields (backwards compat)
    val present: List<StudentAttendanceStatus>? = null,
    val absent: List<StudentAttendanceStatus>? = null,
    val late: List<StudentAttendanceStatus>? = null,
    @SerializedName("early_leave") val earlyLeave: List<StudentAttendanceStatus>? = null,
)
data class StudentAttendanceStatus(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("student_number") val studentNumber: String? = null,
    @SerializedName("student_name") val studentName: String,
    val status: String,
    @SerializedName("check_in_time") val checkInTime: String? = null,
    @SerializedName("presence_score") val presenceScore: Float? = null,
)
data class AlertResponse(
    val id: String,
    @SerializedName("student_name") val studentName: String? = null,
    @SerializedName("student_id") val studentId: String? = null,
    @SerializedName("schedule_id") val scheduleId: String? = null,
    @SerializedName("attendance_id") val attendanceId: String? = null,
    val type: String? = null,
    val message: String? = null,
    @SerializedName("detected_at") val detectedAt: String? = null,
    @SerializedName("last_seen_at") val lastSeenAt: String? = null,
    @SerializedName("consecutive_misses") val consecutiveMisses: Int = 0,
    val notified: Boolean = false,
    val returned: Boolean = false,
    @SerializedName("returned_at") val returnedAt: String? = null,
    @SerializedName("absence_duration_seconds") val absenceDurationSeconds: Int? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)

// === Student Attendance Summary (for faculty student detail) ===
data class StudentAttendanceSummaryResponse(
    val total: Int = 0,
    val present: Int = 0,
    val late: Int = 0,
    val absent: Int = 0,
    @SerializedName("attendance_rate") val attendanceRate: Float = 0f,
)

// === Student Attendance History (for faculty student detail) ===
data class StudentAttendanceHistoryResponse(
    val data: List<AttendanceRecordResponse> = emptyList(),
)

// === Room ===
data class RoomResponse(
    val id: String,
    val name: String,
    @SerializedName("stream_key") val streamKey: String?,
    @SerializedName("camera_endpoint") val cameraEndpoint: String?
)

// === WebSocket Messages ===

/** Legacy scan_result message (backward compatibility) */
data class ScanResultMessage(
    val type: String,
    @SerializedName("schedule_id") val scheduleId: String,
    val detections: List<Detection>,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("total_enrolled") val totalEnrolled: Int,
    val absent: List<String>,
    @SerializedName("early_leave") val earlyLeave: List<String>
)
data class Detection(
    val bbox: List<Float>,  // [x1, y1, x2, y2] normalized 0-1
    val name: String?,      // null = unrecognized face
    val confidence: Float,
    @SerializedName("user_id") val userId: String?
)

/** Real-time track info from ByteTrack pipeline */
data class TrackInfo(
    @SerializedName("track_id") val trackId: Int,
    val bbox: List<Float>,  // [x1, y1, x2, y2] normalized 0-1
    val velocity: List<Float>? = null,  // [vx, vy, vw, vh] normalized units/second (center+size)
    val name: String?,
    val confidence: Float,
    @SerializedName("user_id") val userId: String?,
    val status: String  // "recognized" | "unknown" | "pending"
)

/** frame_update message (at ~15fps from backend pipeline) */
data class FrameUpdateMessage(
    val type: String,
    val timestamp: Double,
    @SerializedName("frame_size") val frameSize: List<Int>? = null,  // [width, height] from backend
    val tracks: List<TrackInfo>,
    val fps: Float,
    @SerializedName("processing_ms") val processingMs: Float
)

/** attendance_summary message (every 5-10s from backend pipeline) */
data class AttendanceSummaryMessage(
    val type: String,
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("on_time_count") val onTimeCount: Int = 0,
    @SerializedName("late_count") val lateCount: Int = 0,
    @SerializedName("absent_count") val absentCount: Int = 0,
    @SerializedName("early_leave_count") val earlyLeaveCount: Int = 0,
    @SerializedName("total_enrolled") val totalEnrolled: Int,
    val present: List<AttendanceSummaryStudent>?,
    val absent: List<AttendanceSummaryStudent>?,
    val late: List<AttendanceSummaryStudent>?,
    @SerializedName("early_leave") val earlyLeave: List<AttendanceSummaryStudent>?,
    @SerializedName("early_leave_returned") val earlyLeaveReturned: List<AttendanceSummaryStudent>?,
)

data class AttendanceSummaryStudent(
    @SerializedName("user_id") val userId: String,
    val name: String
)

// === Analytics ===
data class StudentAnalyticsDashboard(
    @SerializedName("overall_attendance_rate") val overallAttendanceRate: Float,
    @SerializedName("total_classes") val totalClasses: Int,
    @SerializedName("total_classes_attended") val totalClassesAttended: Int,
    @SerializedName("current_streak") val currentStreak: Int,
    @SerializedName("longest_streak") val longestStreak: Int,
    val trend: String,
    @SerializedName("rank_in_class") val rankInClass: Int?,
    @SerializedName("total_students") val totalStudents: Int?,
    @SerializedName("early_leave_count") val earlyLeaveCount: Int,
)

data class SubjectBreakdown(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("subject_name") val subjectName: String,
    @SerializedName("subject_code") val subjectCode: String?,
    @SerializedName("attendance_rate") val attendanceRate: Float,
    @SerializedName("sessions_attended") val sessionsAttended: Int,
    @SerializedName("sessions_total") val sessionsTotal: Int,
    @SerializedName("last_attended") val lastAttended: String?,
)

// === Notifications ===
data class NotificationResponse(
    val id: String,
    @SerializedName("user_id") val userId: String = "",
    val type: String,
    val title: String,
    val message: String,
    val read: Boolean,
    @SerializedName("read_at") val readAt: String? = null,
    @SerializedName("reference_id") val referenceId: String? = null,
    @SerializedName("reference_type") val referenceType: String? = null,
    @SerializedName("created_at") val createdAt: String = "",
)

data class UnreadCountResponse(
    @SerializedName("unread_count") val unreadCount: Int
)

// === Profile ===
data class UpdateProfileRequest(
    val email: String? = null,
    val phone: String? = null,
)

// === Sessions (Presence) ===
data class SessionStartRequest(
    @SerializedName("schedule_id") val scheduleId: String
)
data class SessionStartResponse(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("started_at") val startedAt: String,
    @SerializedName("student_count") val studentCount: Int,
    val message: String,
)
data class SessionEndResponse(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("total_scans") val totalScans: Int,
    @SerializedName("total_students") val totalStudents: Int,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("early_leave_count") val earlyLeaveCount: Int,
    val message: String,
)
data class ActiveSessionsResponse(
    @SerializedName("active_sessions") val activeSessions: List<String>,
    val count: Int,
)

// === Manual Entry ===
data class ManualEntryRequest(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("student_id") val studentId: String,
    val date: String,
    val status: String,
    val remarks: String? = null,
)

// === Live Attendance (extended) ===
data class LiveAttendanceFullResponse(
    @SerializedName("schedule_id") val scheduleId: String,
    val students: List<LiveStudentStatus>,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("absent_count") val absentCount: Int,
    @SerializedName("late_count") val lateCount: Int,
    @SerializedName("early_leave_count") val earlyLeaveCount: Int,
)

data class LiveStudentStatus(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("student_name") val studentName: String,
    @SerializedName("student_number") val studentNumber: String? = null,
    val status: String,
    @SerializedName("check_in_time") val checkInTime: String? = null,
    @SerializedName("currently_detected") val currentlyDetected: Boolean = false,
    @SerializedName("presence_score") val presenceScore: Float? = null,
)

// === Notification Preferences ===
data class NotificationPreferenceResponse(
    @SerializedName("attendance_confirmation") val attendanceConfirmation: Boolean = true,
    @SerializedName("early_leave_alerts") val earlyLeaveAlerts: Boolean = true,
    @SerializedName("anomaly_alerts") val anomalyAlerts: Boolean = true,
    @SerializedName("low_attendance_warning") val lowAttendanceWarning: Boolean = true,
    @SerializedName("daily_digest") val dailyDigest: Boolean = false,
    @SerializedName("weekly_digest") val weeklyDigest: Boolean = true,
    @SerializedName("email_enabled") val emailEnabled: Boolean = false,
)

data class NotificationPreferenceUpdateRequest(
    @SerializedName("attendance_confirmation") val attendanceConfirmation: Boolean? = null,
    @SerializedName("early_leave_alerts") val earlyLeaveAlerts: Boolean? = null,
    @SerializedName("anomaly_alerts") val anomalyAlerts: Boolean? = null,
    @SerializedName("low_attendance_warning") val lowAttendanceWarning: Boolean? = null,
    @SerializedName("daily_digest") val dailyDigest: Boolean? = null,
    @SerializedName("weekly_digest") val weeklyDigest: Boolean? = null,
    @SerializedName("email_enabled") val emailEnabled: Boolean? = null,
)

// === Real-time Notification Event (from WebSocket /ws/alerts/{user_id}) ===
data class NotificationEvent(
    val type: String,
    @SerializedName("toast_type") val toastType: String,
    @SerializedName("notification_type") val notificationType: String,
    val title: String,
    val message: String,
    @SerializedName("reference_id") val referenceId: String? = null,
    @SerializedName("reference_type") val referenceType: String? = null,
    val timestamp: String? = null,
)

// === Faculty Analytics ===
data class ClassOverview(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("subject_name") val subjectName: String,
    @SerializedName("subject_code") val subjectCode: String?,
    @SerializedName("day_of_week") val dayOfWeek: Int = 0,
    @SerializedName("start_time") val startTime: String? = null,
    @SerializedName("end_time") val endTime: String? = null,
    @SerializedName("average_attendance_rate") val averageAttendanceRate: Float,
    @SerializedName("total_sessions") val totalSessions: Int,
    @SerializedName("total_enrolled") val totalEnrolled: Int,
    @SerializedName("early_leave_count") val earlyLeaveCount: Int,
    @SerializedName("anomaly_count") val anomalyCount: Int,
) {
    val dayName: String get() = when (dayOfWeek) {
        0 -> "Monday"; 1 -> "Tuesday"; 2 -> "Wednesday"; 3 -> "Thursday"
        4 -> "Friday"; 5 -> "Saturday"; 6 -> "Sunday"; else -> ""
    }
}

data class AtRiskStudent(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("student_name") val studentName: String,
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("subject_name") val subjectName: String,
    @SerializedName("subject_code") val subjectCode: String?,
    @SerializedName("attendance_rate") val attendanceRate: Float,
    @SerializedName("risk_level") val riskLevel: String,
    @SerializedName("sessions_missed") val sessionsMissed: Int,
    @SerializedName("sessions_total") val sessionsTotal: Int,
)

data class AnomalyItem(
    val id: String,
    val description: String,
    val severity: String,
    @SerializedName("detected_at") val detectedAt: String,
    @SerializedName("subject_name") val subjectName: String? = null,
    val resolved: Boolean = false,
)

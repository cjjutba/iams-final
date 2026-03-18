package com.iams.app.data.model

import com.google.gson.annotations.SerializedName

// === Auth ===
data class LoginRequest(val identifier: String, val password: String)
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
data class RegisterResponse(val message: String, val user: UserResponse?)
data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String,
    val user: UserResponse
)
data class RefreshRequest(@SerializedName("refresh_token") val refreshToken: String)
data class CheckEmailRequest(val email: String)
data class EmailVerifiedResponse(val verified: Boolean, val message: String)
data class ChangePasswordRequest(
    @SerializedName("old_password") val oldPassword: String,
    @SerializedName("new_password") val newPassword: String
)
data class MessageResponse(val message: String)

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
    @SerializedName("face_registered") val faceRegistered: Boolean
)

// === Schedule ===
data class ScheduleResponse(
    val id: String,
    @SerializedName("subject_name") val subjectName: String,
    @SerializedName("subject_code") val subjectCode: String?,
    @SerializedName("day_of_week") val dayOfWeek: String,
    @SerializedName("start_time") val startTime: String,
    @SerializedName("end_time") val endTime: String,
    @SerializedName("room_name") val roomName: String?,
    @SerializedName("room_id") val roomId: String?,
    @SerializedName("faculty_name") val facultyName: String?,
)

// === Attendance ===
data class AttendanceRecordResponse(
    val id: String,
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("student_id") val studentId: String?,
    @SerializedName("student_name") val studentName: String?,
    val status: String,
    val date: String,
    @SerializedName("check_in_time") val checkInTime: String?,
    @SerializedName("presence_score") val presenceScore: Float?
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
    val present: List<StudentAttendanceStatus>,
    val absent: List<StudentAttendanceStatus>,
    val late: List<StudentAttendanceStatus>,
    @SerializedName("early_leave") val earlyLeave: List<StudentAttendanceStatus>
)
data class StudentAttendanceStatus(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("student_name") val studentName: String,
    val status: String,
    @SerializedName("check_in_time") val checkInTime: String?
)
data class AlertResponse(
    val id: String,
    @SerializedName("student_name") val studentName: String,
    @SerializedName("schedule_id") val scheduleId: String,
    val type: String,
    val message: String,
    @SerializedName("created_at") val createdAt: String
)

// === Room ===
data class RoomResponse(
    val id: String,
    val name: String,
    @SerializedName("stream_key") val streamKey: String?,
    @SerializedName("camera_endpoint") val cameraEndpoint: String?
)

// === WebSocket Messages ===
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
    val name: String,
    val confidence: Float,
    @SerializedName("user_id") val userId: String
)

package com.iams.app.data.api

import com.iams.app.data.model.*
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    // Auth
    @POST("auth/check-student-id")
    suspend fun checkStudentId(@Body request: CheckStudentIdRequest): Response<CheckStudentIdResponse>

    @POST("auth/verify-student-id")
    suspend fun verifyStudentId(@Body request: VerifyStudentIdRequest): Response<VerifyStudentIdResponse>

    @POST("auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<RegisterResponse>

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<TokenResponse>

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshRequest): Response<TokenResponse>

    @GET("auth/me")
    suspend fun getMe(): Response<UserResponse>

    @POST("auth/change-password")
    suspend fun changePassword(@Body request: ChangePasswordRequest): Response<MessageResponse>

    @POST("auth/forgot-password")
    suspend fun forgotPassword(@Body request: ForgotPasswordRequest): Response<MessageResponse>

    @POST("auth/logout")
    suspend fun logout(): Response<MessageResponse>

    // Face
    @Multipart
    @POST("face/register")
    suspend fun registerFace(@Part images: List<MultipartBody.Part>): Response<FaceRegisterResponse>

    @Multipart
    @POST("face/reregister")
    suspend fun reregisterFace(@Part images: List<MultipartBody.Part>): Response<FaceRegisterResponse>

    @GET("face/status")
    suspend fun getFaceStatus(): Response<FaceStatusResponse>

    // Schedules
    @GET("schedules")
    suspend fun getSchedules(): Response<List<ScheduleResponse>>

    @GET("schedules/me")
    suspend fun getMySchedules(): Response<List<ScheduleResponse>>

    @GET("schedules/{id}")
    suspend fun getSchedule(@Path("id") id: String): Response<ScheduleResponse>

    @PATCH("schedules/{id}/config")
    suspend fun updateScheduleConfig(
        @Path("id") scheduleId: String,
        @Body request: ScheduleConfigUpdateRequest,
    ): Response<ScheduleResponse>

    // Attendance
    @GET("attendance/me")
    suspend fun getMyAttendance(
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null,
    ): Response<List<AttendanceRecordResponse>>

    @GET("attendance/me/summary")
    suspend fun getMyAttendanceSummary(): Response<AttendanceSummaryResponse>

    @GET("attendance/today/{scheduleId}")
    suspend fun getTodayAttendance(@Path("scheduleId") scheduleId: String): Response<List<AttendanceRecordResponse>>

    @GET("attendance/live/{scheduleId}")
    suspend fun getLiveAttendance(@Path("scheduleId") scheduleId: String): Response<LiveAttendanceResponse>

    @GET("attendance/schedule/{scheduleId}/summary")
    suspend fun getScheduleAttendanceSummary(
        @Path("scheduleId") scheduleId: String,
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null,
    ): Response<AttendanceSummaryResponse>

    @GET("attendance/{id}")
    suspend fun getAttendanceDetail(@Path("id") id: String): Response<AttendanceRecordResponse>

    @GET("attendance/{id}/presence-logs")
    suspend fun getPresenceLogs(@Path("id") id: String): Response<List<PresenceLogResponse>>

    @GET("attendance")
    suspend fun getAttendanceRecords(
        @Query("schedule_id") scheduleId: String? = null,
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null,
        @Query("limit") limit: Int? = null,
    ): Response<List<AttendanceRecordResponse>>

    @Streaming
    @GET("attendance/export/pdf")
    suspend fun exportAttendancePdf(
        @Query("schedule_ids") scheduleIds: String,
        @Query("start_date") startDate: String,
        @Query("end_date") endDate: String,
    ): Response<ResponseBody>

    @GET("attendance/alerts")
    suspend fun getAlerts(
        @Query("filter") filter: String? = null,
    ): Response<List<AlertResponse>>

    // Student info (faculty viewing a student)
    @GET("auth/users/{userId}")
    suspend fun getUser(@Path("userId") userId: String): Response<UserResponse>

    // Student attendance summary (for a specific schedule)
    @GET("attendance/summary")
    suspend fun getStudentAttendanceSummary(
        @Query("student_id") studentId: String,
        @Query("schedule_id") scheduleId: String,
    ): Response<StudentAttendanceSummaryResponse>

    // Student attendance history (for a specific schedule)
    @GET("attendance/history")
    suspend fun getStudentAttendanceHistory(
        @Query("student_id") studentId: String,
        @Query("schedule_id") scheduleId: String,
        @Query("limit") limit: Int? = null,
    ): Response<List<AttendanceRecordResponse>>

    // Analytics
    @GET("analytics/student/dashboard")
    suspend fun getStudentAnalyticsDashboard(): Response<StudentAnalyticsDashboard>

    @GET("analytics/student/subjects")
    suspend fun getStudentSubjects(): Response<List<SubjectBreakdown>>

    // Notifications
    @GET("notifications")
    suspend fun getNotifications(): Response<List<NotificationResponse>>

    @PATCH("notifications/{id}/read")
    suspend fun markNotificationRead(@Path("id") id: String): Response<NotificationResponse>

    @GET("notifications/unread-count")
    suspend fun getUnreadCount(): Response<UnreadCountResponse>

    @POST("notifications/read-all")
    suspend fun markAllNotificationsRead(): Response<MessageResponse>

    @DELETE("notifications/{id}")
    suspend fun deleteNotification(@Path("id") id: String): Response<MessageResponse>

    @DELETE("notifications/")
    suspend fun deleteAllNotifications(): Response<MessageResponse>

    // Profile
    @PUT("auth/profile")
    suspend fun updateProfile(@Body request: UpdateProfileRequest): Response<UserResponse>

    // Manual Attendance Entry
    @POST("attendance/manual")
    suspend fun createManualEntry(@Body request: ManualEntryRequest): Response<AttendanceRecordResponse>

    // Live Attendance (full response with students list)
    @GET("attendance/live/{scheduleId}/full")
    suspend fun getLiveAttendanceFull(
        @Path("scheduleId") scheduleId: String
    ): Response<LiveAttendanceFullResponse>

    // Notification Preferences
    @GET("notifications/preferences")
    suspend fun getNotificationPreferences(): Response<NotificationPreferenceResponse>

    @PATCH("notifications/preferences")
    suspend fun updateNotificationPreferences(
        @Body request: NotificationPreferenceUpdateRequest
    ): Response<NotificationPreferenceResponse>

    // Faculty Analytics
    @GET("analytics/class/{scheduleId}/overview")
    suspend fun getClassOverview(
        @Path("scheduleId") scheduleId: String
    ): Response<ClassOverview>

    @GET("analytics/at-risk-students")
    suspend fun getAtRiskStudents(): Response<List<AtRiskStudent>>

    @GET("analytics/anomalies")
    suspend fun getAnomalies(): Response<List<AnomalyItem>>

    // Rooms
    @GET("rooms")
    suspend fun getRooms(): Response<List<RoomResponse>>

    // Sessions (Presence)
    @POST("presence/sessions/start")
    suspend fun startSession(@Body request: SessionStartRequest): Response<SessionStartResponse>

    @POST("presence/sessions/end")
    suspend fun endSession(@Query("schedule_id") scheduleId: String): Response<SessionEndResponse>

    @GET("presence/sessions/active")
    suspend fun getActiveSessions(): Response<ActiveSessionsResponse>
}

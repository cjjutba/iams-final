package com.iams.app.data.api

import com.iams.app.data.model.*
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    // Auth
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

    @POST("auth/check-email-verified")
    suspend fun checkEmailVerified(@Body request: CheckEmailRequest): Response<EmailVerifiedResponse>

    @POST("auth/change-password")
    suspend fun changePassword(@Body request: ChangePasswordRequest): Response<MessageResponse>

    @POST("auth/logout")
    suspend fun logout(): Response<MessageResponse>

    // Face
    @Multipart
    @POST("face/register")
    suspend fun registerFace(@Part images: List<MultipartBody.Part>): Response<FaceRegisterResponse>

    @GET("face/status")
    suspend fun getFaceStatus(): Response<FaceStatusResponse>

    // Schedules
    @GET("schedules")
    suspend fun getSchedules(): Response<List<ScheduleResponse>>

    @GET("schedules/{id}")
    suspend fun getSchedule(@Path("id") id: String): Response<ScheduleResponse>

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

    @GET("attendance/alerts")
    suspend fun getAlerts(): Response<List<AlertResponse>>

    // Rooms
    @GET("rooms")
    suspend fun getRooms(): Response<List<RoomResponse>>
}

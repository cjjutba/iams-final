package com.iams.app.ui.navigation

import android.net.Uri

object Routes {
    // Onboarding & Welcome
    const val SPLASH = "splash"
    const val ONBOARDING = "onboarding"
    const val WELCOME = "welcome"

    // Legacy alias — existing logout/post-registration flows reference Routes.LOGIN;
    // now they land on the Welcome screen where the user picks Student or Faculty login.
    const val LOGIN = WELCOME

    // Auth
    // Faculty login moved to the dedicated :app-faculty APK after the
    // 2026-04-22 two-app split. Student APK is student-only.
    const val STUDENT_LOGIN = "auth/student-login"
    const val FORGOT_PASSWORD = "auth/forgot-password"
    const val RESET_PASSWORD = "auth/reset-password"

    // Registration
    const val REGISTER_STEP1 = "register/step1"
    const val REGISTER_STEP2 = "register/step2/{studentId}/{firstName}/{lastName}/{email}"

    // Face registration flow (nested nav graph for shared ViewModel)
    const val REGISTER_FACE_FLOW = "register/face-flow"
    const val REGISTER_STEP3_INNER = "register/step3"
    const val REGISTER_REVIEW_INNER = "register/review"

    // Public aliases
    const val REGISTER_STEP3 = REGISTER_FACE_FLOW
    const val REGISTER_REVIEW = REGISTER_REVIEW_INNER

    // Student (primary tabs)
    const val STUDENT_HOME = "student/home"
    const val STUDENT_SCHEDULE = "student/schedule"
    const val STUDENT_HISTORY = "student/history"
    // Full pattern with optional query arg for deep-links from Analytics.
    const val STUDENT_HISTORY_PATTERN = "student/history?scheduleId={scheduleId}"
    const val STUDENT_PROFILE = "student/profile"

    // Student (secondary screens)
    const val STUDENT_ATTENDANCE_DETAIL = "student/attendance-detail/{attendanceId}/{scheduleId}/{date}"
    const val STUDENT_ANALYTICS = "student/analytics"
    const val STUDENT_EDIT_PROFILE = "student/edit-profile"
    const val STUDENT_FACE_REGISTER = "student/face-register/{mode}"

    // Faculty routes removed — the faculty app lives in :app-faculty
    // after the 2026-04-22 two-app split. See
    // android/app-faculty/src/main/java/com/iams/app/ui/navigation/FacultyNavHost.kt
    // for that app's route constants.

    // Common
    const val SETTINGS = "settings"

    // ── Helper functions ────────────────────────────────────────────────

    fun studentAttendanceDetail(attendanceId: String, scheduleId: String, date: String) =
        "student/attendance-detail/${Uri.encode(attendanceId)}/${Uri.encode(scheduleId)}/${Uri.encode(date)}"

    /** Navigate to Student History optionally pre-filtered to a specific schedule. */
    fun studentHistory(scheduleId: String? = null): String =
        if (scheduleId.isNullOrBlank()) "student/history"
        else "student/history?scheduleId=${Uri.encode(scheduleId)}"

    fun studentFaceRegister(mode: String) =
        "student/face-register/${Uri.encode(mode)}"

    fun registerStep2(studentId: String, firstName: String, lastName: String, email: String) =
        "register/step2/${Uri.encode(studentId)}/${Uri.encode(firstName)}/${Uri.encode(lastName)}/${Uri.encode(email.ifBlank { "_" })}"


}

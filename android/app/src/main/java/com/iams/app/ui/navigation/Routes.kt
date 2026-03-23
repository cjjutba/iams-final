package com.iams.app.ui.navigation

object Routes {
    // Onboarding & Welcome
    const val SPLASH = "splash"
    const val ONBOARDING = "onboarding"
    const val WELCOME = "welcome"

    // Legacy alias — existing logout/post-registration flows reference Routes.LOGIN;
    // now they land on the Welcome screen where the user picks Student or Faculty login.
    const val LOGIN = WELCOME

    // Auth
    const val STUDENT_LOGIN = "auth/student-login"
    const val FACULTY_LOGIN = "auth/faculty-login"
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
    const val STUDENT_PROFILE = "student/profile"

    // Student (secondary screens)
    const val STUDENT_ATTENDANCE_DETAIL = "student/attendance-detail/{attendanceId}/{scheduleId}/{date}"
    const val STUDENT_ANALYTICS = "student/analytics"
    const val STUDENT_EDIT_PROFILE = "student/edit-profile"
    const val STUDENT_NOTIFICATIONS = "student/notifications"
    const val STUDENT_FACE_REGISTER = "student/face-register/{mode}"

    // Faculty (primary tabs — bottom navigation)
    const val FACULTY_HOME = "faculty/home"
    const val FACULTY_SCHEDULE = "faculty/schedule"
    const val FACULTY_ANALYTICS_DASHBOARD = "faculty/analytics"
    const val FACULTY_ALERTS = "faculty/alerts"
    const val FACULTY_PROFILE = "faculty/profile"

    // Faculty (secondary / stack screens)
    const val FACULTY_LIVE_FEED = "faculty/live-feed/{scheduleId}/{roomId}"
    const val FACULTY_REPORTS = "faculty/reports"
    const val FACULTY_CLASS_DETAIL = "faculty/class-detail/{scheduleId}"
    const val FACULTY_STUDENT_DETAIL = "faculty/student-detail/{studentId}/{scheduleId}"
    const val FACULTY_EDIT_PROFILE = "faculty/edit-profile"
    const val FACULTY_NOTIFICATIONS = "faculty/notifications"
    const val FACULTY_LIVE_ATTENDANCE = "faculty/live-attendance/{scheduleId}"
    const val FACULTY_MANUAL_ENTRY = "faculty/manual-entry/{scheduleId}"

    // Common
    const val SETTINGS = "settings"

    // ── Helper functions ────────────────────────────────────────────────

    fun facultyLiveFeed(scheduleId: String, roomId: String) =
        "faculty/live-feed/$scheduleId/$roomId"

    fun facultyClassDetail(scheduleId: String) =
        "faculty/class-detail/$scheduleId"

    fun facultyStudentDetail(studentId: String, scheduleId: String) =
        "faculty/student-detail/$studentId/$scheduleId"

    fun facultyLiveAttendance(scheduleId: String) =
        "faculty/live-attendance/$scheduleId"

    fun facultyManualEntry(scheduleId: String) =
        "faculty/manual-entry/$scheduleId"

    fun studentAttendanceDetail(attendanceId: String, scheduleId: String, date: String) =
        "student/attendance-detail/$attendanceId/$scheduleId/$date"

    fun studentFaceRegister(mode: String) =
        "student/face-register/$mode"

    fun registerStep2(studentId: String, firstName: String, lastName: String, email: String) =
        "register/step2/$studentId/$firstName/$lastName/${email.ifBlank { "_" }}"


}

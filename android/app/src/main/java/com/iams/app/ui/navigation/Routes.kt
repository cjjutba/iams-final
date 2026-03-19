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
    const val REGISTER_STEP2 = "register/step2/{studentId}/{firstName}/{lastName}"
    const val EMAIL_VERIFICATION = "email-verification/{email}"

    // Face registration flow (nested nav graph for shared ViewModel)
    const val REGISTER_FACE_FLOW = "register/face-flow"
    const val REGISTER_STEP3_INNER = "register/step3"
    const val REGISTER_REVIEW_INNER = "register/review"

    // Public aliases
    const val REGISTER_STEP3 = REGISTER_FACE_FLOW
    const val REGISTER_REVIEW = REGISTER_REVIEW_INNER

    // Student
    const val STUDENT_HOME = "student/home"
    const val STUDENT_SCHEDULE = "student/schedule"
    const val STUDENT_HISTORY = "student/history"
    const val STUDENT_PROFILE = "student/profile"

    // Faculty
    const val FACULTY_HOME = "faculty/home"
    const val FACULTY_LIVE_FEED = "faculty/live-feed/{scheduleId}/{roomId}"
    const val FACULTY_REPORTS = "faculty/reports"
    const val FACULTY_PROFILE = "faculty/profile"

    fun facultyLiveFeed(scheduleId: String, roomId: String) =
        "faculty/live-feed/$scheduleId/$roomId"

    fun registerStep2(studentId: String, firstName: String, lastName: String) =
        "register/step2/$studentId/$firstName/$lastName"

    fun emailVerification(email: String) =
        "email-verification/$email"
}

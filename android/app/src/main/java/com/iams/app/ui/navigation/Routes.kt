package com.iams.app.ui.navigation

object Routes {
    const val LOGIN = "login"
    const val REGISTER_STEP1 = "register/step1"
    const val REGISTER_STEP2 = "register/step2/{studentId}/{firstName}/{lastName}"
    const val EMAIL_VERIFICATION = "email-verification/{email}"

    // Face registration flow (nested nav graph for shared ViewModel)
    const val REGISTER_FACE_FLOW = "register/face-flow"
    const val REGISTER_STEP3_INNER = "register/step3"
    const val REGISTER_REVIEW_INNER = "register/review"

    // Public aliases that other screens use to navigate into the flow
    const val REGISTER_STEP3 = REGISTER_FACE_FLOW
    const val REGISTER_REVIEW = REGISTER_REVIEW_INNER

    const val STUDENT_HOME = "student/home"
    const val STUDENT_SCHEDULE = "student/schedule"
    const val STUDENT_HISTORY = "student/history"
    const val STUDENT_PROFILE = "student/profile"

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

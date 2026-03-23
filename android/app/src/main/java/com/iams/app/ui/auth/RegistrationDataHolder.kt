package com.iams.app.ui.auth

/**
 * Temporary in-memory holder for registration data between steps.
 *
 * Matches the React Native flow where data is passed via navigation params
 * between Step 1 → Step 2 → Step 3 → Step 4 (Review).
 *
 * Account creation (register API call) only happens in Step 4.
 * This object is cleared after registration completes.
 */
object RegistrationDataHolder {
    // Step 1 data
    var studentId: String = ""
    var firstName: String = ""
    var lastName: String = ""

    // Step 2 data
    var email: String = ""
    var password: String = ""

    fun clear() {
        studentId = ""
        firstName = ""
        lastName = ""
        email = ""
        password = ""
    }
}

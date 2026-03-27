package com.iams.app.ui.utils

import android.util.Patterns

/**
 * Centralized input validation. Returns null if valid, error message if invalid.
 */
object InputValidation {

    fun validateRequired(value: String, fieldName: String): String? {
        return if (value.isBlank()) "$fieldName is required" else null
    }

    fun validateEmail(email: String): String? {
        if (email.isBlank()) return "Email is required"
        if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) return "Invalid email address"
        return null
    }

    fun validatePassword(password: String, minLength: Int = 8): String? {
        if (password.isBlank()) return "Password is required"
        if (password.length < minLength) return "Password must be at least $minLength characters"
        return null
    }

    fun validatePasswordMatch(password: String, confirmPassword: String): String? {
        if (confirmPassword.isBlank()) return "Please confirm your password"
        if (password != confirmPassword) return "Passwords do not match"
        return null
    }

    fun validatePhone(phone: String): String? {
        if (phone.isBlank()) return "Phone number is required"
        if (!phone.matches(Regex("^09\\d{9}$"))) return "Invalid phone number (09XXXXXXXXX)"
        return null
    }

    fun validatePhoneOptional(phone: String): String? {
        if (phone.isBlank()) return null
        if (!phone.matches(Regex("^09\\d{9}$"))) return "Invalid phone number (09XXXXXXXXX)"
        return null
    }

    fun validateStudentId(studentId: String): String? {
        return if (studentId.isBlank()) "Student ID is required" else null
    }

    fun validateBirthdate(mmddyyyy: String): String? {
        if (mmddyyyy.length != 8) return "Enter birthdate as MMDDYYYY"
        val mm = mmddyyyy.substring(0, 2).toIntOrNull() ?: return "Invalid month"
        val dd = mmddyyyy.substring(2, 4).toIntOrNull() ?: return "Invalid day"
        val yyyy = mmddyyyy.substring(4, 8).toIntOrNull() ?: return "Invalid year"
        if (mm !in 1..12) return "Month must be 01-12"
        if (dd !in 1..31) return "Day must be 01-31"
        if (yyyy !in 1950..2015) return "Year must be 1950-2015"
        return null
    }
}

/**
 * Centralized input sanitization applied before API calls.
 */
object InputSanitizer {
    fun email(value: String): String = value.trim().lowercase()
    fun studentId(value: String): String = value.trim().uppercase()
    fun trimmed(value: String): String = value.trim()
    fun digitsOnly(value: String, maxLength: Int): String = value.filter { it.isDigit() }.take(maxLength)
}

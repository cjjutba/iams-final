package com.iams.app.ui.utils

import android.util.Patterns

/**
 * Unified password policy used across registration, password reset,
 * and edit-profile change-password flows.
 *
 * Requirements:
 *   - Minimum 8 characters
 *   - At least one uppercase letter (A-Z)
 *   - At least one lowercase letter (a-z)
 *   - At least one digit (0-9)
 *   - No whitespace
 *   - No special characters required
 */
object PasswordPolicy {
    const val MIN_LENGTH = 8
    const val MAX_LENGTH = 128
    const val REQUIREMENTS_TEXT =
        "At least 8 characters with uppercase, lowercase, and a number."

    private val UPPERCASE = Regex("[A-Z]")
    private val LOWERCASE = Regex("[a-z]")
    private val DIGIT = Regex("\\d")
    private val WHITESPACE = Regex("\\s")

    fun hasMinLength(value: String): Boolean = value.length >= MIN_LENGTH
    fun hasUppercase(value: String): Boolean = UPPERCASE.containsMatchIn(value)
    fun hasLowercase(value: String): Boolean = LOWERCASE.containsMatchIn(value)
    fun hasDigit(value: String): Boolean = DIGIT.containsMatchIn(value)
    fun hasNoWhitespace(value: String): Boolean = !WHITESPACE.containsMatchIn(value)

    /**
     * Evaluates every rule against the candidate password and returns a snapshot
     * suitable for real-time UI feedback (checklist + strength meter).
     */
    fun evaluate(password: String): PasswordEvaluation {
        val rules = listOf(
            PasswordRule(
                id = RuleId.MIN_LENGTH,
                label = "At least $MIN_LENGTH characters",
                satisfied = hasMinLength(password),
            ),
            PasswordRule(
                id = RuleId.UPPERCASE,
                label = "Contains an uppercase letter (A-Z)",
                satisfied = hasUppercase(password),
            ),
            PasswordRule(
                id = RuleId.LOWERCASE,
                label = "Contains a lowercase letter (a-z)",
                satisfied = hasLowercase(password),
            ),
            PasswordRule(
                id = RuleId.DIGIT,
                label = "Contains a number (0-9)",
                satisfied = hasDigit(password),
            ),
        )
        val satisfiedCount = rules.count { it.satisfied }
        val strength = when {
            password.isEmpty() -> PasswordStrength.EMPTY
            satisfiedCount <= 1 -> PasswordStrength.WEAK
            satisfiedCount == 2 -> PasswordStrength.FAIR
            satisfiedCount == 3 -> PasswordStrength.GOOD
            else -> PasswordStrength.STRONG
        }
        return PasswordEvaluation(
            rules = rules,
            strength = strength,
            satisfiedCount = satisfiedCount,
            totalCount = rules.size,
            hasWhitespace = !hasNoWhitespace(password),
        )
    }

    /**
     * Returns the first rule violation as a human-readable error, or null if
     * the password satisfies every requirement. Used on submit.
     */
    fun firstError(password: String): String? {
        if (password.isEmpty()) return "Password is required"
        if (!hasNoWhitespace(password)) return "Password cannot contain spaces"
        if (password.length < MIN_LENGTH) return "Password must be at least $MIN_LENGTH characters"
        if (password.length > MAX_LENGTH) return "Password is too long (max $MAX_LENGTH)"
        if (!hasUppercase(password)) return "Password must include an uppercase letter"
        if (!hasLowercase(password)) return "Password must include a lowercase letter"
        if (!hasDigit(password)) return "Password must include a number"
        return null
    }
}

enum class RuleId { MIN_LENGTH, UPPERCASE, LOWERCASE, DIGIT }

data class PasswordRule(
    val id: RuleId,
    val label: String,
    val satisfied: Boolean,
)

enum class PasswordStrength { EMPTY, WEAK, FAIR, GOOD, STRONG }

data class PasswordEvaluation(
    val rules: List<PasswordRule>,
    val strength: PasswordStrength,
    val satisfiedCount: Int,
    val totalCount: Int,
    val hasWhitespace: Boolean,
) {
    val isValid: Boolean get() = satisfiedCount == totalCount && !hasWhitespace
}

/**
 * Centralized input validation. Returns null if valid, error message if invalid.
 */
object InputValidation {

    fun validateRequired(value: String, fieldName: String): String? {
        return if (value.isBlank()) "$fieldName is required" else null
    }

    fun validateEmail(email: String): String? {
        val trimmed = email.trim()
        if (trimmed.isBlank()) return "Email is required"
        if (trimmed.length > 254) return "Email is too long"
        if (!Patterns.EMAIL_ADDRESS.matcher(trimmed).matches()) return "Invalid email address"
        return null
    }

    /**
     * Unified password validator. The optional [minLength] parameter is kept
     * for source compatibility with legacy callers but is ignored — policy
     * length comes from [PasswordPolicy.MIN_LENGTH].
     */
    @Suppress("UNUSED_PARAMETER")
    fun validatePassword(password: String, minLength: Int = PasswordPolicy.MIN_LENGTH): String? {
        return PasswordPolicy.firstError(password)
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

    /**
     * Passwords must never be trimmed or transformed in a way that changes the
     * user's intended value — we only strip stray whitespace that the IME may
     * inject (e.g. trailing autocorrect space). The unified policy rejects any
     * whitespace inside the password at validation time.
     */
    fun password(value: String): String = value.trim()
}

package com.iams.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.components.PasswordMatchIndicator
import com.iams.app.ui.components.PasswordStrengthMeter
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.PasswordPolicy
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary

/**
 * Step 2: Collect email and password. NO API call here — account creation
 * happens in Step 4 (Review).
 *
 * Validation:
 *   - Email: RFC + live sanitization on submit
 *   - Password: unified [PasswordPolicy] with real-time strength meter and
 *     rule checklist
 *   - Confirm password: live, character-by-character comparison. The Continue
 *     button is disabled until passwords match *and* policy passes, and
 *     `proceed()` re-validates before navigation so the keyboard Done action
 *     can never slip through a mismatch either.
 */
@Composable
fun RegisterStep2Screen(
    navController: NavController,
    studentId: String,
    firstName: String,
    lastName: String,
    prefillEmail: String = "",
) {
    var email by remember { mutableStateOf(prefillEmail) }
    var password by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }

    var emailError by remember { mutableStateOf<String?>(null) }
    var passwordError by remember { mutableStateOf<String?>(null) }
    var confirmPasswordError by remember { mutableStateOf<String?>(null) }

    // Touched flags so we only show errors after the user interacts with the field.
    var passwordTouched by remember { mutableStateOf(false) }
    var confirmTouched by remember { mutableStateOf(false) }

    val focusManager = LocalFocusManager.current

    // Real-time password evaluation — `derivedStateOf` automatically tracks
    // reads of `password` (a MutableState) and recomputes on change. No keys
    // are passed to `remember` because that would recreate the derived state
    // on every keystroke, which is what caused mismatch races previously.
    val evaluation by remember { derivedStateOf { PasswordPolicy.evaluate(password) } }

    // Live "passwords do not match" message, suppressed until confirm is touched.
    val liveConfirmError by remember {
        derivedStateOf {
            when {
                !confirmTouched || confirmPassword.isEmpty() -> null
                password != confirmPassword -> "Passwords do not match"
                else -> null
            }
        }
    }

    val passwordsMatch by remember {
        derivedStateOf { confirmPassword.isNotEmpty() && password == confirmPassword }
    }

    val emailValid by remember {
        derivedStateOf { InputValidation.validateEmail(email) == null }
    }

    val formValid by remember {
        derivedStateOf { emailValid && evaluation.isValid && passwordsMatch }
    }

    fun proceed() {
        // Mark touched so every field can surface its error after a failed submit.
        passwordTouched = true
        confirmTouched = true

        val sanitizedEmail = InputSanitizer.email(email)
        val sanitizedPassword = InputSanitizer.password(password)

        val eErr = InputValidation.validateEmail(sanitizedEmail)
        val pErr = InputValidation.validatePassword(sanitizedPassword)
        val cErr = InputValidation.validatePasswordMatch(sanitizedPassword, confirmPassword)

        emailError = eErr
        passwordError = pErr
        confirmPasswordError = cErr

        // Defensive: never navigate if anything is wrong, including a last-
        // moment mismatch check against the raw (untrimmed) confirm value.
        if (eErr != null || pErr != null || cErr != null) return
        if (sanitizedPassword != confirmPassword) {
            confirmPasswordError = "Passwords do not match"
            return
        }

        RegistrationDataHolder.studentId = studentId
        RegistrationDataHolder.firstName = firstName
        RegistrationDataHolder.lastName = lastName
        RegistrationDataHolder.email = sanitizedEmail
        RegistrationDataHolder.password = sanitizedPassword

        navController.navigate(Routes.REGISTER_FACE_FLOW)
    }

    AuthLayout(
        showBack = true,
        title = "Create Account",
        subtitle = "Step 2 of 4 - Set up your account",
        onBack = { navController.popBackStack() }
    ) {
        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Step 2 of 4",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        LinearProgressIndicator(
            progress = { 0.5f },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(50)),
            color = Primary,
            trackColor = Border,
        )

        Spacer(modifier = Modifier.height(20.dp))

        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Secondary, RoundedCornerShape(10.dp))
                .padding(horizontal = 12.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Outlined.Person,
                contentDescription = null,
                tint = TextSecondary
            )
            Spacer(modifier = Modifier.weight(1f))
            Text(
                text = "$firstName $lastName",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onBackground
            )
            Spacer(modifier = Modifier.weight(1f))
            Text(
                text = studentId,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "Set your contact details and secure password for your account.",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Email field
        IAMSTextField(
            value = email,
            onValueChange = { newValue ->
                email = newValue
                emailError = null
            },
            label = "Email",
            error = emailError,
            placeholder = "your.email@example.com",
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            )
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Password field — live strength + rule checklist below
        IAMSTextField(
            value = password,
            onValueChange = { newValue ->
                password = newValue
                passwordTouched = true
                passwordError = null
                // If confirm was typed first, re-validate it live so the
                // match indicator updates without needing to re-touch confirm.
                if (confirmPassword.isNotEmpty()) confirmPasswordError = null
            },
            label = "Password",
            placeholder = "At least 8 characters",
            error = if (passwordTouched) passwordError else null,
            isPassword = true,
            supportingText = PasswordPolicy.REQUIREMENTS_TEXT,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            )
        )

        if (password.isNotEmpty() || passwordTouched) {
            Spacer(modifier = Modifier.height(12.dp))
            PasswordStrengthMeter(evaluation = evaluation)
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Confirm password field
        IAMSTextField(
            value = confirmPassword,
            onValueChange = { newValue ->
                confirmPassword = newValue
                confirmTouched = true
                confirmPasswordError = null
            },
            label = "Confirm Password",
            error = confirmPasswordError ?: liveConfirmError,
            placeholder = "Re-enter your password",
            isPassword = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    focusManager.clearFocus()
                    proceed()
                }
            )
        )

        if (confirmPassword.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            PasswordMatchIndicator(
                password = password,
                confirmPassword = confirmPassword,
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        IAMSButton(
            text = "Continue",
            onClick = { proceed() },
            enabled = formValid,
        )
    }
}

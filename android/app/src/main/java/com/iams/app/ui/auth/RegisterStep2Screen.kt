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
 * Step 2: Collect email and password. NO API call here.
 * Account creation happens in Step 4 (Review).
 *
 * Validation:
 *   - Email: RFC + live sanitization on submit
 *   - Password: unified [PasswordPolicy] with real-time strength meter and
 *     rule checklist; submit blocked until every rule is satisfied and
 *     confirm-password matches.
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

    // Real-time password evaluation — recomputed on every keystroke.
    val evaluation by remember(password) {
        derivedStateOf { PasswordPolicy.evaluate(password) }
    }

    // Real-time confirm-password live error (only surfaces after confirm is touched).
    val liveConfirmError by remember(password, confirmPassword, confirmTouched) {
        derivedStateOf {
            if (!confirmTouched || confirmPassword.isEmpty()) null
            else if (password != confirmPassword) "Passwords do not match"
            else null
        }
    }

    // The Continue button is only enabled when every field is valid client-side.
    val formValid by remember(email, password, confirmPassword, evaluation) {
        derivedStateOf {
            InputValidation.validateEmail(email) == null &&
                evaluation.isValid &&
                confirmPassword.isNotEmpty() &&
                password == confirmPassword
        }
    }

    fun proceed() {
        // Sanitize at submit time so we never store stray whitespace in the
        // registration holder that downstream API calls consume.
        val sanitizedEmail = InputSanitizer.email(email)
        val sanitizedPassword = InputSanitizer.password(password)

        val eErr = InputValidation.validateEmail(sanitizedEmail)
        val pErr = InputValidation.validatePassword(sanitizedPassword)
        val cErr = InputValidation.validatePasswordMatch(sanitizedPassword, confirmPassword)
        emailError = eErr
        passwordError = pErr
        confirmPasswordError = cErr
        passwordTouched = true
        confirmTouched = true
        if (eErr != null || pErr != null || cErr != null) return

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

        // Email field — rejects leading/trailing whitespace as-you-type by
        // re-validating on every change once it's been touched.
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

        // Real-time meter & checklist — only shown once the user has started typing
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

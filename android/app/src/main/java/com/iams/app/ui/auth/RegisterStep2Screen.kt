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
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary

/**
 * Step 2: Collect email and password. NO API call here.
 * Account creation happens in Step 4 (Review).
 * Matches the React Native flow where Step 2 is data-collection only.
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
    val focusManager = LocalFocusManager.current
    val toastState = LocalToastState.current

    fun proceed() {
        if (email.isBlank() || password.isBlank() || confirmPassword.isBlank()) {
            toastState.showToast("Please fill in all fields", ToastType.ERROR)
            return
        }
        if (!email.contains("@")) {
            toastState.showToast("Please enter a valid email address", ToastType.ERROR)
            return
        }
        if (password != confirmPassword) {
            toastState.showToast("Passwords do not match", ToastType.ERROR)
            return
        }
        if (password.length < 6) {
            toastState.showToast("Password must be at least 6 characters", ToastType.ERROR)
            return
        }

        // Store data for Step 4 (Review) — no API call yet
        RegistrationDataHolder.studentId = studentId
        RegistrationDataHolder.firstName = firstName
        RegistrationDataHolder.lastName = lastName
        RegistrationDataHolder.email = email
        RegistrationDataHolder.password = password

        // Navigate to face capture (Step 3)
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

        // Student info badge
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
            onValueChange = { email = it },
            label = "Email",
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

        // Password field
        IAMSTextField(
            value = password,
            onValueChange = { password = it },
            label = "Password",
            placeholder = "At least 6 characters",
            isPassword = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            )
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Confirm password field
        IAMSTextField(
            value = confirmPassword,
            onValueChange = { confirmPassword = it },
            label = "Confirm Password",
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

        Spacer(modifier = Modifier.height(32.dp))

        // Continue button (NOT "Create Account" — account is created in Step 4)
        IAMSButton(
            text = "Continue",
            onClick = { proceed() },
        )
    }
}

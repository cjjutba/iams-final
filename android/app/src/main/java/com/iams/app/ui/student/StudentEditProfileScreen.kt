package com.iams.app.ui.student

import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Email
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.TextTertiary
import androidx.compose.material3.pulltorefresh.PullToRefreshBox

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentEditProfileScreen(
    navController: NavController,
    viewModel: StudentEditProfileViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current

    // Show toast messages for success/error
    LaunchedEffect(uiState.profileSuccess) {
        uiState.profileSuccess?.let {
            toastState.showToast(it, ToastType.SUCCESS)
            viewModel.clearProfileMessages()
        }
    }

    LaunchedEffect(uiState.profileError) {
        uiState.profileError?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearProfileMessages()
        }
    }

    LaunchedEffect(uiState.passwordSuccess) {
        uiState.passwordSuccess?.let {
            toastState.showToast(it, ToastType.SUCCESS)
            viewModel.clearPasswordMessages()
        }
    }

    LaunchedEffect(uiState.passwordError) {
        uiState.passwordError?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearPasswordMessages()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Edit Profile",
            onBack = { navController.popBackStack() }
        )

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(spacing.screenPadding)
            ) {
                // --- Personal Information Section ---
                Text(
                    text = "Personal Information",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = spacing.lg)
                )

                // Email input
                IAMSTextField(
                    value = uiState.email,
                    onValueChange = { viewModel.updateEmail(it) },
                    label = "Email",
                    placeholder = "your.email@example.com",
                    error = uiState.emailError,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    leadingIcon = {
                        Icon(
                            Icons.Outlined.Email,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                            tint = TextTertiary
                        )
                    }
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                // Phone input
                IAMSTextField(
                    value = uiState.phone,
                    onValueChange = { viewModel.updatePhone(it) },
                    label = "Phone",
                    placeholder = "09XXXXXXXXX",
                    error = uiState.phoneError,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                    leadingIcon = {
                        Icon(
                            Icons.Outlined.Phone,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                            tint = TextTertiary
                        )
                    }
                )

                Spacer(modifier = Modifier.height(spacing.xxl))

                // Save profile button
                IAMSButton(
                    text = "Save Changes",
                    onClick = { viewModel.saveProfile() },
                    variant = IAMSButtonVariant.PRIMARY,
                    size = IAMSButtonSize.LG,
                    isLoading = uiState.isSavingProfile,
                    loadingText = "Saving...",
                    enabled = !uiState.isSavingProfile
                )

                Spacer(modifier = Modifier.height(spacing.xxl))

                // Divider
                HorizontalDivider(
                    modifier = Modifier.padding(vertical = spacing.xxl),
                    thickness = 1.dp,
                    color = Border
                )

                // --- Change Password Section ---
                Text(
                    text = "Change Password",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = spacing.lg)
                )

                // Current password
                IAMSTextField(
                    value = uiState.currentPassword,
                    onValueChange = { viewModel.updateCurrentPassword(it) },
                    label = "Current Password",
                    placeholder = "Current Password",
                    error = uiState.currentPasswordError,
                    isPassword = true,
                    leadingIcon = {
                        Icon(
                            Icons.Outlined.Lock,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                            tint = TextTertiary
                        )
                    }
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                // New password
                IAMSTextField(
                    value = uiState.newPassword,
                    onValueChange = { viewModel.updateNewPassword(it) },
                    label = "New Password",
                    placeholder = "New Password",
                    error = uiState.newPasswordError,
                    isPassword = true,
                    leadingIcon = {
                        Icon(
                            Icons.Outlined.Lock,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                            tint = TextTertiary
                        )
                    }
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                // Confirm password
                IAMSTextField(
                    value = uiState.confirmPassword,
                    onValueChange = { viewModel.updateConfirmPassword(it) },
                    label = "Confirm Password",
                    placeholder = "Confirm Password",
                    error = uiState.confirmPasswordError,
                    isPassword = true,
                    leadingIcon = {
                        Icon(
                            Icons.Outlined.Lock,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                            tint = TextTertiary
                        )
                    }
                )

                Spacer(modifier = Modifier.height(spacing.xxl))

                // Change password button
                IAMSButton(
                    text = "Change Password",
                    onClick = { viewModel.changePassword() },
                    variant = IAMSButtonVariant.SECONDARY,
                    size = IAMSButtonSize.LG,
                    isLoading = uiState.isChangingPassword,
                    loadingText = "Changing...",
                    enabled = !uiState.isChangingPassword
                )

                Spacer(modifier = Modifier.height(spacing.xxxl))
            }

        }
    }
}

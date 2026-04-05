package com.iams.app.ui.faculty

import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyEditProfileScreen(
    navController: NavController,
    viewModel: FacultyEditProfileViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current

    // Show toast for success/error
    LaunchedEffect(uiState.successMessage) {
        uiState.successMessage?.let {
            toastState.showToast(it, ToastType.SUCCESS)
            viewModel.clearMessages()
        }
    }

    LaunchedEffect(uiState.errorMessage) {
        uiState.errorMessage?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearMessages()
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        IAMSHeader(
            title = "Edit Profile",
            onBack = { navController.popBackStack() }
        )

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize(),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(spacing.lg),
            ) {
                // -- Profile section --
                IAMSTextField(
                    value = uiState.email,
                    onValueChange = { viewModel.updateEmail(it) },
                    label = "Email",
                    placeholder = "your.email@example.com",
                    error = uiState.emailError,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                IAMSTextField(
                    value = uiState.phone,
                    onValueChange = { viewModel.updatePhone(it) },
                    label = "Phone",
                    placeholder = "09XXXXXXXXX",
                    error = uiState.phoneError,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                IAMSButton(
                    text = "Save",
                    onClick = { viewModel.saveProfile() },
                    size = IAMSButtonSize.LG,
                    isLoading = uiState.isSavingProfile,
                    loadingText = "Saving...",
                    enabled = uiState.profileDirty,
                )

                Spacer(modifier = Modifier.height(spacing.xxl))

                HorizontalDivider(thickness = 1.dp, color = Border)

                Spacer(modifier = Modifier.height(spacing.xxl))

                // -- Password section --
                IAMSTextField(
                    value = uiState.currentPassword,
                    onValueChange = { viewModel.updateCurrentPassword(it) },
                    label = "Current Password",
                    placeholder = "Current Password",
                    error = uiState.currentPasswordError,
                    isPassword = true,
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                IAMSTextField(
                    value = uiState.newPassword,
                    onValueChange = { viewModel.updateNewPassword(it) },
                    label = "New Password",
                    placeholder = "New Password",
                    error = uiState.newPasswordError,
                    isPassword = true,
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                IAMSTextField(
                    value = uiState.confirmPassword,
                    onValueChange = { viewModel.updateConfirmPassword(it) },
                    label = "Confirm Password",
                    placeholder = "Confirm Password",
                    error = uiState.confirmPasswordError,
                    isPassword = true,
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                IAMSButton(
                    text = "Change Password",
                    onClick = { viewModel.changePassword() },
                    variant = IAMSButtonVariant.SECONDARY,
                    size = IAMSButtonSize.LG,
                    isLoading = uiState.isChangingPassword,
                    loadingText = "Changing...",
                )

                Spacer(modifier = Modifier.height(spacing.xxl))
            }
        }
    }
}

package com.iams.app.ui.student

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.content.Intent
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.MainActivity
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentProfileScreen(
    navController: NavController,
    viewModel: StudentProfileViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val layout = IAMSThemeTokens.layout
    val context = LocalContext.current
    val toastState = LocalToastState.current

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // Restart Activity on logout — goes through Splash → no tokens → Welcome
    LaunchedEffect(uiState.loggedOut) {
        if (uiState.loggedOut) {
            val intent = Intent(context, MainActivity::class.java)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            context.startActivity(intent)
        }
    }

    // Sign out confirmation dialog
    var showSignOutDialog by remember { mutableStateOf(false) }
    if (showSignOutDialog) {
        AlertDialog(
            onDismissRequest = { showSignOutDialog = false },
            title = { Text("Sign Out") },
            text = { Text("Are you sure you want to sign out?") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showSignOutDialog = false
                        viewModel.logout()
                    }
                ) {
                    Text("Sign Out", color = AbsentFg)
                }
            },
            dismissButton = {
                TextButton(onClick = { showSignOutDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(title = "Profile")

        when {
            uiState.isLoading && uiState.user == null -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Primary)
                }
            }

            uiState.error != null && uiState.user == null -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = spacing.xxl),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = uiState.error!!,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.error,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(spacing.lg))
                        IAMSButton(
                            text = "Retry",
                            onClick = { viewModel.loadProfile() },
                            variant = IAMSButtonVariant.OUTLINE,
                            fullWidth = false
                        )
                        Spacer(modifier = Modifier.height(spacing.md))
                        IAMSButton(
                            text = "Sign Out",
                            onClick = { viewModel.logout() },
                            variant = IAMSButtonVariant.OUTLINE,
                            fullWidth = false,
                            leadingIcon = {
                                Icon(
                                    Icons.AutoMirrored.Filled.Logout,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = AbsentFg
                                )
                            }
                        )
                    }
                }
            }

            else -> {
                PullToRefreshBox(
                    isRefreshing = uiState.isRefreshing,
                    onRefresh = { viewModel.refresh() },
                    modifier = Modifier.fillMaxSize()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(
                                horizontal = spacing.lg,
                                vertical = spacing.xxl
                            ),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        // ── Profile header ──

                        // Avatar circle with initials
                        val firstName = uiState.user?.firstName ?: ""
                        val lastName = uiState.user?.lastName ?: ""
                        val initials = buildString {
                            if (firstName.isNotEmpty()) append(firstName.first().uppercaseChar())
                            if (lastName.isNotEmpty()) append(lastName.first().uppercaseChar())
                        }

                        Box(
                            modifier = Modifier
                                .size(layout.avatarXl)
                                .clip(CircleShape)
                                .background(Secondary),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = initials,
                                fontSize = 24.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = TextSecondary
                            )
                        }

                        Spacer(modifier = Modifier.height(spacing.lg))

                        // Full name
                        Text(
                            text = "$firstName $lastName".trim(),
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Bold,
                            color = Primary,
                            textAlign = TextAlign.Center
                        )

                        Spacer(modifier = Modifier.height(spacing.sm))

                        // Student ID
                        if (!uiState.user?.studentId.isNullOrBlank()) {
                            Text(
                                text = uiState.user?.studentId ?: "",
                                style = MaterialTheme.typography.bodyLarge,
                                color = TextSecondary,
                                textAlign = TextAlign.Center
                            )
                        }

                        Spacer(modifier = Modifier.height(spacing.xxxl))

                        // ── Info card ──
                        IAMSCard {
                            Column(modifier = Modifier.fillMaxWidth()) {
                                InfoRow(
                                    label = "Email",
                                    value = uiState.user?.email ?: "--"
                                )

                                Spacer(modifier = Modifier.height(spacing.md))

                                InfoRow(
                                    label = "Role",
                                    value = (uiState.user?.role ?: "student")
                                        .replaceFirstChar { it.uppercaseChar() }
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(spacing.xxl))
                        HorizontalDivider(thickness = 1.dp, color = Border)
                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // ── Action items ──
                        Column(modifier = Modifier.fillMaxWidth()) {
                            ActionItem(
                                icon = Icons.Default.Person,
                                label = "Edit Profile",
                                onClick = { navController.navigate(Routes.STUDENT_EDIT_PROFILE) }
                            )
                            ActionItem(
                                icon = Icons.Default.CameraAlt,
                                label = "Re-register Face",
                                onClick = { navController.navigate(Routes.studentFaceRegister("reregister")) }
                            )
                            ActionItem(
                                icon = Icons.Default.Notifications,
                                label = "Notifications",
                                onClick = { navController.navigate(Routes.STUDENT_NOTIFICATIONS) }
                            )
                            ActionItem(
                                icon = Icons.Default.Settings,
                                label = "Settings",
                                onClick = { navController.navigate(Routes.SETTINGS) }
                            )
                        }

                        Spacer(modifier = Modifier.height(spacing.xxl))
                        HorizontalDivider(thickness = 1.dp, color = Border)
                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // ── Sign out button ──
                        IAMSButton(
                            text = "Sign Out",
                            onClick = { showSignOutDialog = true },
                            variant = IAMSButtonVariant.OUTLINE,
                            size = IAMSButtonSize.LG,
                            enabled = !uiState.isLoading,
                            isLoading = uiState.isLoading,
                            leadingIcon = {
                                Icon(
                                    Icons.AutoMirrored.Filled.Logout,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = AbsentFg
                                )
                            }
                        )

                        Spacer(modifier = Modifier.height(spacing.xxl))
                    }
                }
            }
        }
    }
}

// ── Sub-components ──

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextTertiary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            color = Primary
        )
    }
}

@Composable
private fun ActionItem(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = spacing.lg),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            modifier = Modifier.size(20.dp),
            tint = TextSecondary
        )
        Spacer(modifier = Modifier.width(spacing.md))
        Text(
            text = label,
            style = MaterialTheme.typography.bodyLarge,
            color = Primary,
            modifier = Modifier.weight(1f)
        )
        Icon(
            Icons.AutoMirrored.Filled.KeyboardArrowRight,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = TextTertiary
        )
    }

    HorizontalDivider(thickness = 1.dp, color = Border)
}

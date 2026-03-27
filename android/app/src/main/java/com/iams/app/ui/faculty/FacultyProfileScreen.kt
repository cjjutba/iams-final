package com.iams.app.ui.faculty

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
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
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyProfileScreen(
    navController: NavController,
    viewModel: FacultyProfileViewModel = hiltViewModel()
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

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
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
                    modifier = Modifier.fillMaxSize(),
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
                                horizontal = spacing.screenPadding,
                                vertical = 0.dp
                            ),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Avatar circle (80dp)
                        Box(
                            modifier = Modifier
                                .size(layout.avatarXl)
                                .clip(CircleShape)
                                .background(Secondary),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Default.Person,
                                contentDescription = "Profile",
                                modifier = Modifier.size(40.dp),
                                tint = TextTertiary
                            )
                        }

                        Spacer(modifier = Modifier.height(spacing.lg))

                        // Full name (h2)
                        Text(
                            text = "${uiState.user?.firstName ?: ""} ${uiState.user?.lastName ?: ""}".trim(),
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary,
                            textAlign = TextAlign.Center
                        )

                        Spacer(modifier = Modifier.height(spacing.sm))

                        // Role text
                        Text(
                            text = "Faculty",
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextSecondary,
                            textAlign = TextAlign.Center
                        )

                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Info card
                        IAMSCard {
                            ProfileInfoRow(
                                label = "Email",
                                value = uiState.user?.email ?: "--"
                            )

                            Spacer(modifier = Modifier.height(spacing.md))

                            ProfileInfoRow(
                                label = "Department",
                                value = uiState.user?.role?.replaceFirstChar { it.uppercase() }
                                    ?: "--"
                            )
                        }

                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Divider
                        HorizontalDivider(color = Border, thickness = 1.dp)

                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Action items
                        Column(modifier = Modifier.fillMaxWidth()) {
                            ProfileActionItem(
                                icon = Icons.Default.Person,
                                label = "Edit Profile",
                                onClick = { navController.navigate(Routes.FACULTY_EDIT_PROFILE) }
                            )
                            ProfileActionItem(
                                icon = Icons.Default.Notifications,
                                label = "Notifications",
                                onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) }
                            )
                            ProfileActionItem(
                                icon = Icons.Default.Settings,
                                label = "Settings",
                                onClick = { navController.navigate(Routes.SETTINGS) }
                            )
                        }

                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Divider
                        HorizontalDivider(color = Border, thickness = 1.dp)

                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Sign Out button
                        IAMSButton(
                            text = "Sign Out",
                            onClick = { viewModel.logout() },
                            variant = IAMSButtonVariant.OUTLINE,
                            size = IAMSButtonSize.LG,
                            fullWidth = true,
                            enabled = !uiState.isLoading,
                            isLoading = uiState.isLoading,
                            loadingText = "Signing out...",
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

@Composable
private fun ProfileInfoRow(
    label: String,
    value: String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
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
            color = TextPrimary
        )
    }
}

@Composable
private fun ProfileActionItem(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .padding(vertical = spacing.lg),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = label,
            modifier = Modifier.size(20.dp),
            tint = TextSecondary
        )
        Spacer(modifier = Modifier.width(spacing.md))
        Text(
            text = label,
            style = MaterialTheme.typography.bodyLarge,
            color = TextPrimary,
            modifier = Modifier.weight(1f)
        )
        Icon(
            Icons.Default.ChevronRight,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = TextTertiary
        )
    }

    HorizontalDivider(color = Border, thickness = 1.dp)
}

package com.iams.app.ui.common

import android.content.Intent
import android.net.Uri
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

// Switch track colors matching the RN design
private val SwitchTrackOff = Color(0xFFE5E5E5)
private val SwitchTrackOn = Color(0xFF171717)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    navController: NavController,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val context = LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Settings",
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
                    .padding(bottom = spacing.xxxl)
            ) {
                // ========== Notification Preferences ==========
                IAMSCard {
                    Text(
                        text = "Notification Preferences",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))

                    if (uiState.isLoading) {
                        // Loading placeholder
                        repeat(4) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth(0.6f)
                                            .height(14.dp)
                                            .background(Border)
                                    )
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth(0.85f)
                                            .height(10.dp)
                                            .background(Border)
                                    )
                                }
                                Box(
                                    modifier = Modifier
                                        .size(width = 44.dp, height = 26.dp)
                                        .background(Border)
                                )
                            }
                            if (it < 3) {
                                HorizontalDivider(color = Border)
                            }
                        }
                    } else if (uiState.prefs != null) {
                        val prefs = uiState.prefs!!

                        ToggleItem(
                            label = "Attendance Confirmations",
                            description = "Confirm when your attendance is successfully recorded",
                            value = prefs.attendanceConfirmation,
                            onToggle = { viewModel.togglePreference("attendance_confirmation", it) },
                            disabled = uiState.updatingKey == "attendance_confirmation"
                        )

                        ToggleItem(
                            label = "Early Leave Alerts",
                            description = "Get notified when an early leave is detected",
                            value = prefs.earlyLeaveAlerts,
                            onToggle = { viewModel.togglePreference("early_leave_alerts", it) },
                            disabled = uiState.updatingKey == "early_leave_alerts"
                        )

                        if (uiState.isFaculty) {
                            ToggleItem(
                                label = "Anomaly Alerts",
                                description = "Receive alerts about unusual attendance patterns",
                                value = prefs.anomalyAlerts,
                                onToggle = { viewModel.togglePreference("anomaly_alerts", it) },
                                disabled = uiState.updatingKey == "anomaly_alerts"
                            )
                        }

                        ToggleItem(
                            label = "Low Attendance Warning",
                            description = "Get warned when attendance drops below the threshold",
                            value = prefs.lowAttendanceWarning,
                            onToggle = { viewModel.togglePreference("low_attendance_warning", it) },
                            disabled = uiState.updatingKey == "low_attendance_warning"
                        )

                        if (uiState.isFaculty) {
                            ToggleItem(
                                label = "Daily Digest",
                                description = "Receive a daily attendance summary at 8 PM",
                                value = prefs.dailyDigest,
                                onToggle = { viewModel.togglePreference("daily_digest", it) },
                                disabled = uiState.updatingKey == "daily_digest"
                            )
                        }

                        ToggleItem(
                            label = "Weekly Digest",
                            description = "Receive a weekly attendance summary",
                            value = prefs.weeklyDigest,
                            onToggle = { viewModel.togglePreference("weekly_digest", it) },
                            disabled = uiState.updatingKey == "weekly_digest"
                        )

                        ToggleItem(
                            label = "Email Notifications",
                            description = "Also receive notifications via email",
                            value = prefs.emailEnabled,
                            onToggle = { viewModel.togglePreference("email_enabled", it) },
                            disabled = uiState.updatingKey == "email_enabled",
                            isLast = true
                        )
                    } else {
                        Text(
                            text = "Unable to load preferences. Pull to refresh.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextTertiary
                        )
                    }
                }

                Spacer(modifier = Modifier.height(spacing.lg))

                // ========== Appearance ==========
                IAMSCard {
                    Text(
                        text = "Appearance",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))

                    SettingItem(label = "Theme", value = "Light")
                    SettingItem(label = "Language", value = "English", isLast = true)
                }

                Spacer(modifier = Modifier.height(spacing.lg))

                // ========== About ==========
                IAMSCard {
                    Text(
                        text = "About",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))

                    SettingItem(label = "App Version", value = "1.0.0")
                    SettingItem(label = "App Name", value = "IAMS")
                    SettingItem(label = "Platform", value = "Android", isLast = true)
                }

                Spacer(modifier = Modifier.height(spacing.lg))

                // ========== Legal ==========
                IAMSCard {
                    Text(
                        text = "Legal",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))

                    SettingItem(
                        label = "Privacy Policy",
                        onPress = {
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://iams.jrmsu.edu.ph/privacy"))
                            context.startActivity(intent)
                        }
                    )
                    SettingItem(
                        label = "Terms of Service",
                        onPress = {
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://iams.jrmsu.edu.ph/terms"))
                            context.startActivity(intent)
                        },
                        isLast = true
                    )
                }

                // ========== Footer ==========
                Spacer(modifier = Modifier.height(spacing.xxxl))

                Text(
                    text = "IAMS - Intelligent Attendance Monitoring System",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextTertiary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = "Jose Rizal Memorial State University",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextTertiary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}

@Composable
private fun ToggleItem(
    label: String,
    description: String? = null,
    value: Boolean,
    onToggle: (Boolean) -> Unit,
    disabled: Boolean = false,
    isLast: Boolean = false
) {
    val spacing = IAMSThemeTokens.spacing

    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = spacing.lg),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(end = spacing.md)
            ) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium
                )
                if (description != null) {
                    Spacer(modifier = Modifier.height(spacing.xs))
                    Text(
                        text = description,
                        style = MaterialTheme.typography.labelSmall,
                        color = TextTertiary
                    )
                }
            }
            Switch(
                checked = value,
                onCheckedChange = onToggle,
                enabled = !disabled,
                colors = SwitchDefaults.colors(
                    checkedTrackColor = SwitchTrackOn,
                    checkedThumbColor = Background,
                    uncheckedTrackColor = SwitchTrackOff,
                    uncheckedThumbColor = Background,
                    uncheckedBorderColor = SwitchTrackOff,
                )
            )
        }
        if (!isLast) {
            HorizontalDivider(color = Border)
        }
    }
}

@Composable
private fun SettingItem(
    label: String,
    value: String? = null,
    onPress: (() -> Unit)? = null,
    isLast: Boolean = false
) {
    val spacing = IAMSThemeTokens.spacing

    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .then(
                    if (onPress != null) Modifier.clickable(onClick = onPress) else Modifier
                )
                .padding(vertical = spacing.lg),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (value != null) {
                    Text(
                        text = value,
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary,
                        modifier = Modifier.padding(end = spacing.sm)
                    )
                }
                if (onPress != null) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowRight,
                        contentDescription = "Navigate",
                        modifier = Modifier.size(20.dp),
                        tint = TextTertiary
                    )
                }
            }
        }
        if (!isLast) {
            HorizontalDivider(color = Border)
        }
    }
}

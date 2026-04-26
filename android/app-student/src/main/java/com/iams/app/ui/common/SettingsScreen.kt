package com.iams.app.ui.common

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun SettingsScreen(
    navController: NavController
) {
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

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(spacing.screenPadding)
                .padding(bottom = spacing.xxxl)
        ) {
                // Notification preferences UI removed in 2026-04-26 cleanup.
                // The student APK no longer surfaces in-app notifications —
                // the bell + Notifications screen + preference toggles
                // were the only consumers, and admins manage all
                // notification policy from the admin portal now.

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

package com.iams.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary

/**
 * AuthLayout — shared layout wrapper for all auth screens.
 *
 * Matches the React Native AuthLayout pattern:
 * - Optional back button (ArrowBack icon + "Back" text)
 * - Title (headlineLarge, bold)
 * - Subtitle (bodyLarge, secondary)
 * - Scrollable content with keyboard avoidance
 */
@Composable
fun AuthLayout(
    title: String? = null,
    subtitle: String? = null,
    showBack: Boolean = false,
    onBack: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .padding(top = 16.dp, bottom = 32.dp)
        ) {
            // Back button
            if (showBack && onBack != null) {
                Row(
                    modifier = Modifier
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                            onClick = onBack
                        )
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "Back",
                        modifier = Modifier.size(24.dp),
                        tint = Primary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Back",
                        style = MaterialTheme.typography.bodyLarge,
                        color = Primary
                    )
                }
                Spacer(modifier = Modifier.height(24.dp))
            }

            // Title
            if (title != null) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineLarge.copy(
                        fontWeight = FontWeight.Bold
                    ),
                    color = Primary
                )
                Spacer(modifier = Modifier.height(12.dp))
            }

            // Subtitle
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodyLarge.copy(
                        lineHeight = 24.sp
                    ),
                    color = TextSecondary
                )
            }

            // Content
            content()
        }
    }
}

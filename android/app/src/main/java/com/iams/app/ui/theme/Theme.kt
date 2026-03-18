package com.iams.app.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Gray900,
    onPrimary = White,
    primaryContainer = Gray200,
    onPrimaryContainer = Gray900,
    secondary = Gray700,
    onSecondary = White,
    secondaryContainer = Gray100,
    onSecondaryContainer = Gray900,
    background = Gray50,
    onBackground = Gray900,
    surface = White,
    onSurface = Gray900,
    surfaceVariant = Gray100,
    onSurfaceVariant = Gray700,
    outline = Gray400,
    error = Red500,
    onError = White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Red700,
)

@Composable
fun IAMSTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = IAMSTypography,
        content = content
    )
}

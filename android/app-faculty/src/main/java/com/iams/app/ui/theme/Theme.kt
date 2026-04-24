package com.iams.app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

// ── Material 3 Color Scheme (mapped to RN monochrome palette) ───────────
private val LightColorScheme = lightColorScheme(
    primary = Primary,
    onPrimary = PrimaryForeground,
    primaryContainer = Secondary,
    onPrimaryContainer = SecondaryForeground,
    secondary = Secondary,
    onSecondary = SecondaryForeground,
    secondaryContainer = Muted,
    onSecondaryContainer = MutedForeground,
    background = Background,
    onBackground = Foreground,
    surface = Background,
    onSurface = Foreground,
    surfaceVariant = Secondary,
    onSurfaceVariant = MutedForeground,
    outline = Border,
    outlineVariant = BorderDark,
    error = AbsentFg,
    onError = PrimaryForeground,
    errorContainer = AbsentBg,
    onErrorContainer = AbsentFg,
)

// ── Spacing Scale (8dp grid) ────────────────────────────────────────────
@Immutable
data class IAMSSpacing(
    val none: Dp = 0.dp,
    val xs: Dp = 4.dp,
    val sm: Dp = 8.dp,
    val md: Dp = 12.dp,
    val lg: Dp = 16.dp,
    val xl: Dp = 20.dp,
    val xxl: Dp = 24.dp,
    val xxxl: Dp = 32.dp,
    val section: Dp = 24.dp,
    val screenPadding: Dp = 16.dp,
    val cardPadding: Dp = 12.dp,
)

// ── Border Radius ───────────────────────────────────────────────────────
@Immutable
data class IAMSRadius(
    val none: Dp = 0.dp,
    val sm: Dp = 6.dp,
    val md: Dp = 10.dp,
    val lg: Dp = 16.dp,
    val xl: Dp = 24.dp,
    val card: Dp = 12.dp,
) {
    val smShape = RoundedCornerShape(sm)
    val mdShape = RoundedCornerShape(md)
    val lgShape = RoundedCornerShape(lg)
    val xlShape = RoundedCornerShape(xl)
    val cardShape = RoundedCornerShape(card)
}

// ── Layout ──────────────────────────────────────────────────────────────
@Immutable
data class IAMSLayout(
    val headerHeight: Dp = 56.dp,
    val tabBarHeight: Dp = 56.dp,
    val inputHeightSm: Dp = 36.dp,
    val inputHeightMd: Dp = 44.dp,
    val inputHeightLg: Dp = 52.dp,
    val buttonHeightSm: Dp = 36.dp,
    val buttonHeightMd: Dp = 44.dp,
    val buttonHeightLg: Dp = 52.dp,
    val iconSm: Dp = 16.dp,
    val iconMd: Dp = 20.dp,
    val iconLg: Dp = 24.dp,
    val avatarSm: Dp = 32.dp,
    val avatarMd: Dp = 40.dp,
    val avatarLg: Dp = 56.dp,
    val avatarXl: Dp = 80.dp,
)

val LocalIAMSSpacing = staticCompositionLocalOf { IAMSSpacing() }
val LocalIAMSRadius = staticCompositionLocalOf { IAMSRadius() }
val LocalIAMSLayout = staticCompositionLocalOf { IAMSLayout() }

// ── Theme extension accessors ───────────────────────────────────────────
object IAMSThemeTokens {
    val spacing: IAMSSpacing
        @Composable get() = LocalIAMSSpacing.current
    val radius: IAMSRadius
        @Composable get() = LocalIAMSRadius.current
    val layout: IAMSLayout
        @Composable get() = LocalIAMSLayout.current
}

// ── Theme Composable ────────────────────────────────────────────────────
@Composable
fun IAMSTheme(content: @Composable () -> Unit) {
    CompositionLocalProvider(
        LocalIAMSSpacing provides IAMSSpacing(),
        LocalIAMSRadius provides IAMSRadius(),
        LocalIAMSLayout provides IAMSLayout(),
    ) {
        MaterialTheme(
            colorScheme = LightColorScheme,
            typography = IAMSTypography,
            content = content
        )
    }
}

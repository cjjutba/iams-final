package com.iams.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val IAMSTypography = Typography(
    // h1 → displayLarge: 32sp, Bold, lineHeight 40sp, letterSpacing -0.5sp
    displayLarge = TextStyle(
        fontSize = 32.sp,
        fontWeight = FontWeight.Bold,
        lineHeight = 40.sp,
        letterSpacing = (-0.5).sp
    ),
    // h2 → headlineLarge: 24sp, SemiBold, lineHeight 32sp, letterSpacing -0.25sp
    headlineLarge = TextStyle(
        fontSize = 24.sp,
        fontWeight = FontWeight.SemiBold,
        lineHeight = 32.sp,
        letterSpacing = (-0.25).sp
    ),
    // h3 → headlineMedium: 20sp, SemiBold, lineHeight 28sp
    headlineMedium = TextStyle(
        fontSize = 20.sp,
        fontWeight = FontWeight.SemiBold,
        lineHeight = 28.sp
    ),
    // h4 → titleLarge: 18sp, SemiBold, lineHeight 26sp
    titleLarge = TextStyle(
        fontSize = 18.sp,
        fontWeight = FontWeight.SemiBold,
        lineHeight = 26.sp
    ),
    // body → titleMedium: 16sp, Normal, lineHeight 24sp
    titleMedium = TextStyle(
        fontSize = 16.sp,
        fontWeight = FontWeight.Normal,
        lineHeight = 24.sp
    ),
    // body → bodyLarge: 16sp, Normal, lineHeight 24sp
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        fontWeight = FontWeight.Normal,
        lineHeight = 24.sp
    ),
    // bodySmall → bodyMedium: 14sp, Normal, lineHeight 20sp
    bodyMedium = TextStyle(
        fontSize = 14.sp,
        fontWeight = FontWeight.Normal,
        lineHeight = 20.sp
    ),
    // caption → bodySmall: 12sp, Normal, lineHeight 16sp
    bodySmall = TextStyle(
        fontSize = 12.sp,
        fontWeight = FontWeight.Normal,
        lineHeight = 16.sp
    ),
    // button → labelLarge: 14sp, SemiBold, lineHeight 20sp, letterSpacing 0.25sp
    labelLarge = TextStyle(
        fontSize = 14.sp,
        fontWeight = FontWeight.SemiBold,
        lineHeight = 20.sp,
        letterSpacing = 0.25.sp
    ),
    // label → labelMedium: 14sp, Medium, lineHeight 20sp
    labelMedium = TextStyle(
        fontSize = 14.sp,
        fontWeight = FontWeight.Medium,
        lineHeight = 20.sp
    ),
    // small label → labelSmall: 12sp, Medium, lineHeight 16sp
    labelSmall = TextStyle(
        fontSize = 12.sp,
        fontWeight = FontWeight.Medium,
        lineHeight = 16.sp
    ),
)

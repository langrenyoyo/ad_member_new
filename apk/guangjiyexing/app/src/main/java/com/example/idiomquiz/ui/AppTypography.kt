package com.example.idiomquiz.ui

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// The reference uses Android system text, not a bundled custom typeface.
// Explicit line heights and zero tracking prevent Material defaults from
// introducing different spacing for otherwise equal sp sizes.
private fun text(size: Int, height: Int, weight: FontWeight = FontWeight.Normal) = TextStyle(
    fontFamily = FontFamily.SansSerif,
    fontWeight = weight,
    fontSize = size.sp,
    lineHeight = height.sp,
    letterSpacing = 0.sp
)

internal val AppTypography = Typography(
    displayLarge = text(38, 46, FontWeight.Bold),
    displayMedium = text(38, 46, FontWeight.Bold),
    displaySmall = text(28, 36, FontWeight.Bold),
    headlineLarge = text(28, 36, FontWeight.Bold),
    headlineMedium = text(20, 28, FontWeight.Bold),
    headlineSmall = text(18, 26, FontWeight.Bold),
    titleLarge = text(18, 26, FontWeight.Bold),
    titleMedium = text(15, 22, FontWeight.Bold),
    titleSmall = text(13, 20, FontWeight.Bold),
    bodyLarge = text(15, 22),
    bodyMedium = text(13, 20),
    bodySmall = text(12, 18),
    labelLarge = text(14, 20, FontWeight.Medium),
    labelMedium = text(12, 18),
    labelSmall = text(11, 16)
)

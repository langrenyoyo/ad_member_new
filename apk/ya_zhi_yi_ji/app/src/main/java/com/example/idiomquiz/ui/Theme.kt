package com.example.idiomquiz.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

internal object AppPalette {
    val Primary = Color(0xFFB5521B)
    val PrimarySoft = Color(0xFFFFF0E3)
    val Background = Color(0xFFFFFAF5)
    val Text = Color(0xFF443125)
    val Muted = Color(0xFF806B5B)
    val Border = Color(0xFFEFDDCF)
}

private val LightColors = lightColorScheme(
    primary = AppPalette.Primary,
    onPrimary = Color.White,
    primaryContainer = AppPalette.PrimarySoft,
    onPrimaryContainer = AppPalette.Primary,
    secondary = Color(0xFFA6663C),
    onSecondary = Color.White,
    secondaryContainer = AppPalette.PrimarySoft,
    onSecondaryContainer = AppPalette.Primary,
    tertiary = Color(0xFF44649B),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFD6E3FF),
    onTertiaryContainer = Color(0xFF061B39),
    background = AppPalette.Background,
    onBackground = AppPalette.Text,
    surface = Color.White,
    onSurface = AppPalette.Text,
    surfaceVariant = AppPalette.PrimarySoft,
    onSurfaceVariant = AppPalette.Muted,
    outline = Color(0xFFA18470),
    outlineVariant = AppPalette.Border,
    error = Color(0xFFBA1A1A),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002)
)

@Composable
fun IdiomQuizTheme(
    @Suppress("UNUSED_PARAMETER") darkTheme: Boolean = false,
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = AppTypography,
        shapes = androidx.compose.material3.Shapes(
            small = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
            medium = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
            large = androidx.compose.foundation.shape.RoundedCornerShape(16.dp)
        ),
        content = content
    )
}

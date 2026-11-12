package com.example.idiomquiz.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFFE86867),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFD9D0),
    onPrimaryContainer = Color(0xFF4B1714),
    secondary = Color(0xFFF0B34F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFDBCA),
    onSecondaryContainer = Color(0xFF351000),
    tertiary = Color(0xFF4C6FAE),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFD6E3FF),
    onTertiaryContainer = Color(0xFF061B39),
    background = Color(0xFFF8EFE5),
    onBackground = Color(0xFF1A1C1B),
    surface = Color(0xFFFFFCF8),
    onSurface = Color(0xFF1A1C1B),
    surfaceVariant = Color(0xFFE8DED0),
    onSurfaceVariant = Color(0xFF404945),
    outline = Color(0xFF707A75),
    error = Color(0xFFBA1A1A),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9DD8CE),
    onPrimary = Color(0xFF003731),
    primaryContainer = Color(0xFF005047),
    onPrimaryContainer = Color(0xFFB8EFE5),
    secondary = Color(0xFFFFB693),
    onSecondary = Color(0xFF542006),
    secondaryContainer = Color(0xFF743617),
    onSecondaryContainer = Color(0xFFFFDBCA),
    tertiary = Color(0xFFA9C7FF),
    onTertiary = Color(0xFF0C3262),
    tertiaryContainer = Color(0xFF345484),
    onTertiaryContainer = Color(0xFFD6E3FF),
    background = Color(0xFF101413),
    onBackground = Color(0xFFE1E3E0),
    surface = Color(0xFF101413),
    onSurface = Color(0xFFE1E3E0),
    surfaceVariant = Color(0xFF404945),
    onSurfaceVariant = Color(0xFFC0C9C4),
    outline = Color(0xFF8A938E),
    error = Color(0xFFFFB4AB),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6)
)

@Composable
fun IdiomQuizTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content
    )
}

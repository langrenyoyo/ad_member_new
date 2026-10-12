package com.example.idiomquiz.ui

import android.os.SystemClock
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import kotlinx.coroutines.delay

@Composable
internal fun SmsSendButton(state: UiState, enabled: Boolean, onClick: () -> Unit) {
    var remaining by remember(state.smsRetryAt) {
        mutableStateOf(((state.smsRetryAt - SystemClock.elapsedRealtime() + 999) / 1000).coerceAtLeast(0))
    }
    LaunchedEffect(state.smsRetryAt) {
        while (remaining > 0) {
            delay(250)
            remaining = ((state.smsRetryAt - SystemClock.elapsedRealtime() + 999) / 1000).coerceAtLeast(0)
        }
    }
    TextButton(onClick = onClick, enabled = enabled && remaining == 0L) {
        Text(if (remaining > 0) "${remaining} 秒后重新获取" else "获取验证码")
    }
}

package com.example.idiomquiz.ads

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** A missing/failed ad must not prevent access to a financial application. */
internal suspend fun enterAfterInterstitial(
    isCurrent: () -> Boolean,
    showAd: suspend () -> Unit,
    enter: () -> Unit
) {
    currentCoroutineContext().ensureActive()
    if (!isCurrent()) return
    try {
        showAd()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (_: Exception) {
        // No fill, load timeout and SDK errors all allow the original entry.
    }
    currentCoroutineContext().ensureActive()
    if (isCurrent()) enter()
}

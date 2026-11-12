package com.example.idiomquiz.ads

import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.suspendCancellableCoroutine

/** Each operation returns only after its ad closes. A failure stops this group. */
internal suspend fun runRewardedAdGroup(
    showInterstitial: suspend () -> Unit,
    showRewarded: suspend () -> Unit
) {
    currentCoroutineContext().ensureActive()
    showInterstitial()
    currentCoroutineContext().ensureActive()
    showRewarded()
    currentCoroutineContext().ensureActive()
    showInterstitial()
}

/** SDK callbacks and disposal must be serialized on the main thread by the caller. */
internal suspend fun awaitAdClose(
    dispose: (() -> Unit) -> Unit,
    start: (closed: () -> Unit, failed: (String) -> Unit) -> (() -> Unit)
) = suspendCancellableCoroutine<Unit> { continuation ->
    val cancel = start(
        { if (continuation.isActive) continuation.resumeWith(Result.success(Unit)) },
        { message -> if (continuation.isActive) continuation.resumeWith(Result.failure(IllegalStateException(message))) }
    )
    continuation.invokeOnCancellation { dispose(cancel) }
}

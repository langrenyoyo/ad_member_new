package com.example.idiomquiz.data

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** One queue across screen instances; the lock spans persistence, I/O and cleanup. */
internal class CampaignRequests {
    private val mutex = Mutex()

    suspend fun <T> exclusive(action: suspend () -> T): T = mutex.withLock { action() }

    // Called inside exclusive, including when recovering before a new submit.
    suspend fun <T> recoverLocked(
        read: () -> T?,
        send: suspend (T) -> Unit,
        clear: () -> Unit,
        definiteFailure: (Exception) -> Boolean
    ) {
        val pending = read() ?: return
        try {
            send(pending)
        } catch (error: Exception) {
            if (definiteFailure(error)) clear()
            throw error
        }
        clear()
    }
}

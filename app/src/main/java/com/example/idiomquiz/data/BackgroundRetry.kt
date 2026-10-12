package com.example.idiomquiz.data

import kotlinx.coroutines.*

/** One best-effort worker; callers never await network recovery. */
internal class BackgroundRetry(private val scope: CoroutineScope, private val cooldownMs: Long = 30_000) {
    private var job: Job? = null
    private var nextStart = 0L
    private var generation = 0L

    @Synchronized
    fun schedule(action: suspend () -> Unit) {
        val now = System.nanoTime() / 1_000_000
        if (job?.isActive == true || now < nextStart) return
        nextStart = now + cooldownMs
        val ownGeneration = ++generation
        job = scope.launch {
            try { action() }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { /* Durable records remain for the next trigger. */ }
            finally { synchronized(this@BackgroundRetry) {
                if (ownGeneration == generation) nextStart = System.nanoTime() / 1_000_000 + cooldownMs
            } }
        }
    }

    @Synchronized
    fun cancel() { generation++; job?.cancel(); job = null; nextStart = 0 }
}

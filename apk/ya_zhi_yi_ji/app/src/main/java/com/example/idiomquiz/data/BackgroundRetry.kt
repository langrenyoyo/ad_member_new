package com.example.idiomquiz.data

import kotlinx.coroutines.*

/** One best-effort worker; callers never await network recovery. */
internal class BackgroundRetry(private val scope: CoroutineScope, private val cooldownMs: Long = 30_000) {
    private var job: Job? = null
    private var nextStart = 0L
    private var generation = 0L
    private var pending: (suspend () -> Unit)? = null

    @Synchronized
    fun schedule(action: suspend () -> Unit) {
        pending = action
        if (job?.isActive == true) return
        val ownGeneration = ++generation
        job = scope.launch {
            while (true) {
                val wait = synchronized(this@BackgroundRetry) {
                    (nextStart - System.nanoTime() / 1_000_000).coerceAtLeast(0)
                }
                delay(wait)
                val work = synchronized(this@BackgroundRetry) {
                    if (ownGeneration != generation) null else pending.also { pending = null }
                } ?: return@launch
                try { work() }
                catch (e: CancellationException) { throw e }
                catch (_: Exception) { /* Durable records remain for the next trigger. */ }
                finally { synchronized(this@BackgroundRetry) {
                    if (ownGeneration == generation) nextStart = System.nanoTime() / 1_000_000 + cooldownMs
                } }
                val again = synchronized(this@BackgroundRetry) {
                    if (ownGeneration != generation) false
                    else if (pending != null) true
                    else { job = null; false }
                }
                if (!again) return@launch
            }
        }
    }

    @Synchronized
    fun cancel() { generation++; pending = null; job?.cancel(); job = null; nextStart = 0 }
}
